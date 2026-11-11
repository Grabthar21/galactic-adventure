"""Shared downscale for game strips: premultiplied-alpha area averaging.
Lanczos rings at hard edges (faint specks + light halo just outside the outline);
area averaging in premultiplied space can't overshoot, so edges stay clean.
Alpha below FLOOR (invisible dust) is dropped."""
import numpy as np
from PIL import Image

FLOOR = 24


def downscale(img, w, h):
    small = img.convert("RGBa").resize((w, h), Image.BOX).convert("RGBA")
    a = np.array(small)
    a[a[:, :, 3] < FLOOR] = 0
    return Image.fromarray(a)


def defringe(img, lighter=40, passes=2):
    """Final game-size pass: an outer edge pixel that is clearly lighter than the solid
    pixel just inside it is a light rim outside the dark outline -> take the inside colour."""
    from scipy import ndimage
    a = np.array(img.convert("RGBA")).astype(np.int32)
    for _ in range(passes):
        alpha = a[:, :, 3]
        m = alpha > 0
        solid = alpha >= 128
        edge = m & ndimage.binary_dilation(~m)
        inner = solid & ~ndimage.binary_dilation(~m, iterations=2)
        if not inner.any():
            break
        _, (iy, ix) = ndimage.distance_transform_edt(~inner, return_indices=True)
        lum = a[:, :, :3].mean(2)
        rgb = a[:, :, :3]
        bad = edge & (lum - lum[iy, ix] > lighter) & (lum > 150)
        # cool / greenish light pixels near the outside are background-removal leftovers
        # (inside the body, white shirt next to the navy neckerchief is legitimately bluish-grey)
        near_out = ndimage.binary_dilation(~m, iterations=3)
        bad |= m & near_out & (rgb.min(2) > 140) & (rgb[:, :, 0] < np.maximum(rgb[:, :, 1], rgb[:, :, 2]) - 6)
        a[bad, :3] = a[iy[bad], ix[bad], :3]
    return Image.fromarray(a.astype(np.uint8))


def snap_feet(img, cell_w=98, foot_y=147):
    """Shift each cell up/down so its lowest solid row sits exactly on the ground row
    (rounding during scaling can leave a frame floating or sunk by 1px)."""
    a = np.array(img.convert("RGBA"))
    for i in range(a.shape[1] // cell_w):
        c = a[:, i * cell_w:(i + 1) * cell_w]
        rows = np.where((c[:, :, 3] >= 128).any(1))[0]
        if len(rows):
            dy = foot_y - rows.max()
            if dy:
                a[:, i * cell_w:(i + 1) * cell_w] = np.roll(c, dy, axis=0)
    return Image.fromarray(a)


def fill_pinholes(img, max_px=12):
    """Close tiny see-through pockets fully enclosed by the body (one-frame flicker gaps
    between a forearm and the hip); real gaps like between the legs are much larger."""
    from scipy import ndimage
    a = np.array(img.convert("RGBA")).astype(np.int32)
    solid = a[:, :, 3] >= 128
    holes, n = ndimage.label(ndimage.binary_fill_holes(solid) & ~solid)
    if n:
        _, (iy, ix) = ndimage.distance_transform_edt(~solid, return_indices=True)
        for k in range(1, n + 1):
            hm = holes == k
            if hm.sum() <= max_px:
                a[hm, :3] = a[iy[hm], ix[hm], :3]
                a[hm, 3] = 255
    return Image.fromarray(a.astype(np.uint8))
