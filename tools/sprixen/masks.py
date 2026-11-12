"""Skin / hair masks for an in-game strip, used by the recolour shader (player customization).

For every pixel of a finished strip (98x148 cells) this writes a matching mask pixel:
    R = how much the pixel is skin   (0-255)
    G = how much the pixel is hair   (0-255)
Skin uses the same CIE Lab test as skin_match.py (light, orange hue, moderate chroma).
Hair is brown-orange and darker than skin, and must be part of the hair mass on the head:
only the top of each cell (the head) is considered, and only connected patches big enough
to be hair (eyes/irises are separate small dots and stay unmasked). The dark outline is in
neither mask, so it stays dark whatever colours the player picks.
usage: python3 masks.py <strip.png> <mask_out.png> [head_rows=46]
head_rows = height of the head (top of hair to chin) in game pixels; build_char.py passes it
from the head rows it detected in the approved drawing."""
import sys
import cv2
import numpy as np
from PIL import Image
from scipy import ndimage

CELL_W = 98


def ramp(x, lo, hi):
    return np.clip((x - lo) / (hi - lo), 0.0, 1.0)


def lab_parts(rgba):
    lab = cv2.cvtColor(rgba[:, :, :3].astype(np.uint8), cv2.COLOR_RGB2LAB).astype(np.float32)
    l = lab[:, :, 0] * 100 / 255
    a, b = lab[:, :, 1] - 128, lab[:, :, 2] - 128
    return l, np.hypot(a, b), np.degrees(np.arctan2(b, a))


def cell_masks(c, head_rows):
    alpha = c[:, :, 3]
    solid = alpha > 0
    l, chroma, hue = lab_parts(c)
    skin = ramp(l, 54, 62) * ramp(chroma, 8, 14) * (1 - ramp(chroma, 46, 54)) \
        * ramp(hue, 36, 44) * (1 - ramp(hue, 74, 82))
    hairish = (1 - ramp(l, 52, 60)) * ramp(l, 10, 16) * ramp(chroma, 8, 14) \
        * ramp(hue, 28, 36) * (1 - ramp(hue, 78, 86))
    ys = np.where(solid.any(1))[0]
    top = ys.min() if len(ys) else 0
    head = np.zeros_like(solid)
    head[top:top + head_rows] = True
    core = (hairish > 0.5) & head & solid
    lab, n = ndimage.label(core, structure=np.ones((3, 3)))
    keep = np.zeros_like(core)
    if n:
        sizes = ndimage.sum(core, lab, range(1, n + 1))
        for k, s in enumerate(sizes, 1):
            comp = lab == k
            # hair = big patches that reach the top of the head (the vest collar and
            # eyes/brows don't), bangs/sideburns come along because they're attached
            if s >= 25 and comp[top:top + 10].any():
                keep |= comp
    hair = np.where(keep, hairish, 0.0)
    # the dark line art around the face, eyes and lashes touches the hair mass but is outline,
    # not hair: dark pixels next to skin stay out, so they stay dark with any hair colour
    near_skin = ndimage.binary_dilation(skin > 0.5, iterations=2)
    hair *= 1 - (near_skin & (l < 38))
    # eyes, brows and mouth sit inside the face: anything enclosed by skin is a facial feature
    face = ndimage.binary_fill_holes(ndimage.binary_closing(skin > 0.5, iterations=2))
    hair *= 1 - face
    # below brow level, brown pixels bordering the skin are the jaw/neck line art, not hair
    brow = top + int(0.45 * head_rows)
    lower = np.zeros_like(solid)
    lower[brow:] = True
    hair *= 1 - (lower & ndimage.binary_dilation(skin > 0.5, iterations=1))
    hair *= ramp(l, 18, 24)                   # the darkest pixels are always outline
    skin = np.where(solid, skin, 0.0) * (1 - hair)
    # real skin (face, neck, forearms, ears) is a patch with some thickness; 1-2px streaks
    # where the cream shirt blends into the brown vest are not skin
    core = ndimage.binary_opening(skin > 0.5, structure=np.ones((3, 3)))
    # ...except on the head, where ears and the nape are only ~2px thick at game size
    head_skin = (skin > 0.5) & ndimage.binary_dilation(head, iterations=3)
    hl, hn = ndimage.label(head_skin, structure=np.ones((3, 3)))
    if hn:
        hs = ndimage.sum(head_skin, hl, range(1, hn + 1))
        core |= np.isin(hl, [k for k, v in enumerate(hs, 1) if v >= 3])
    lab_s, ns = ndimage.label(skin > 0.15, structure=np.ones((3, 3)))
    ok = np.isin(lab_s, np.unique(lab_s[core])) & (lab_s > 0)
    skin = np.where(ok, skin, 0.0)
    # the soft edge of the skin (pixels half skin, half line art) must follow the skin colour,
    # otherwise they keep the original light tone and glow around a darker face
    core_s = skin > 0.5
    holes = ndimage.binary_fill_holes(ndimage.binary_closing(core_s, iterations=2)) & ~core_s
    features = ndimage.binary_erosion(holes, iterations=1)   # eyes/brows/mouth, minus a 1px rim
    edge = ndimage.binary_dilation(core_s, iterations=2) & solid & (hair < 0.5) & ~features \
        & (l > 20) & (chroma > 6) & (hue > 15) & (hue < 95)
    skin = np.maximum(skin, edge * 1.0)
    return skin, hair


def make_mask(strip, head_rows=46):
    a = np.array(strip.convert("RGBA")).astype(np.float32)
    out = np.zeros(a.shape, np.uint8)
    for i in range(a.shape[1] // CELL_W):
        sl = slice(i * CELL_W, (i + 1) * CELL_W)
        skin, hair = cell_masks(a[:, sl], head_rows)
        out[:, sl, 0] = np.round(skin * 255)
        out[:, sl, 1] = np.round(hair * 255)
        out[:, sl, 3] = 255
    return Image.fromarray(out)


if __name__ == "__main__":
    s = Image.open(sys.argv[1])
    hr = int(sys.argv[3]) if len(sys.argv) > 3 else 46
    make_mask(s, hr).save(sys.argv[2])
