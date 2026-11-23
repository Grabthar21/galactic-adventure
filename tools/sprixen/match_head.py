"""Keep Sprixen's own head (its turn and hair motion) but at the approved drawing's size.

In the Sprixen-style mode (config style.head_lock = false) the approved head is no longer pasted
on every frame, so whatever size Sprixen drew the head at shows. Sprixen tends to draw the head a
few % smaller in its walks than in the approved standing drawing (Arthur's front walk: ~6%), which
makes him change proportions when he starts or stops walking. This step:
  1. measures the head scale: the approved head (HEAD_TOP..CHIN_CUT) is template-matched at
     0.85-1.15x against the frames; the best median scale k is how big Sprixen drew it,
  2. enlarges each frame's head by 1/k about the base of the neck, with a soft taper over the
     collar so the neck flows into the shoulders (no seam, nothing pasted).
Skips frames' bodies entirely; only the head grows/shrinks. Run before match_legs.py.

usage: python3 match_head.py <sheet.png> <base.png> <out.png> <profile JSON from head_rows.py>
"""
import json
import sys
import cv2
import numpy as np
from PIL import Image

SRC = 256
TOL = 0.015        # within 1.5% -> leave the frames alone


def gray(rgba):
    a = rgba[:, :, 3:4] / 255.0
    g = cv2.cvtColor(rgba[:, :, :3].astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
    return (g[:, :, None] * a + 128 * (1 - a))[:, :, 0].astype(np.float32)


def main():
    sheet = np.array(Image.open(sys.argv[1]).convert("RGBA")).astype(np.float32)
    base = np.array(Image.open(sys.argv[2]).convert("RGBA")).astype(np.float32)
    prof = json.loads(sys.argv[4])
    n = sheet.shape[1] // SRC
    frames = [sheet[:, i * SRC:(i + 1) * SRC] for i in range(n)]
    t0, t1 = prof["HEAD_TOP"], prof["CHIN_CUT"]
    head = base[t0:t1]
    cols = np.where(head[:, :, 3].max(0) > 40)[0]
    head = head[:, cols.min():cols.max() + 1]
    tm0 = gray(head)
    imgs = [gray(f) for f in frames]
    best = None
    for k in np.arange(0.85, 1.151, 0.005):
        t = cv2.resize(tm0, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
        sc = [cv2.matchTemplate(im, t, cv2.TM_CCOEFF_NORMED).max() for im in imgs]
        s = float(np.median(sc))
        if best is None or s > best[0]:
            best = (s, k)
    score, k = best
    f = 1.0 / k
    scale_it = abs(f - 1) >= TOL
    if not scale_it:
        f = 1.0
    t = cv2.resize(tm0, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
    th, tw = t.shape
    locs = []
    for im in imgs:
        r = cv2.matchTemplate(im, t, cv2.TM_CCOEFF_NORMED)
        _, _, _, (lx, ly) = cv2.minMaxLoc(r)
        # sub-pixel y (parabola through the neighbours) for a steady bob estimate
        y = float(ly)
        if 0 < ly < r.shape[0] - 1:
            a_, b_, c_ = r[ly - 1, lx], r[ly, lx], r[ly + 1, lx]
            den = a_ - 2 * b_ + c_
            if den < 0:
                y += 0.5 * (a_ - c_) / den
        locs.append((lx, y))
    # steady bob: Sprixen's head hops by a few px between neighbouring frames. Fit the measured
    # head height with a smooth loop curve (1st + 2nd harmonic: two steps per cycle) and move the
    # upper body onto it, tapering to nothing at the hips so the planted feet never move.
    ys_m = np.array([l[1] for l in locs])
    tt = np.arange(n) / n
    X = np.stack([np.ones(n)] + [fn(2 * np.pi * h * tt) for h in (1, 2) for fn in (np.cos, np.sin)], 1)
    coef, *_ = np.linalg.lstsq(X, ys_m, rcond=None)
    fit = X @ coef
    shift = np.clip(fit - ys_m, -4, 4)
    out = np.zeros_like(sheet)
    yy, xx = np.mgrid[0:SRC, 0:SRC].astype(np.float32)
    for i, fr in enumerate(frames):
        lx, ly = locs[i]
        ax, ay = lx + tw / 2.0, ly + th            # base of the neck (bottom centre of the head box)
        sx, sy = xx.copy(), yy.copy()
        if scale_it:
            feather_up, feather_down = 0.12 * th, 0.10 * th
            w = np.clip((ay + feather_down - yy) / (feather_up + feather_down), 0, 1)
            w = w * w * (3 - 2 * w)                  # smoothstep
            sc = 1 + (f - 1) * w
            sx = ax + (xx - ax) / sc
            sy = ay + (yy - ay) / sc
        ys_a = np.where(fr[:, :, 3].max(1) > 40)[0]
        top, bot = ys_a.min(), ys_a.max()
        chest, hip = top + 0.36 * (bot - top), top + 0.52 * (bot - top)
        wv = np.clip((hip - yy) / (hip - chest), 0, 1)
        wv = wv * wv * (3 - 2 * wv)
        sy = sy - shift[i] * wv                     # sample from above/below -> content moves by shift
        pm = fr.copy(); pm[..., :3] *= pm[..., 3:4] / 255.0
        g = cv2.remap(pm, sx.astype(np.float32), sy.astype(np.float32), cv2.INTER_LINEAR,
                      borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        a = g[..., 3:4]
        g[..., :3] = np.where(a > 0, g[..., :3] * 255.0 / np.maximum(a, 1e-3), 0)
        out[:, i * SRC:(i + 1) * SRC] = g
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(sys.argv[3])
    print(f"{sys.argv[1]}: head drawn at {k:.3f}x the approved size (match {score:.2f}) -> "
          f"{'enlarged by %.3f' % f if scale_it else 'size unchanged'}; bob steadied (max {np.abs(shift).max():.1f}px)")


if __name__ == "__main__":
    main()
