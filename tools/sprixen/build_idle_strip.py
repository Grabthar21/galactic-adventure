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
from resample import downscale, defringe, snap_feet, fill_pinholes, remove_specks

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
    import os
    base_scale = target_h / float(os.environ.get("BASE_H", ref_h))   # same rule as the walks
    strip = Image.new("RGBA", (CELL_W * n, CELL_H), (0, 0, 0, 0))
    for i, (f, b, h) in enumerate(zip(frames, boxes, heights)):
        want = ref_h + KEEP * (h - ref_h)
        s = base_scale if "BASE_H" in os.environ else base_scale * want / h
        x0, y0, x1, y1 = b
        part = f.crop((x0, y0, x1 + 1, y1 + 1))
        w2 = max(1, round(part.width * s))
        h2 = max(1, round(part.height * s))
        part = downscale(part, w2, h2)     # premultiplied area average (tools/sprixen/resample.py)
        a = np.array(f)[:, :, 3]
        # torso centre (same anchor as the walk strips, so stopping never shifts him sideways)
        t0, t1 = y0 + 75, y0 + 105
        tx = np.where(a[t0:t1] > 40)[1].mean()
        feet_cx = (tx - x0) * s
        px = round(i * CELL_W + CENTER_X - feet_cx)
        py = FOOT_Y + 1 - h2
        strip.alpha_composite(part, (px, py))
    strip = snap_feet(remove_specks(fill_pinholes(defringe(strip))))
    strip.save(out_path)
    print(f"{n} frames, median src height {ref_h:.0f}px, scale {base_scale:.3f} -> {out_path}")


if __name__ == "__main__":
    main()
