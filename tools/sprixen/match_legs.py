"""Keep the walking body the same height as the approved standing drawing.

match_scale.py sizes a Sprixen walk by its head and upper body, but Sprixen sometimes draws the
legs of one direction longer (Arthur's back walk: taller boots, so he stood ~2.5% taller while
walking up than when standing). A walk should never stand taller than the standing pose (a
stride only bends the knees). This step measures, on the 256px sheet after lock_head, the
height from each frame's head to its feet; if the median is taller than the approved drawing,
the legs (hip line down to the feet) are shortened by that whole number of pixels in every
frame. The head and torso just move down by that amount, so they are not resampled.

usage: python3 match_legs.py <sheet.png> <base.png> <out.png> <profile JSON from head_rows.py>
"""
import json
import sys
import cv2
import numpy as np
from PIL import Image

SRC = 256
DIP = 0.005        # a walk may sit at most this fraction lower/higher than standing before we act
HIP = 0.45         # legs = from this fraction of the body height (head top -> feet) downwards


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
    tm = gray(base[t0:t1])
    by = np.where(base[:, :, 3].max(1) > 40)[0]
    base_h = by.max() - t0                       # head-paste top -> feet, approved drawing
    import os
    gp = os.environ.get("GEOM_SHEET")
    geom = np.array(Image.open(gp).convert("RGBA")).astype(np.float32) if gp else sheet
    hs, tops, bots = [], [], []
    for f in [geom[:, i * SRC:(i + 1) * SRC] for i in range(n)]:
        r = cv2.matchTemplate(gray(f), tm, cv2.TM_CCOEFF_NORMED)
        _, _, _, loc = cv2.minMaxLoc(r)
        ys = np.where(f[:, :, 3].max(1) > 40)[0]
        tops.append(loc[1]); bots.append(ys.max()); hs.append(ys.max() - loc[1])
    med = float(np.median(hs))
    hs = np.array(hs, float)
    # a walk may never stand taller than the standing drawing
    excess = int(round(med - base_h)) if med > base_h * (1 + DIP) else 0
    # Smooth head path: once the feet are put on the ground, a frame's head height is its
    # head-to-feet height. Sprixen's ground line wobbles by a few px (a toe lifts, a heel drops),
    # which would make the head hop. Fit that height with a smooth loop curve (1st + 2nd
    # harmonic: two steps per cycle) and stretch/shrink each frame's legs by the small difference.
    tt = np.arange(n) / n
    X = np.stack([np.ones(n)] + [fn(2 * np.pi * h * tt) for h in (1, 2) for fn in (np.cos, np.sin)], 1)
    coef, *_ = np.linalg.lstsq(X, hs, rcond=None)
    target = X @ coef - excess
    delta = np.clip(target - hs, -9, 9)          # + = legs longer, - = shorter (256px units)
    out = np.zeros_like(sheet)
    for i, f in enumerate(frames):
        top, bot = tops[i], bots[i]
        hip = int(top + HIP * (bot - top))
        L = bot - hip
        k = (L + delta[i]) / L
        new_bot = bot                              # feet stay where they are; the body above moves
        shift = -delta[i]                          # rows above the hip move up when legs lengthen
        pm = f.copy(); pm[..., :3] *= pm[..., 3:4] / 255.0
        yy = np.arange(SRC, dtype=np.float32)
        new_hip = hip + shift
        src = np.where(yy < new_hip, yy - shift, hip + (yy - new_hip) / k)
        src = np.where(yy > new_bot, yy, src)      # below the feet: unchanged (empty)
        y0 = np.clip(np.floor(src).astype(int), 0, SRC - 1)
        y1 = np.clip(y0 + 1, 0, SRC - 1)
        w = (src - np.floor(src))[:, None, None]
        valid = ((src >= 0) & (src <= SRC - 1))[:, None, None]
        g = (pm[y0] * (1 - w) + pm[y1] * w) * valid
        a = g[..., 3:4]
        g[..., :3] = np.where(a > 0, g[..., :3] * 255.0 / np.maximum(a, 1e-3), 0)
        out[:, i * SRC:(i + 1) * SRC] = g
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(sys.argv[3])
    print(f"{sys.argv[1]}: walk median height {med:.0f} vs standing {base_h}"
          f"{' -> legs shortened by %dpx' % excess if excess else ''}; head path smoothed "
          f"(leg change {delta.min():+.1f}..{delta.max():+.1f}px)")


if __name__ == "__main__":
    main()
