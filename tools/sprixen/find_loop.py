"""Find the cleanest seamless walk loop in a Sprixen premium sheet (256px frames).
Compares body silhouettes (aligned on the torso) and picks the start/period with the
smallest seam difference, then writes that loop as its own sheet.
usage: python3 find_loop.py <sheet.png> <out.png> [min_period=20] [max_period=44]"""
import sys
import numpy as np
from PIL import Image

SRC = 256
im = Image.open(sys.argv[1]).convert("RGBA")
lo = int(sys.argv[3]) if len(sys.argv) > 3 else 20
hi = int(sys.argv[4]) if len(sys.argv) > 4 else 44
a = np.array(im)
n = im.width // SRC
sil = []
for i in range(n):
    al = a[:, i * SRC:(i + 1) * SRC, 3] > 40
    ys, xs = np.where(al)
    top = ys.min()
    cx = int(round(np.where(al[top + 75:top + 105])[1].mean()))
    sil.append(np.roll(al, 128 - cx, axis=1).astype(np.float32))
best = None
for p in range(lo, min(hi, n - 1) + 1):
    for s in range(0, n - p):
        d = np.abs(sil[s] - sil[s + p]).mean()
        # also make sure the frame after the seam flows (s+1 vs s+p+1 if available)
        if s + p + 1 < n:
            d += 0.5 * np.abs(sil[s + 1] - sil[s + p + 1]).mean()
        score = d
        if best is None or score < best[0]:
            best = (score, s, p)
score, s, p = best
im.crop((s * SRC, 0, (s + p) * SRC, SRC)).save(sys.argv[2])
steps = [np.abs(sil[i] - sil[i + 1]).mean() for i in range(s, s + p - 1)]
print(f"{n} frames; loop = frames {s}..{s + p - 1} (period {p}); seam diff {score:.4f}; "
      f"typical step {np.median(steps):.4f}")
