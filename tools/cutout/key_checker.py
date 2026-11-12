"""Remove an opaque checkerboard background: flood-fill near-white/light-grey,
low-saturation pixels connected to the image border, then give the 2-px edge band a
soft alpha and pull out the white fringe."""
import sys, numpy as np
from PIL import Image
from scipy import ndimage
src, dst = sys.argv[1], sys.argv[2]
a = np.array(Image.open(src).convert("RGB")).astype(float)
mx, mn = a.max(axis=2), a.min(axis=2)
bgish = (mn > 225) & (mx - mn < 14)                  # checker tones: ~(244,244,244) and (254,254,254)
lab, n = ndimage.label(bgish)
border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
bg = np.isin(lab, list(border))
# close tiny islands of checker trapped by antialiasing next to the border region
bg = ndimage.binary_opening(bg, iterations=1) | (bg & ~ndimage.binary_erosion(~bg, iterations=1))
fg = ~bg
alpha = fg.astype(float)
# soft edge: pixels of the foreground touching background get alpha by how far they are from white
edge = fg & ndimage.binary_dilation(bg, iterations=2)
lum = a.mean(axis=2)
alpha[edge] = np.clip((250 - lum[edge]) / 60.0, 0.0, 1.0)
# un-blend white from edge pixels: c = a*fg + (1-a)*255  ->  fg = (c - (1-a)*255)/a
rgb = a.copy()
m = edge & (alpha > 0.05)
for k in range(3):
    ch = rgb[:, :, k]
    ch[m] = np.clip((ch[m] - (1 - alpha[m]) * 250) / alpha[m], 0, 255)
out = np.dstack([rgb, alpha * 255]).astype(np.uint8)
out[alpha < 0.05] = 0
Image.fromarray(out).save(dst)
lab2, n2 = ndimage.label(alpha > 0.5)
sz = ndimage.sum(np.ones_like(lab2), lab2, range(1, n2 + 1))
objs = ndimage.find_objects(lab2)
print("pieces > 400 px:")
for i, s in enumerate(sz):
    if s > 400:
        o = objs[i]; print(int(s), "box", o[1].start, o[0].start, o[1].stop, o[0].stop)
