"""Scale the rigged side-walk frames into the game's 98x148 cells, using the same
scale and anchors as slice_character_sheet.py so they match the other animations."""
import sys, numpy as np, json
from PIL import Image
sys.argv = ['x']; import importlib.util
spec = importlib.util.spec_from_file_location('sl', 'slice2.py')
src = open('slice2.py').read().split('TARGET=')[0]          # reuse extract() only
ns = {}; exec(src, ns)
rows = ns['extract']('arthur_sheet.png')
ref = np.median([f.shape[0] for f in rows[2]])
TARGET, S = 268.0, 0.5
k = TARGET / ref * S
CW, CH = 98, 148
meta = json.load(open('side_walk_src.json'))
strip = Image.open('side_walk_src.png')
n = meta['count']; fw = meta['frame_w']
# one shared head anchor (body is fixed in the rig), so no per-frame horizontal jitter
first = np.array(strip.crop((0, 0, fw, strip.height)))
ys, xs = np.nonzero(first[:, :, 3])
top = ys.min(); h = ys.max() - top
head_x = np.nonzero(first[top:top + int(h * 0.3), :, 3])[1].mean()
out = Image.new('RGBA', (CW * n, CH), (0, 0, 0, 0))
for i in range(n):
    f = strip.crop((i * fw, 0, (i + 1) * fw, strip.height))
    a = np.array(f)[:, :, 3]
    ys, xs = np.nonzero(a)
    f = f.crop((0, 0, fw, ys.max() + 1))
    g = f.resize((round(f.width * k), round(f.height * k)), Image.LANCZOS)
    out.alpha_composite(g, (i * CW + int(round(CW / 2 - head_x * k)), CH - 2 - g.height))
out.save('arthur_side_walk.png')
print('saved', out.size, 'k=%.3f' % k)
