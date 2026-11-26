"""Make a hairstyle's base drawing: the approved body with the head from a hairstyle drawing.

Sprixen redraws the whole character for a new hairstyle, a little shifted or scaled. To keep
everything else identical, the hairstyle drawing is aligned to the approved drawing by its
shoulders/torso (which don't change), and only its head (above the shoulder line found by
head_rows.py) is placed on the approved body, blended over a few rows at the neck.
The face itself (eyes to chin) stays the approved one: Sprixen redraws the face slightly
differently each time, and a new haircut shouldn't change who the character is. Skip that for
back views (no face) by passing --no-face.
usage: python3 compose_style.py <approved_base.png> <style_drawing.png> <out.png> [--no-face]"""
import sys
import cv2
import numpy as np
from PIL import Image
from head_rows import head_rows
from lock_head import clean_body

SRC = 256
BLEND = 4


def gray(rgba):
    a = rgba[:, :, 3:4] / 255.0
    g = cv2.cvtColor(rgba[:, :, :3].astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
    return (g[:, :, None] * a + 128 * (1 - a))[:, :, 0].astype(np.float32)


def main():
    base = clean_body(np.array(Image.open(sys.argv[1]).convert("RGBA")).astype(np.float32))
    style = clean_body(np.array(Image.open(sys.argv[2]).convert("RGBA")).astype(np.float32))
    prof = head_rows(sys.argv[1])
    cut = prof["CHIN_CUT"]
    # torso band of the approved drawing (shoulders to mid-chest)
    t0, t1 = cut + 2, cut + 62
    cols = np.where(base[t0:t1, :, 3].max(0) > 40)[0]
    tmpl = gray(base[t0:t1, cols.min():cols.max() + 1])
    g = gray(style)
    best = None
    for k in np.arange(0.88, 1.13, 0.005):
        t = cv2.resize(tmpl, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
        r = cv2.matchTemplate(g, t, cv2.TM_CCOEFF_NORMED)
        _, mx, _, loc = cv2.minMaxLoc(r)
        if best is None or mx > best[0]:
            best = (mx, k, loc)
    score, k, (lx, ly) = best
    # style pixel (x, y) corresponds to base pixel ((x - lx)/k + cols.min(), (y - ly)/k + t0)
    M = np.float32([[1 / k, 0, cols.min() - lx / k], [0, 1 / k, t0 - ly / k]])
    pm = style.copy()
    pm[:, :, :3] *= pm[:, :, 3:4] / 255.0
    al = cv2.warpAffine(pm, M, (SRC, SRC), flags=cv2.INTER_CUBIC, borderValue=0)
    al = np.clip(al, 0, 255)
    a = al[:, :, 3:4] / 255.0
    al[:, :, :3] = np.where(a > 0, al[:, :, :3] / np.maximum(a, 1e-6), 0)
    out = base.copy()
    out[:cut] = al[:cut]                                   # new head (and nothing else above the shoulders)
    for i in range(BLEND):                                 # soften the join at the neck
        w = 1 - (i + 1) / (BLEND + 1)
        y = cut + i
        sa = al[y, :, 3:4] / 255.0 * w
        out[y, :, :3] = al[y, :, :3] * sa + out[y, :, :3] * (1 - sa)
        out[y, :, 3] = np.maximum(out[y, :, 3], al[y, :, 3] * w)
    face_note = ""
    if "--no-face" not in sys.argv:
        face_note = keep_face(base, out, prof)
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(sys.argv[3])
    print(f"aligned by torso: scale {1/k:.3f}, match {score:.3f}; head above row {cut} from the style drawing{face_note}")


def keep_face(base, out, prof):
    """Put the approved face (eyes to chin, inside the face outline) back over the new head."""
    from scipy import ndimage
    from masks import lab_parts, ramp
    l, chroma, hue = lab_parts(base)
    skin = (ramp(l, 54, 62) * ramp(chroma, 8, 14) * (1 - ramp(chroma, 46, 54))
            * ramp(hue, 36, 44) * (1 - ramp(hue, 74, 82))) > 0.5
    r1 = prof["CHIN_CUT"]
    # start below the approved drawing's bangs: first row (from the top of the face band) where
    # hair-coloured pixels no longer cover much of the face's width
    hairish = (l < 52) & (l > 14) & (chroma > 8) & (hue > 28) & (hue < 86) & (base[:, :, 3] > 40)
    r0 = prof["FACE"][0] - 6
    rows_skin = np.where(skin[r0:r1].any(1))[0]
    if len(rows_skin):
        xs_s = np.where(skin[r0:r1].any(0))[0]
        xa, xb = xs_s.min(), xs_s.max() + 1
        for y in range(r0, r1):
            frac = hairish[y, xa:xb].mean()
            if frac < 0.22 and skin[y, xa:xb].mean() > 0.35:
                r0 = y + 1
                break
    band = np.zeros_like(skin)
    band[r0:r1] = True
    face = ndimage.binary_fill_holes(ndimage.binary_closing(skin & band, iterations=3)) & band
    face = ndimage.binary_dilation(face, iterations=1) & (base[:, :, 3] > 40)   # include its outline
    if face.sum() < 50:
        return " (no face found, kept the drawing's)"
    ys, xs = np.where(face)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    # fine-align the approved face onto the new head (the heads may sit a pixel or two apart)
    tmpl = gray(base[y0:y1, x0:x1])
    g = gray(out)
    best, by, bx = -2, 0, 0
    for dy in range(-5, 6):
        for dx in range(-5, 6):
            yy, xx = y0 + dy, x0 + dx
            if yy < 0 or xx < 0 or yy + tmpl.shape[0] > SRC or xx + tmpl.shape[1] > SRC:
                continue
            win = g[yy:yy + tmpl.shape[0], xx:xx + tmpl.shape[1]]
            m = face[y0:y1, x0:x1]
            c = np.corrcoef(win[m], tmpl[m])[0, 1]
            if c > best:
                best, by, bx = c, dy, dx
    # feathered paste (soft 2px edge so the join doesn't show)
    d = ndimage.distance_transform_edt(face)
    w = np.clip(d / 2.0, 0, 1)[y0:y1, x0:x1, None]
    dst = out[y0 + by:y1 + by, x0 + bx:x1 + bx]
    src = base[y0:y1, x0:x1]
    dst[:, :, :3] = src[:, :, :3] * w + dst[:, :, :3] * (1 - w)
    dst[:, :, 3:4] = np.maximum(dst[:, :, 3:4], src[:, :, 3:4] * w)
    return f"; approved face kept (offset {bx},{by}, match {best:.2f})"


if __name__ == "__main__":
    main()
