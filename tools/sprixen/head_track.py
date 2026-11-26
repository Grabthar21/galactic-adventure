"""Follow the head through a Sprixen premium move frame by frame and measure its size in every
frame, relative to the first.

usage: python3 head_track.py <sheet.png> <start> <end> [--report]

The head is a rigid ball: however he turns, it should stay one size. Neighbouring frames of
Sprixen's 24 fps video differ very little, so the head cut from one frame (a disc around it) is
found in the next one almost exactly -- turned a few degrees, a fraction of a percent bigger or
smaller. Searching each step over turn (+-24 deg) and size (+-5%) and multiplying the steps gives
the head's size in every frame, even upside down and from the top, where a fixed head picture
can't be recognised. Printed: one size per frame, start..end, comma separated (or a table with
--report).
"""
import sys
import numpy as np
import cv2
from PIL import Image

SRC = 256


def grey(f):
    rgb = f[..., :3].astype(np.float32)
    a = f[..., 3:4].astype(np.float32) / 255
    g = cv2.cvtColor((rgb * a + 128 * (1 - a)).astype(np.float32), cv2.COLOR_RGB2GRAY)
    return g - 128.0


def warp(img, cx, cy, ang, sc, size, with_matrix=False):
    """the size x size patch whose centre is (cx, cy) in img, turned by ang and scaled by sc"""
    R = cv2.getRotationMatrix2D((cx, cy), ang, sc)
    R[0, 2] += size / 2 - cx
    R[1, 2] += size / 2 - cy
    out = cv2.warpAffine(img, R, (size, size), flags=cv2.INTER_LINEAR, borderValue=0)
    return (out, R) if with_matrix else out


def disc(size, r):
    yy, xx = np.mgrid[:size, :size]
    return (((xx - size / 2 + 0.5) ** 2 + (yy - size / 2 + 0.5) ** 2) <= r * r).astype(np.float32)


def first_head(f):
    s = f[..., 3] > 128
    ys = np.where(s.any(1))[0]
    t, b = ys.min(), ys.max()
    band = s[t:t + int(0.24 * (b - t))]
    yy, xx = np.nonzero(band)
    xs = np.where(band.any(0))[0]
    d = xs.max() - xs.min()
    return xx.mean(), t + yy.mean(), d


def track(sheet, start, end):
    a = np.array(Image.open(sheet).convert("RGBA"))
    fr = [a[:, i * SRC:(i + 1) * SRC] for i in range(start, end + 1)]
    cx, cy, d = first_head(fr[0])
    r = 0.55 * d                         # the head disc: hair and face, a little of the neck
    size = int(2 * r + 8) | 1
    m = disc(size, r)
    T = warp(grey(fr[0]), cx, cy, 0, 1, size)
    cum, ang_cum = 1.0, 0.0
    out = [(1.0, 0.0, 1.0, cx, cy)]
    for k in range(1, len(fr)):
        g = grey(fr[k])
        best = (-2, 0, 1, cx, cy)
        win = 34
        x0, y0 = int(cx - win), int(cy - win)

        def try_(ang, sc):
            # the next frame around the last centre, turned/scaled back by the total so far plus
            # this step, so its head should look exactly like the canonical head picture T
            big = warp(g, cx, cy, -(ang_cum + ang), 1 / (cum * sc), size + 2 * win)
            res = cv2.matchTemplate(big.astype(np.float32), (T * m).astype(np.float32), cv2.TM_CCORR_NORMED,
                                    mask=m)
            res[~np.isfinite(res)] = -2
            _, v, _, loc = cv2.minMaxLoc(res)
            return v, loc
        for ang in np.arange(-24, 25, 3):
            for sc in np.arange(0.95, 1.051, 0.01):
                v, loc = try_(ang, sc)
                if v > best[0]:
                    best = (v, ang, sc, loc)
        _, ang0, sc0, _ = best
        for ang in np.arange(ang0 - 2, ang0 + 2.1, 0.5):
            for sc in np.arange(sc0 - 0.01, sc0 + 0.0101, 0.0025):
                v, loc = try_(ang, sc)
                if v > best[0]:
                    best = (v, ang, sc, loc)
        v, ang, sc, loc = best
        # where the match centre sits, back in the next frame's own coordinates
        _, M = warp(g, cx, cy, -(ang_cum + ang), 1 / (cum * sc), size + 2 * win, with_matrix=True)
        Mi = cv2.invertAffineTransform(M)
        px_, py_ = loc[0] + size / 2, loc[1] + size / 2
        ncx = Mi[0, 0] * px_ + Mi[0, 1] * py_ + Mi[0, 2]
        ncy = Mi[1, 0] * px_ + Mi[1, 1] * py_ + Mi[1, 2]
        cum *= sc
        ang_cum += ang
        cx, cy = ncx, ncy
        # the next step compares with this frame's head, so the picture never drifts away from it
        T = warp(g, cx, cy, -ang_cum, 1 / cum, size)
        out.append((cum, ang_cum, v, cx, cy))
    return out


if __name__ == "__main__":
    sheet, s, e = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    res = track(sheet, s, e)
    if "--report" in sys.argv:
        for k, (c, ang, v, x, y) in enumerate(res):
            print(f"  frame {s + k:3d}: head size {c:.3f}  turned {ang:7.1f} deg  match {v:.3f}  at ({x:.0f},{y:.0f})")
    else:
        print(",".join(f"{c:.4f}" for c, *_ in res))
