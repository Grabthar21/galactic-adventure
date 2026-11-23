"""Clean Sprixen's background-removal leftovers on every frame of a 256px sheet, without
touching the drawing (the 'head_lock: false' path: Sprixen's own head, hair motion and turn
are kept). Same matte clean-up lock_head.py applies.
usage: python3 clean_sheet.py <sheet.png> <out.png>"""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage
from lock_head import clean_body, SRC


def restore_collar(f):
    """Sprixen's background removal sometimes eats part of the white collar between neck and
    shoulder: those pixels keep their real colour but come out half see-through, so the clean-up
    cut a notch there and the notch was patched with mismatched colours. Pixels in that band that
    sit in a concave notch of the body (inside a small closing of the shape) are made opaque again:
    their own colour where Sprixen kept one, otherwise painted in smoothly from the neighbours."""
    import cv2
    a = f[:, :, 3]
    body = a >= 60
    ys = np.where(body.any(1))[0]
    if not len(ys):
        return f
    top, bot = ys.min(), ys.max()
    h = bot - top
    band = np.zeros_like(body)
    band[top + int(0.20 * h):top + int(0.42 * h)] = True        # chin to chest
    disk = np.ones((9, 9), bool)
    yy, xx = np.mgrid[-4:5, -4:5]
    disk = (yy * yy + xx * xx) <= 16
    closed = ndimage.binary_closing(np.pad(body, 6), structure=disk)[6:-6, 6:-6]
    notch = closed & ~body & band
    if not notch.any():
        return f
    out = f.copy()
    # only real collar: pale pixels Sprixen kept (some alpha), in pieces of a useful size that touch
    # the opaque white shirt. Empty background between nape and shoulder, and pale specks at the
    # hair edge, are left alone (painting those added pixels that were never part of the drawing).
    rgb = f[:, :, :3]
    shirt = body & (rgb.min(2) > 175) & (rgb[:, :, 0] >= rgb[:, :, 2] - 4)
    pale = notch & (a >= 15) & (rgb.min(2) > 150)
    pale = ndimage.binary_opening(pale, structure=np.ones((3, 3)))   # solid patches only, no wisps
    lab, nl = ndimage.label(pale, structure=np.ones((3, 3)))
    near_shirt = ndimage.binary_dilation(shirt, iterations=1)
    for k in range(1, nl + 1):
        comp = lab == k
        if comp.sum() >= 6 and (comp & near_shirt).any():
            out[comp, 3] = 255
    return out


def clean_soft(f, collar=True, aa=True):
    """clean_body, but the outline keeps Sprixen's soft (anti-aliased) edge instead of a hard
    on/off one, so the downscaled sprite has smooth outlines; small enclosed gaps in the head
    and chest (e.g. the notch Sprixen leaves between nape and collar) are closed."""
    if collar:
        f = restore_collar(f)
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
                    # paint the gap smoothly from its surroundings (nearest-pixel copying made a
                    # patchwork of skin/vest/shirt colours in the collar)
                    import cv2
                    rgb8 = np.clip(c[:, :, :3], 0, 255).astype(np.uint8)
                    painted = cv2.inpaint(rgb8, hm.astype(np.uint8) * 255, 4, cv2.INPAINT_TELEA)
                    c[hm, :3] = painted[hm]
                    c[hm, 3] = 255
                    solid |= hm
    edge = solid & (ndimage.distance_transform_edt(solid) <= 1.5)
    c[:, :, 3] = np.where(solid, np.where(edge, np.maximum(f[:, :, 3], 0), 255), 0)
    if not aa:
        return c
    # Anti-aliased silhouette. The clean-up keeps a pixel or drops it, which leaves stair-steps
    # along slanted edges (upper arm, nape). Soften only the alpha of the outermost pixels with a
    # small blur of the shape: same outline position, no colour change, no new solid pixels.
    A = c[:, :, 3] / 255.0
    As = ndimage.gaussian_filter(A, 0.7)
    band = ndimage.binary_dilation(solid) & ~ndimage.binary_erosion(solid)
    outer = band & ~solid                       # one pixel outside: faint coverage only
    newA = A.copy()
    newA[band & solid] = np.minimum(A[band & solid], np.maximum(As[band & solid] * 1.35, 0.55))
    newA[outer] = np.clip(As[outer] * 0.6, 0, 0.35)
    if outer.any():
        _, (iy, ix) = ndimage.distance_transform_edt(~solid, return_indices=True)
        c[outer, :3] = c[iy[outer], ix[outer], :3]
    c[:, :, 3] = newA * 255
    return c

if __name__ == "__main__":
    sheet = np.array(Image.open(sys.argv[1]).convert("RGBA")).astype(np.float32)
    out = sheet.copy()
    for i in range(sheet.shape[1] // SRC):
        out[:, i * SRC:(i + 1) * SRC] = clean_soft(sheet[:, i * SRC:(i + 1) * SRC],
                                                   collar="--no-collar" not in sys.argv)
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(sys.argv[2])
