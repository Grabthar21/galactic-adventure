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
    # The approved drawing shows the white collar behind the neck in every pose. Sprixen sometimes
    # erased it (the background shows through there in some frames and not others, so it flashes).
    # Rebuild it the same way in every frame: the notch between nape and shoulder is filled up to
    # the collar's height above the shirt, in the shirt's own white (never the background colour);
    # greyish/lavender collar pixels that Sprixen blended with its backdrop get the same white.
    rgb = f[:, :, :3]
    shirt = body & (rgb.min(2) > 175) & (rgb[:, :, 0] >= rgb[:, :, 2] - 4)
    if not shirt.any():
        return f
    dist_shirt, (iy, ix) = ndimage.distance_transform_edt(~shirt, return_indices=True)
    collar_h = 0.035 * h                                   # ~ collar height in the approved drawing
    fill = notch & (dist_shirt <= collar_h)
    sat = rgb.max(2) - rgb.min(2)
    dirty = body & band & (dist_shirt <= 3) & ~shirt & (rgb.min(2) > 120) & (sat < 45) \
        & (rgb[:, :, 2] >= rgb[:, :, 0] - 6) & ndimage.binary_dilation(notch | fill, iterations=3)
    tgt = fill | dirty
    if tgt.any():
        col = rgb[iy, ix]                                  # nearest shirt colour
        col = np.stack([ndimage.gaussian_filter(col[..., c], 1.2) for c in range(3)], -1)
        out[tgt, :3] = col[tgt] * 0.96                     # a touch of collar shade
        out[tgt, 3] = 255
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

def clean_gentle(f):
    """Sprixen-style clean-up that keeps Sprixen's own outline shape and anti-aliasing.
    The earlier clean-up decided pixel by pixel whether to keep an edge pixel, and peeled light
    grey pixels off the edge; on the white sleeves and collar (whose shading IS light grey) that
    carved dents and slivers that changed from frame to frame. Here the shape is Sprixen's alpha:
      - faint leftovers of the old backdrop (alpha < 60 and cool/light) are dropped,
      - edge pixels keep their alpha but take the colour of the nearest solid pixel, so no backdrop
        colour (white/lavender) is blended into the edge,
      - tiny enclosed holes (<= 12 px) are filled; the far-arm see-through is made solid.
    """
    a = f[:, :, 3].copy()
    rgb = f[:, :, :3]
    cool = (rgb.min(2) > 140) & (rgb[:, :, 0] < np.maximum(rgb[:, :, 1], rgb[:, :, 2]) - 2)
    a[(a < 60) & cool] = 0
    a[a < 8] = 0
    solid = a >= 200
    holes, n = ndimage.label(ndimage.binary_fill_holes(solid) & ~solid)
    for k in range(1, n + 1):
        hm = holes == k
        if hm.sum() <= 12:
            solid |= hm
            a[hm] = 255
    # enclosed gaps in the head/chest (the collar Sprixen made see-through between nape and vest):
    # painted in smoothly from their surroundings, so the background never flashes through.
    ys = np.where(solid.any(1))[0]
    if len(ys):
        y0, y1 = ys.min(), ys.max()
        holes, n = ndimage.label(ndimage.binary_fill_holes(a >= 60) & ~(a >= 200))
        for k in range(1, n + 1):
            hm = holes == k
            if hm.sum() <= 220 and np.where(hm)[0].mean() < y0 + 0.45 * (y1 - y0):
                import cv2
                yy, xx = np.where(hm)
                ya, yb = max(yy.min() - 6, 0), yy.max() + 7
                xa, xb = max(xx.min() - 6, 0), xx.max() + 7
                known = (a[ya:yb, xa:xb] >= 200) & ~hm[ya:yb, xa:xb]
                # a see-through collar is filled in the collar's own white (as in the frames where
                # Sprixen kept it), not a blend with the hair and vest around it
                lightk = known & (rgb[ya:yb, xa:xb].min(2) > 170)
                ring = ndimage.binary_dilation(hm[ya:yb, xa:xb], iterations=2) & known
                # the only thing that sits in this gap in the approved drawing is the white collar
                if lightk.sum() >= 6:
                    known = lightk
                _, (iy, ix) = ndimage.distance_transform_edt(~known, return_indices=True)
                loc = rgb[ya:yb, xa:xb][iy, ix]            # nearest solid colour everywhere
                rgb8 = np.clip(loc, 0, 255).astype(np.uint8)
                painted = cv2.inpaint(rgb8, hm[ya:yb, xa:xb].astype(np.uint8) * 255, 3, cv2.INPAINT_TELEA)
                rgb = rgb.copy()
                sub = rgb[ya:yb, xa:xb]
                sub[hm[ya:yb, xa:xb]] = painted[hm[ya:yb, xa:xb]]
                a[hm] = 255
                solid |= hm
    # inside the body (2+ px from the outside) everything is solid: the far arm is see-through in Sprixen
    inner = ndimage.binary_erosion(a > 60, iterations=2)
    # half see-through pale pixels (Sprixen's backdrop showing between hair tufts or limbs) are not
    # made solid: near the outside they are cleared, deeper in they take the surrounding colour
    sat0 = rgb.max(2) - rgb.min(2)
    pale_semi = inner & (a < 200) & (rgb.min(2) > 150) & (sat0 < 50)
    if pale_semi.any():
        near_out = ndimage.binary_dilation(a < 60, iterations=3)
        a[pale_semi & near_out] = 0
        deep = pale_semi & ~near_out
        if deep.any():
            good = (a >= 200) & ~pale_semi
            _, (gy, gx) = ndimage.distance_transform_edt(~good, return_indices=True)
            rgb = rgb.copy()
            rgb[deep] = rgb[gy[deep], gx[deep]]
        inner &= ~(pale_semi & near_out)
    a[inner] = 255
    # pale bluish-white patches next to the outside are Sprixen's old backdrop showing in the gaps
    # between arm and body (the shirt is a warm white, never bluish): cleared
    outside = a == 0
    # (low colour only: the neckerchief's light-blue highlights are part of the drawing)
    coolw = (a > 0) & (rgb.min(2) > 150) & (rgb[:, :, 2] >= rgb[:, :, 0] + 3) \
        & (rgb.max(2) - rgb.min(2) < 30)
    lab, nl = ndimage.label(coolw)
    if nl:
        near_out = ndimage.binary_dilation(outside, iterations=3)
        solid_wo = (a >= 200) & ~coolw
        gaps = ndimage.binary_fill_holes(solid_wo) & ~solid_wo        # enclosed gaps (arm/body, legs)
        ysb = np.where((a >= 200).any(1))[0]
        head_end = ysb.min() + int(0.30 * (ysb.max() - ysb.min())) if len(ysb) else 0
        for k in range(1, nl + 1):
            comp = lab == k
            if np.where(comp)[0].mean() < head_end:
                continue                                              # eyes etc.
            if (comp & near_out).any() or ((comp & gaps).sum() >= 0.6 * comp.sum() and comp.sum() >= 40):
                a[comp] = 0          # small enclosed bits are highlights (neckerchief), kept
    # below the belt nothing in the outfit is white (gloves, trousers, boots; the buckle is gold):
    # light, colourless pixels there are the old backdrop between arm, hip and legs -> cleared
    navy = (a >= 200) & (rgb[:, :, 2] > rgb[:, :, 0] + 8) & (rgb[:, :, 0] < 110)
    ysb = np.where((a >= 200).any(1))[0]
    rows = np.where(navy.sum(1) > 20)[0]                     # trousers (wide), not the neckerchief
    if len(ysb):
        rows = rows[rows > ysb.min() + 0.42 * (ysb.max() - ysb.min())]
    if len(rows):
        belt = rows.min()
        sat = rgb.max(2) - rgb.min(2)
        pale = (a > 0) & (rgb.min(2) > 130) & (sat < 45)
        pale[:belt] = False
        lab, nl = ndimage.label(pale)
        near_out = ndimage.binary_dilation(a == 0, iterations=3)
        for k in range(1, nl + 1):
            comp = lab == k
            if (comp & near_out).any() or comp.sum() >= 40:
                a[comp] = 0          # backdrop open to the outside, or a real gap between arm and hip / legs
            else:
                # a sliver of backdrop where arm and hip (or the legs) touch: take the colour of
                # what is around it, so it neither shows white nor turns into a see-through speck
                keep = (a >= 200) & ~pale
                _, (iy, ix) = ndimage.distance_transform_edt(~keep, return_indices=True)
                rgb = rgb.copy()
                rgb[comp] = rgb[iy[comp], ix[comp]]
                a[comp] = 255
    # thin wisps on the outline (1-2 px strands of half see-through hair or collar behind the neck):
    # they come and go between frames and turn into dark hooks once the outline is inked. Anything
    # an opening with a 3x3 square removes, in pieces under 30 px, is dropped.
    body = a > 60
    opened = ndimage.binary_opening(body, structure=np.ones((3, 3)))
    thin = body & ~opened
    lab, nl = ndimage.label(thin)
    if nl:
        sizes = ndimage.sum(thin, lab, range(1, nl + 1))
        drop = np.isin(lab, 1 + np.where(sizes < 30)[0])
        a[drop] = 0
    # small light pockets caught between hair tips (where the hair meets the collar): once inked
    # they read as little loops. Pockets of <= 14 px whose border is mostly hair take the hair colour.
    body = a > 60
    hair = body & (rgb[:, :, 0] > rgb[:, :, 2] + 25) & (rgb.mean(2) < 150) & (rgb[:, :, 0] < 190)
    lightp = body & (rgb.min(2) > 140)
    lab, nl = ndimage.label(lightp)
    if nl:
        sizes = ndimage.sum(lightp, lab, range(1, nl + 1))
        _, (hy, hx) = ndimage.distance_transform_edt(~hair, return_indices=True)
        rgb = rgb.copy()
        ysb = np.where((a >= 200).any(1))[0]
        eye_end = ysb.min() + int(0.21 * (ysb.max() - ysb.min())) if len(ysb) else 0
        for k in np.where(sizes <= 40)[0] + 1:
            comp = lab == k
            if np.where(comp)[0].mean() < eye_end:
                continue          # eye whites sit between dark lines too: never recoloured
            if not (ndimage.binary_dilation(comp, iterations=3) & ~body).any():
                continue          # only pockets on the outline (hair tips); inside the body it's the shirt
            ring = ndimage.binary_dilation(comp, iterations=2) & ~comp
            hair_or_out = (ring & (hair | ~body)).sum()
            if ring.sum() and (ring & hair).sum() >= 0.25 * ring.sum() and hair_or_out >= 0.7 * ring.sum():
                rgb[comp] = rgb[hy[comp], hx[comp]]
    # pixels Sprixen left half see-through inside the body (mostly the white collar behind the neck)
    # carry a muddy blend with its backdrop; greyish ones next to the shirt take the shirt's white,
    # so the collar looks the same in every frame
    a0 = f[:, :, 3]
    semi = (a0 >= 20) & (a0 < 230) & (a >= 245)
    sat = rgb.max(2) - rgb.min(2)
    lightop = (a0 >= 230) & (rgb.min(2) > 170)
    if semi.any() and lightop.any():
        dl, (ly, lx) = ndimage.distance_transform_edt(~lightop, return_indices=True)
        ysb = np.where(a.max(1) >= 200)[0]
        collar_band = np.zeros_like(semi)
        if len(ysb):
            hh = ysb.max() - ysb.min()
            collar_band[ysb.min() + int(.22 * hh):ysb.min() + int(.40 * hh)] = True
        fix = semi & (sat < 45) & (dl <= 12) & collar_band
        rgb = rgb.copy()
        rgb[fix] = rgb[ly[fix], lx[fix]]
    _, (iy, ix) = ndimage.distance_transform_edt(~(a >= 245), return_indices=True)
    out = f.copy()
    out[:, :, :3] = rgb
    edge = (a > 0) & (a < 245)
    # only edge pixels the old backdrop lightened take the inner colour; Sprixen's dark line stays
    lighter = rgb.mean(2) > rgb[iy, ix].mean(2) + 15
    edge &= lighter
    out[edge, :3] = rgb[iy[edge], ix[edge]]
    out[:, :, 3] = a
    out[a == 0, :3] = 0
    return out


if __name__ == "__main__":
    sheet = np.array(Image.open(sys.argv[1]).convert("RGBA")).astype(np.float32)
    out = sheet.copy()
    for i in range(sheet.shape[1] // SRC):
        fr = sheet[:, i * SRC:(i + 1) * SRC]
        out[:, i * SRC:(i + 1) * SRC] = clean_gentle(fr) if "--gentle" in sys.argv else \
            clean_soft(fr, collar="--no-collar" not in sys.argv)
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(sys.argv[2])
