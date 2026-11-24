"""Give every walk frame the same dark outline as the approved drawing, where Sprixen left it out.

Sprixen's walk frames draw the outer line only in places: about half of the edge pixels are dark,
against ~85% in the approved drawing, so a cheek, a sleeve or the side of a boot can end in bare
colour against the background. This step inks the outer edge (the silhouette and the edges of the
gaps between arm and body or between the legs) with the approved drawing's line colour:
  - only pixels within ~2.5px of the edge, fading smoothly to nothing (anti-aliased, no pixel look),
  - only where the pixel is lighter than the line already (existing lines are left exactly as drawn),
  - alpha and every pixel further inside are untouched, so shapes, motion and colours stay the same.
Works on a 256px-frame sheet (before the downscale).

usage: python3 ink_outline.py <sheet.png> <base.png> <out.png>
"""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage

SRC = 256
import os
WEIGHT = float(os.environ.get("OUTLINE_WEIGHT", "1"))   # line thickness (config style.outline_weight)
FULL, FADE = 1.6 * WEIGHT, 3.0 * WEIGHT    # fully inked up to FULL px from the edge, nothing past FADE px


def line_colour(base):
    s = base[:, :, 3] > 128
    d = ndimage.distance_transform_edt(s)
    lum = base[:, :, :3].mean(2)
    m = s & (d <= 2.5) & (lum < 100)
    return np.median(base[m][:, :3], 0), float(np.median(lum[m]))


def ink(f, col, col_l):
    a = f[:, :, 3]
    # the line follows a smoothed version of the silhouette, so ragged half see-through edge
    # pixels (hair tips, nape) don't turn into a row of dark dashes
    solid = ndimage.gaussian_filter(a / 255.0, 1.0) > 0.5
    d = ndimage.distance_transform_edt(solid)
    w = np.clip((FADE - d) / (FADE - FULL), 0, 1)
    w = w * w * (3 - 2 * w)
    w[~(a > 0)] = 0
    # semi-transparent rim pixels (outside the solid shape) take the line colour fully
    rim = (a > 0) & ~solid
    w[rim] = np.clip(a[rim] / 255.0 * 1.5, 0, 1)
    rgb = f[:, :, :3]
    lum = rgb.mean(2)
    need = np.clip((lum - col_l) / 60.0, 0, 1)          # already as dark as a line -> unchanged
    # eyes: in the 3/4 view the far eye sits on the face's outline; its white must stay white.
    # Very light pixels in the head (the top 21% of the figure, above the chin) are never inked.
    ys = np.where(solid.any(1))[0]
    if len(ys):
        head = np.zeros_like(solid)
        head[:ys.min() + int(0.21 * (ys.max() - ys.min()))] = True
        need[head & (rgb.min(2) > 175)] = 0
    k = (w * need)[:, :, None]
    out = f.copy()
    out[:, :, :3] = rgb * (1 - k) + col[None, None, :] * k
    return out, float((w * need > 0.5).sum())


def main():
    sheet = np.array(Image.open(sys.argv[1]).convert("RGBA")).astype(np.float32)
    base = np.array(Image.open(sys.argv[2]).convert("RGBA")).astype(np.float32)
    col, col_l = line_colour(base)
    out = sheet.copy()
    inked, face_hits = [], []
    for i in range(sheet.shape[1] // SRC):
        before = sheet[:, i * SRC:(i + 1) * SRC]
        out[:, i * SRC:(i + 1) * SRC], n = ink(before, col, col_l)
        inked.append(int(n))
        # check: the ink must never turn light details of the face (eye whites, highlights) dark
        after = out[:, i * SRC:(i + 1) * SRC]
        s = before[..., 3] > 128
        ys = np.where(s.any(1))[0]
        band = np.zeros_like(s)
        band[ys.min():ys.min() + int(0.21 * (ys.max() - ys.min()))] = True
        hit = band & s & (before[..., :3].min(2) > 175) & (after[..., :3].mean(2) < before[..., :3].mean(2) - 40)
        face_hits.append(int(hit.sum()))
    if max(face_hits) > 0:
        print(f"FAIL: outline ink darkened light face pixels (eye whites) in frames: "
              f"{[i for i, v in enumerate(face_hits) if v]}")
        sys.exit(1)
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(sys.argv[3])
    print(f"{sys.argv[1]}: outline inked with {tuple(int(c) for c in col)}; px per frame {min(inked)}-{max(inked)}")


if __name__ == "__main__":
    main()
