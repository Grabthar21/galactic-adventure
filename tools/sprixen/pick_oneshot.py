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
out = Image.new("RGBA", (SRC * count, SRC), (0, 0, 0, 0))
for k, i in enumerate(idx):
    out.paste(im.crop((i * SRC, 0, (i + 1) * SRC, SRC)), (k * SRC, 0))
out.save(sys.argv[2])
print(f"one-shot: frames {s}..{e} of {n} (heights {hs[s]:.0f}->{hs.min():.0f}->{hs[e]:.0f}), {count} picked")
