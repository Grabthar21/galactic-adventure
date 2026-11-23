"""Clean Sprixen's background-removal leftovers on every frame of a 256px sheet, without
touching the drawing (the 'head_lock: false' path: Sprixen's own head, hair motion and turn
are kept). Same matte clean-up lock_head.py applies.
usage: python3 clean_sheet.py <sheet.png> <out.png>"""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage
from lock_head import clean_body, SRC


def clean_soft(f):
    """clean_body, but the outline keeps Sprixen's soft (anti-aliased) edge instead of a hard
    on/off one, so the downscaled sprite has smooth outlines; small enclosed gaps in the head
    and chest (e.g. the notch Sprixen leaves between nape and collar) are closed."""
    c = clean_body(f)
    solid = c[:, :, 3] > 0
    # backdrop seen through narrow gaps (between the legs, arm and body) comes out light grey-blue;
    # peel such pixels from any see-through area, a few px deep
    rgb = f[:, :, :3]
    greyish = (rgb.min(2) > 115) & (rgb.max(2) - rgb.min(2) < 40) & (rgb[:, :, 2] >= rgb[:, :, 0])
    for _ in range(5):
        peel = solid & ndimage.binary_dilation(~solid) & greyish
        if not peel.any():
            break
        solid &= ~peel
    # enclosed backdrop: a pale neutral/greenish patch boxed in between the arm and the body
    # (Sprixen fills it with its backdrop). The white shirt is a warm white, so a pale patch
    # whose surroundings are mostly NOT warm white is backdrop, not shirt shading.
    lum = rgb.mean(2)
    pale = solid & (rgb.min(2) > 165) & ((rgb[:, :, 2] >= rgb[:, :, 0] - 2) | (rgb[:, :, 1] > rgb[:, :, 0] + 8))
    warm_white = solid & (rgb.min(2) > 165) & (rgb[:, :, 0] > rgb[:, :, 2] + 3)
    lab, nl = ndimage.label(pale)
    for k in range(1, nl + 1):
        comp = lab == k
        sz = int(comp.sum())
        if sz < 6 or sz > 400:
            continue
        ring = ndimage.binary_dilation(comp, iterations=2) & ~comp & solid
        if ring.sum() and (warm_white & ring).sum() / ring.sum() < 0.3:
            solid &= ~comp
    c[~solid, 3] = 0
    top = np.where(solid.any(1))[0]
    if len(top):
        y0, y1 = top.min(), top.max()
        holes, n = ndimage.label(ndimage.binary_fill_holes(solid) & ~solid)
        if n:
            _, (iy, ix) = ndimage.distance_transform_edt(~solid, return_indices=True)
            for k in range(1, n + 1):
                hm = holes == k
                hy = np.where(hm)[0].mean()
                if hm.sum() <= 160 and hy < y0 + 0.45 * (y1 - y0):
                    c[hm, :3] = c[iy[hm], ix[hm], :3]
                    c[hm, 3] = 255
                    solid |= hm
    edge = solid & (ndimage.distance_transform_edt(solid) <= 1.5)
    c[:, :, 3] = np.where(solid, np.where(edge, np.maximum(f[:, :, 3], 0), 255), 0)
    return c

if __name__ == "__main__":
    sheet = np.array(Image.open(sys.argv[1]).convert("RGBA")).astype(np.float32)
    out = sheet.copy()
    for i in range(sheet.shape[1] // SRC):
        out[:, i * SRC:(i + 1) * SRC] = clean_soft(sheet[:, i * SRC:(i + 1) * SRC])
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(sys.argv[2])
