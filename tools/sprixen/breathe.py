"""Make a subtle, seamless breathing idle from ONE approved standing drawing.

Sprixen's idle frames change pose between frames (shoulders/arms jump) and the face/chin
ghosts, so instead the approved drawing itself breathes:
  - everything from the waist down stays perfectly still (feet planted, hands at the hips)
  - between waist and shoulders the body stretches upward a little (the in-breath),
    tapering to zero at the waist
  - shoulders, neck and head lift rigidly with the chest
  - a slow sine cycle with a short rest at the bottom of each breath
usage: python3 breathe.py <base.png> <out_sheet.png> [frames=32] [lift_px=2.4] [profile]
"""
import sys
import cv2
import numpy as np
from PIL import Image

SRC = 256


def main():
    base = np.array(Image.open(sys.argv[1]).convert("RGBA")).astype(np.float32)
    out_path = sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 32
    lift = float(sys.argv[4]) if len(sys.argv) > 4 else 2.4
    a = base[:, :, 3]
    ys = np.where(a.max(1) > 40)[0]
    top, bot = ys.min(), ys.max()
    h = bot - top
    waist = top + 0.53 * h          # belt line: below this nothing moves
    chest = top + 0.36 * h          # shoulders: above this everything lifts rigidly
    # premultiply so resampling can't pull colour from transparent pixels
    pm = base.copy()
    pm[:, :, :3] *= pm[:, :, 3:4] / 255.0
    yy, xx = np.mgrid[0:SRC, 0:SRC].astype(np.float32)
    frames = []
    for i in range(n):
        t = i / n
        # breath curve: smooth in/out, with the lungs resting a little at the bottom
        b = 0.5 - 0.5 * np.cos(2 * np.pi * t)
        b = b ** 1.3
        d = lift * b
        # displacement (upward) per output row
        w = np.clip((waist - yy) / (waist - chest), 0.0, 1.0)
        w = w * w * (3 - 2 * w)      # smoothstep taper from waist to chest
        map_y = (yy + d * w).astype(np.float32)   # sample from lower rows -> content moves up
        out = cv2.remap(np.ascontiguousarray(pm, np.float32), xx, map_y, interpolation=cv2.INTER_CUBIC,
                        borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        out = np.clip(out, 0, 255)
        al = out[:, :, 3:4] / 255.0
        out[:, :, :3] = np.where(al > 0, out[:, :, :3] / np.maximum(al, 1e-6), 0)
        frames.append(np.clip(out, 0, 255).astype(np.uint8))
    sheet = np.concatenate(frames, axis=1)
    Image.fromarray(sheet).save(out_path)
    print(f"{n} frames, lift {lift}px at the shoulders, waist row {waist:.0f}, chest row {chest:.0f}")


if __name__ == "__main__":
    main()
