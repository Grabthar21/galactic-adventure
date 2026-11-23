"""Make the shirt collar behind the neck look the same in every frame of a walk strip.

Sprixen draws the back of the collar cleanly in most frames but as a muddy, speckled or
see-through patch in runs of a few frames (Arthur's side walk: frames 2-4, 19, 24). Single-frame
repairs can't fix a run, so this step uses the whole loop:
  1. the nape box (behind the neck, between the hair and the vest) is located in every frame by
     matching the head + collar area of a reference frame (whole-pixel shift),
  2. the aligned boxes give a per-pixel median over the loop: the clean collar, since most frames
     are clean,
  3. in each frame, pixels of that box where the median is collar (light, low colour) and the frame
     differs from it (darker, browner or see-through) are replaced by the median.
Only collar pixels change; hair, face, vest and motion are untouched.

usage: python3 collar_median.py <walk_strip.png> [out.png]
"""
import sys
import cv2
import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, __import__("os").path.dirname(__file__))
from cells import CELL_W as CW


def gray(f):
    al = f[..., 3:4] / 255.0
    return (f[..., :3].mean(2, keepdims=True) * al + 128 * (1 - al))[..., 0].astype(np.float32)


def nape_box(f):
    """box around the back of the neck: rows chin->chest, from 14 px behind the neck to its front."""
    s = f[..., 3] > 128
    ys = np.where(s.any(1))[0]
    top, bot = ys.min(), ys.max()
    h = bot - top
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    skin = s & (r > 195) & (g > 125) & (b > 80) & (r - b > 55)
    y0, y1 = top + int(.24 * h), top + int(.36 * h)
    cols = np.where(skin[y0:y1].any(0))[0]
    if not len(cols):
        return None
    x0 = cols.min()
    return y0, y1, max(x0 - 14, 0), x0 + 8


def collar_consistency(fr):
    """per frame: collar-area pixels (aligned to the body) that differ strongly from the loop's
    median collar. Used by qa_shape.py."""
    box = nape_box(fr[0])
    if box is None:
        return [0] * len(fr)
    y0, y1, x0, x1 = box
    ty0, ty1, tx0, tx1 = y0 + 2, y1 + 16, max(x0 - 4, 0), x1 + 24
    tmpl = gray(fr[0])[ty0:ty1, tx0:tx1]
    stack = []
    for f in fr:
        r = cv2.matchTemplate(gray(f), tmpl, cv2.TM_SQDIFF)
        _, _, (lx, ly), _ = cv2.minMaxLoc(r)
        dy, dx = ly - ty0, lx - tx0
        stack.append(np.roll(np.roll(f, -dy, 0), -dx, 1)[y0:y1, x0:x1])
    stack = np.stack(stack)
    med = np.median(stack, axis=0)
    m = med[..., :3]
    collar = (med[..., 3] > 200) & (m.min(2) > 165) & (m.max(2) - m.min(2) < 45)
    zone = ndimage.binary_dilation(collar, iterations=1)
    return [int((zone & (np.abs(p[..., :3] - m).max(2) > 60) & (p[..., 3] > 128)).sum() +
                (zone & (p[..., 3] < 128)).sum()) for p in stack]


def main():
    a = np.array(Image.open(sys.argv[1]).convert("RGBA")).astype(np.float32)
    n = a.shape[1] // CW
    fr = [a[:, i * CW:(i + 1) * CW].copy() for i in range(n)]
    box = nape_box(fr[0])
    if box is None:
        print(f"{sys.argv[1]}: no neck found, unchanged")
        return
    y0, y1, x0, x1 = box
    # template: head + collar area of frame 0 (bigger than the box, for a stable match)
    ty0, ty1, tx0, tx1 = y0 + 2, y1 + 16, max(x0 - 4, 0), x1 + 24   # collar + vest top: moves with the body
    tmpl = gray(fr[0])[ty0:ty1, tx0:tx1]
    shifts = []
    for f in fr:
        r = cv2.matchTemplate(gray(f), tmpl, cv2.TM_SQDIFF)
        _, _, (lx, ly), _ = cv2.minMaxLoc(r)
        shifts.append((ly - ty0, lx - tx0))
    stack = np.stack([np.roll(np.roll(f, -dy, 0), -dx, 1)[y0:y1, x0:x1] for f, (dy, dx) in zip(fr, shifts)])
    med = np.median(stack, axis=0)
    mrgb = med[..., :3]
    collar = (med[..., 3] > 200) & (mrgb.min(2) > 165) & (mrgb.max(2) - mrgb.min(2) < 45)
    # the clean collar from the loop replaces the collar area of every frame: the light (collar)
    # part of the median grown by 3 px to take in its edges, feathered so there is no seam
    zone = ndimage.binary_dilation(collar, iterations=3)
    wgt = np.clip(ndimage.gaussian_filter(zone.astype(np.float32), 1.0) * 1.6, 0, 1)
    wgt[ndimage.binary_dilation(collar, iterations=2)] = 1.0
    wgt = wgt[..., None]
    report = []
    for i, (f, (dy, dx)) in enumerate(zip(fr, shifts)):
        patch = stack[i]
        newp = patch * (1 - wgt) + med * wgt
        ys, xs = np.mgrid[y0:y1, x0:x1]
        ys, xs = ys + dy, xs + dx
        ok = (ys >= 0) & (ys < f.shape[0]) & (xs >= 0) & (xs < f.shape[1])
        f[ys[ok], xs[ok]] = newp[ok]
        a[:, i * CW:(i + 1) * CW] = f
        report.append(int((np.abs(newp - patch).max(2) > 30).sum()))
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(sys.argv[2] if len(sys.argv) > 2 else sys.argv[1])
    print(f"{sys.argv[1]}: collar behind the neck matched to the loop's clean collar; px replaced per frame: {report}")


if __name__ == "__main__":
    main()
