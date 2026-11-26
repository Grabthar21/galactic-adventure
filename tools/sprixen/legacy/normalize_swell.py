"""Remove Sprixen's whole-body 'swell' from a source sheet (256px frames) before head-locking:
each frame is rescaled about its feet so its height change is cut to KEEP of the original
(keeping a soft breath), and optionally only a frame range is kept.
usage: python3 normalize_swell.py <sheet.png> <out.png> [keep=0.25] [first,last]"""
import sys
import numpy as np
from PIL import Image

SRC = 256
sheet = Image.open(sys.argv[1]).convert("RGBA")
keep = float(sys.argv[3]) if len(sys.argv) > 3 else 0.25
n = sheet.width // SRC
lo, hi = (map(int, sys.argv[4].split(","))) if len(sys.argv) > 4 else (0, n - 1)
idx = list(range(lo, hi + 1))
frames = [sheet.crop((i * SRC, 0, (i + 1) * SRC, SRC)) for i in idx]
boxes = []
for f in frames:
    ys, xs = np.where(np.array(f)[:, :, 3] > 40)
    boxes.append((ys.min(), ys.max(), xs.mean()))
H = np.array([b[1] - b[0] for b in boxes], float)
ref = float(np.median(H))
out = Image.new("RGBA", (SRC * len(frames), SRC), (0, 0, 0, 0))
for k, (f, (top, bot, cx), h) in enumerate(zip(frames, boxes, H)):
    s = (ref + keep * (h - ref)) / h
    w2 = round(SRC * s)
    g = f.resize((w2, w2), Image.LANCZOS) if abs(s - 1) > 1e-3 else f
    px = round(cx - cx * s)              # keep the body centre in place
    py = round(bot - bot * s)            # keep the feet on the same row
    cell = Image.new("RGBA", (SRC, SRC), (0, 0, 0, 0))
    cell.alpha_composite(g, (max(px, 0), max(py, 0)), (max(-px, 0), max(-py, 0)))
    out.paste(cell, (k * SRC, 0))
out.save(sys.argv[2])
print(f"frames {idx[0]}-{idx[-1]}: heights {H.min():.0f}-{H.max():.0f} -> ~{ref:.0f} (+{keep:.0%} of change)")
