"""Turn the Sprixen idle sheet (16 x 256px frames) into art/<hero>_side_idle.png.

Sprixen's frames 3-7 render the whole character ~5% larger (a "swell", not a breath),
so each frame is rescaled about its feet so the height change is cut to a quarter:
that keeps a soft breathing rise of ~2px in game and removes the pulsing.
Then frames are scaled to the in-game hero height and placed in 98x148 cells,
feet on the cell's bottom row, so they line up with the walk strip.

usage: python3 build_idle_strip.py <sheet.png> <out.png> [target_height=133]
"""
import sys
import numpy as np
from PIL import Image

SRC_CELL = 256
CELL_W, CELL_H = 98, 148
FOOT_Y = 147          # bottom row of the feet in the game cells
CENTER_X = 46         # body centre in the game cells (matches the walk strip)
KEEP = 0.25           # fraction of Sprixen's size change to keep


def bbox(a):
    ys, xs = np.where(a[:, :, 3] > 40)
    return xs.min(), ys.min(), xs.max(), ys.max()


def main():
    sheet = Image.open(sys.argv[1]).convert("RGBA")
    out_path = sys.argv[2]
    target_h = float(sys.argv[3]) if len(sys.argv) > 3 else 133.0
    n = sheet.width // SRC_CELL
    frames = [sheet.crop((i * SRC_CELL, 0, (i + 1) * SRC_CELL, SRC_CELL)) for i in range(n)]
    boxes = [bbox(np.array(f)) for f in frames]
    heights = np.array([b[3] - b[1] for b in boxes], float)
    ref_h = float(np.median(heights))
    # one global scale so the median frame is target_h tall
    base_scale = target_h / ref_h
    strip = Image.new("RGBA", (CELL_W * n, CELL_H), (0, 0, 0, 0))
    for i, (f, b, h) in enumerate(zip(frames, boxes, heights)):
        want = ref_h + KEEP * (h - ref_h)
        s = base_scale * want / h
        x0, y0, x1, y1 = b
        part = f.crop((x0, y0, x1 + 1, y1 + 1))
        w2 = max(1, round(part.width * s))
        h2 = max(1, round(part.height * s))
        # resample at 2x then halve for clean edges
        part = part.resize((w2 * 2, h2 * 2), Image.LANCZOS).resize((w2, h2), Image.LANCZOS)
        # horizontal anchor: feet span centre, so the planted feet never slide
        a = np.array(f)[:, :, 3]
        fy = np.where(a[y1 - 8:y1 + 1] > 40)[1]
        feet_cx = ((fy.min() + fy.max()) / 2.0 - x0) * s
        px = round(i * CELL_W + CENTER_X - feet_cx)
        py = FOOT_Y + 1 - h2
        strip.alpha_composite(part, (px, py))
    strip.save(out_path)
    print(f"{n} frames, median src height {ref_h:.0f}px, scale {base_scale:.3f} -> {out_path}")


if __name__ == "__main__":
    main()
