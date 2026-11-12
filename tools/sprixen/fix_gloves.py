"""Repaint bare-skin fingers sticking out of Arthur's gloves (Sprixen sometimes draws the far
hand as a fingerless glove). Works on a 256px-frame sheet.

A skin patch is treated as fingers when it is below the waist, touches glove leather, sits
lower than (or level with) that leather, and does not run up into the white sleeve (that is
the forearm, left alone). Finger pixels are recoloured with the glove's leather colour, keeping
their light/dark shading so the drawn knuckles still read.
usage: python3 fix_gloves.py <sheet.png> <out.png>"""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage

SRC = 256


def fix(f):
    f = f.astype(np.float32)
    rgb, a = f[:, :, :3], f[:, :, 3]
    R, G, B = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    lum = rgb.mean(2)
    solid = a > 60
    ys, _ = np.where(solid)
    top, bot = ys.min(), ys.max()
    waist = top + int(0.48 * (bot - top))
    below = np.zeros_like(solid)
    below[top + int(0.58 * (bot - top)):top + int(0.80 * (bot - top))] = True   # hand zone: below the belt buckle, above the boots
    # skin keeps a fair amount of blue (B > ~0.52 R); the gold buckles do not
    skin = solid & below & (R > 150) & (R > G) & (G > B) & (R - B > 45) & (lum > 120) & (B > 0.52 * R)
    leather = solid & (R > G) & (G >= B) & (R - B > 25) & (lum > 40) & (lum < 130)
    sleeve = solid & (rgb.min(2) > 175) & (rgb.max(2) - rgb.min(2) < 40)
    lab, n = ndimage.label(skin, structure=np.ones((3, 3)))
    changed = 0
    for k in range(1, n + 1):
        comp = lab == k
        ring = ndimage.binary_dilation(comp, iterations=3) & leather
        if ring.sum() < 6:
            continue
        if (ndimage.binary_dilation(comp, iterations=3) & sleeve).any():
            continue             # runs up into the white sleeve = forearm, keep
        cy = np.where(comp)[0].mean()
        ly = np.where(ring)[0].mean()
        if cy < ly - 1:          # above the glove = forearm, keep
            continue
        # leather colour of this glove, shaded by the finger's own brightness
        glove = np.median(rgb[ring], axis=0)
        skin_l = np.median(lum[comp])
        shade = (lum[comp] / max(skin_l, 1))[:, None]
        rgb[comp] = np.clip(glove[None, :] * shade, 0, 255)
        changed += int(comp.sum())
    f[:, :, :3] = rgb
    return f.astype(np.uint8), changed


def main():
    im = np.array(Image.open(sys.argv[1]).convert("RGBA"))
    n = im.shape[1] // SRC
    total = []
    for i in range(n):
        im[:, i * SRC:(i + 1) * SRC], c = fix(im[:, i * SRC:(i + 1) * SRC])
        total.append(c)
    Image.fromarray(im).save(sys.argv[2])
    print("finger px repainted per frame:", total)


if __name__ == "__main__":
    main()
