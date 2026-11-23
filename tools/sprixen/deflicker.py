"""Repair one-frame blinks in the upper body of a finished walk strip.

Finds exactly what qa_shape.py reports: patches in the upper body (outline or shirt-white layer)
that are present in both neighbouring frames but missing in this one (or the reverse), and
one-frame dents in the outline. Each such patch (grown by 2 px) is replaced by the average of the
two neighbouring frames at that spot, after aligning each neighbour to this frame by the best
whole-pixel shift (within 2 px) of the surrounding area. Neighbours agree there by definition,
so the repaired pixels continue the motion instead of blinking. Everything else is untouched.

usage: python3 deflicker.py <walk_strip.png> [out.png]
"""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, __import__("os").path.dirname(__file__))
from cells import CELL_W as CW
from qa_shape import upper, notches, MIN_BLINK, MIN_DENT


def layers(f):
    s = f[..., 3] > 128
    return s, s & (f[..., :3].min(2) > 170)


def defects(fr, i):
    n = len(fr)
    p, c, q = fr[i - 1], fr[i], fr[(i + 1) % n]
    U = upper(c)[0]
    out = np.zeros(c.shape[:2], bool)
    for k in range(2):
        P, C, Q = layers(p)[k], layers(c)[k], layers(q)[k]
        on = ndimage.binary_erosion(P, iterations=1) & ndimage.binary_erosion(Q, iterations=1)
        off = ~ndimage.binary_dilation(P, iterations=1) & ~ndimage.binary_dilation(Q, iterations=1)
        for m in (on & ~C, off & C):
            lab, nl = ndimage.label(m & U)
            for j in range(1, nl + 1):
                comp = lab == j
                if comp.sum() >= MIN_BLINK:
                    out |= comp
    dent = np.zeros_like(out)
    Np, Nc, Nq = notches(layers(p)[0]), notches(layers(c)[0]), notches(layers(q)[0])
    lone = Nc & U & ~ndimage.binary_dilation(Np, iterations=1) & ~ndimage.binary_dilation(Nq, iterations=1)
    lab, nl = ndimage.label(lone)
    for j in range(1, nl + 1):
        comp = lab == j
        if comp.sum() >= MIN_DENT:
            dent |= comp
    return out, dent


def aligned(src, dst, box):
    """src shifted by the whole-pixel offset (|d| <= 2) that best matches dst inside box."""
    y0, y1, x0, x1 = box
    best = None
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            sh = np.roll(np.roll(src, dy, 0), dx, 1)
            e = np.abs(sh[y0:y1, x0:x1] - dst[y0:y1, x0:x1]).mean()
            if best is None or e < best[0]:
                best = (e, sh)
    return best[1]


def main():
    a = np.array(Image.open(sys.argv[1]).convert("RGBA")).astype(np.float32)
    n = a.shape[1] // CW
    fr = [a[:, i * CW:(i + 1) * CW].copy() for i in range(n)]
    out = [f.copy() for f in fr]
    fixed = []
    for i in range(n):
        d, dent = defects(fr, i)
        if dent.any():
            # a one-frame dent: filled in as the smooth outline would have it, in the colour of
            # the nearest solid pixel (the edge colour)
            solid = fr[i][..., 3] > 200
            _, (iy, ix) = ndimage.distance_transform_edt(~solid, return_indices=True)
            g = ndimage.binary_dilation(dent, iterations=1) & ~solid
            out[i][g, :3] = fr[i][iy[g], ix[g], :3]
            out[i][g, 3] = 255
            fr[i] = out[i].copy()
        if not d.any():
            fixed.append(int(dent.sum()))
            continue
        region = ndimage.binary_dilation(d, iterations=2)
        yy, xx = np.where(region)
        box = (max(yy.min() - 8, 0), yy.max() + 9, max(xx.min() - 8, 0), xx.max() + 9)
        if d.sum() < 12:      # small dents/blinks: neighbours as they are (what qa_shape compares)
            p, q = fr[i - 1], fr[(i + 1) % n]
        else:
            p = aligned(fr[i - 1], fr[i], box)
            q = aligned(fr[(i + 1) % n], fr[i], box)
        pm = lambda f: np.concatenate([f[..., :3] * f[..., 3:4] / 255.0, f[..., 3:4]], -1)
        avg = (pm(p) + pm(q)) / 2
        # coverage: the middle of the three frames' coverage at each pixel, so a spot both
        # neighbours cover is covered and a spot neither covers is clear (no half-filled dents)
        cov = np.median(np.stack([p[..., 3], fr[i][..., 3], q[..., 3]]), axis=0)
        k = np.where(avg[..., 3] > 0, cov / np.maximum(avg[..., 3], 1e-3), 0)[..., None]
        avg = avg * k
        al = avg[..., 3:4]
        avg[..., :3] = np.where(al > 0, avg[..., :3] * 255.0 / np.maximum(al, 1e-3), 0)
        # soft edge around the repaired patch
        w = ndimage.gaussian_filter(region.astype(np.float32), 0.8)
        w = np.maximum(w, region.astype(np.float32) * 0.0)
        w[region] = 1.0
        w = w[..., None]
        out[i] = fr[i] * (1 - w) + avg * w
        fixed.append(int(d.sum() + dent.sum()))
    for i in range(n):
        a[:, i * CW:(i + 1) * CW] = out[i]
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(sys.argv[2] if len(sys.argv) > 2 else sys.argv[1])
    print(f"{sys.argv[1]}: one-frame blinks repaired (px per frame): {fixed}")


if __name__ == "__main__":
    main()
