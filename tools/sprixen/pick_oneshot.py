"""Cut a one-shot move (e.g. a dodge roll) out of a Sprixen premium sheet (256px frames).

usage: python3 pick_oneshot.py <sheet.png> <out.png> <count> [start end]
Without start/end the move is found automatically: the frames from where the figure first
drops below 94% of its standing height to where it is back above it, plus 2 frames either side
(the take-off and the landing). `count` frames are then picked evenly from that range, so the
move plays the same way at the game's frame rate."""
import sys
import numpy as np
from PIL import Image

SRC = 256
im = Image.open(sys.argv[1]).convert("RGBA")
a = np.array(im)
n = im.width // SRC
count = int(sys.argv[3])
hs = []
for i in range(n):
    al = a[:, i * SRC:(i + 1) * SRC, 3] > 40
    ys = np.where(al.any(1))[0]
    hs.append(ys.max() - ys.min() if len(ys) else 0)
hs = np.array(hs, float)
if len(sys.argv) > 5:
    s, e = int(sys.argv[4]), int(sys.argv[5])
else:
    stand = np.median(np.r_[hs[:3], hs[-3:]])
    low = np.where(hs < 0.94 * stand)[0]
    s, e = max(low.min() - 2, 0), min(low.max() + 2, n - 1)
idx = np.round(np.linspace(s, e, count)).astype(int)
# Sprixen's video smears fast motion: where a neighbouring frame (one either side) is sharper,
# use it instead, so no frame shows a ghosted face. Sharpness: the variance of the Laplacian of
# the figure on grey. The first and last frames stay (take-off and landing), the order stays.
import cv2


def sharpness(i):
    f = a[:, i * SRC:(i + 1) * SRC].astype(np.float32)
    al = f[..., 3:4] / 255
    g = cv2.cvtColor((f[..., :3] * al + 128 * (1 - al)).astype(np.uint8), cv2.COLOR_RGB2GRAY)
    lap = cv2.Laplacian(g, cv2.CV_32F)
    m = cv2.erode((f[..., 3] > 200).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    return float(lap[m].var()) if m.any() else 0.0


for k in range(1, count - 1):
    cands = [c for c in (idx[k] - 1, idx[k], idx[k] + 1) if idx[k - 1] < c < (idx[k + 1] if k + 1 < count else e + 1)]
    idx[k] = max(cands, key=sharpness)
out = Image.new("RGBA", (SRC * count, SRC), (0, 0, 0, 0))
for k, i in enumerate(idx):
    out.paste(im.crop((i * SRC, 0, (i + 1) * SRC, SRC)), (k * SRC, 0))
out.save(sys.argv[2])
open(sys.argv[2] + ".picks", "w").write(",".join(str(int(i)) for i in idx))
print(f"one-shot: frames {s}..{e} of {n} (heights {hs[s]:.0f}->{hs.min():.0f}->{hs[e]:.0f}), {count} picked: {list(map(int, idx))}")
