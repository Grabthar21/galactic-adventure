"""Match Arthur's skin colour to the approved Version 1 drawing.

Sprixen drew the front/back views with slightly pinker, less golden skin. This shifts only
skin-coloured pixels (in CIE Lab: light, moderately saturated, orange hue) so their average
colour matches the reference, keeping every pixel's light/dark shading. Hair (darker), gold
buckles (yellower), the cream shirt (unsaturated) and leather (dark) are outside the skin
range and untouched; pixels near the edge of the range are blended so there are no seams.
usage: python3 skin_match.py <reference_base.png> <in.png> <out.png>"""
import sys
import cv2
import numpy as np
from PIL import Image


def lab(rgba):
    return cv2.cvtColor(rgba[:, :, :3].astype(np.uint8), cv2.COLOR_RGB2LAB).astype(np.float32)


def skin_weight(L, A, B, alpha):
    # OpenCV 8-bit Lab: L 0-255, a/b offset by 128
    l = L * 100 / 255
    a, b = A - 128, B - 128
    chroma = np.hypot(a, b)
    hue = np.degrees(np.arctan2(b, a))
    def ramp(x, lo, hi):            # 0 below lo, 1 above hi
        return np.clip((x - lo) / (hi - lo), 0, 1)
    w = ramp(l, 54, 62)                                   # light enough (hair is darker)
    w *= ramp(chroma, 8, 14) * (1 - ramp(chroma, 46, 54))  # skin saturation (not shirt, not gold)
    w *= ramp(hue, 38, 46) * (1 - ramp(hue, 72, 80))      # orange hue (gold is yellower)
    w *= alpha > 128
    return w


def stats(img):
    L, A, B = np.moveaxis(lab(img), 2, 0)
    w = skin_weight(L, A, B, img[:, :, 3])
    sel = w > 0.9
    return np.array([np.median(L[sel]), np.median(A[sel]), np.median(B[sel])]), int(sel.sum())


def main():
    ref = np.array(Image.open(sys.argv[1]).convert("RGBA")).astype(np.float32)
    img = np.array(Image.open(sys.argv[2]).convert("RGBA")).astype(np.float32)
    rs, rn = stats(ref)
    ss, sn = stats(img)
    delta = rs - ss
    delta[0] *= 0.5                       # lightness: only half-way (shading differs by view)
    lb = lab(img)
    w = skin_weight(lb[:, :, 0], lb[:, :, 1], lb[:, :, 2], img[:, :, 3])[:, :, None]
    lb2 = np.clip(lb + w * delta[None, None, :], 0, 255)
    rgb = cv2.cvtColor(lb2.astype(np.uint8), cv2.COLOR_LAB2RGB).astype(np.float32)
    # convert only where we changed something, to avoid Lab round-trip drift elsewhere
    img[:, :, :3] = np.where(w > 0.001, rgb, img[:, :, :3])
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(sys.argv[3])
    print(f"{sys.argv[2]}: skin Lab {np.round(ss,1)} -> ref {np.round(rs,1)} (shift {np.round(delta,1)}; {sn} skin px)")


if __name__ == "__main__":
    main()
