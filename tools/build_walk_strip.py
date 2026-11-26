"""Scale a generated side-walk strip into the game's 98x148 cells.
Every frame gets the SAME scale and the SAME offset (head over the cell centre, ground
line on the cell floor), so the motion inside the frames is exactly what the rig produced.
No per-frame re-alignment, so no jitter."""
import json, sys
import numpy as np
from PIL import Image

name = sys.argv[1] if len(sys.argv) > 1 else "arthur"
sheet = sys.argv[2] if len(sys.argv) > 2 else f"source_art/{name}_sheet.png"
ns = {}
exec(open("slice_character_sheet.py").read().split("TARGET=")[0], ns)   # reuse extract()
rows = ns["extract"](sheet)
ref = np.median([f.shape[0] for f in rows[2]])
TARGET, S = 268.0, 0.5
k = TARGET / ref * S
CW, CH = 98, 148
meta = json.load(open(f"{name}_side_walk_src.json"))
strip = Image.open(f"{name}_side_walk_src.png")
n, fw, fh = meta["count"], meta["frame_w"], meta["frame_h"]
ox = CW / 2 - meta["head_x"] * k
oy = (CH - 2) - meta["ground_y"] * k
out = Image.new("RGBA", (CW * n, CH), (0, 0, 0, 0))
for i in range(n):
    f = strip.crop((i * fw, 0, (i + 1) * fw, fh))
    # sub-pixel placement via an affine transform (identical for every frame)
    g = f.transform((CW, CH), Image.AFFINE, (1 / k, 0, -ox / k, 0, 1 / k, -oy / k), resample=Image.BICUBIC)
    # downscale quality: render at 4x then reduce
    big = f.transform((CW * 4, CH * 4), Image.AFFINE, (1 / (k * 4), 0, -ox / k, 0, 1 / (k * 4), -oy / k), resample=Image.BICUBIC)
    g = big.resize((CW, CH), Image.LANCZOS)
    out.alpha_composite(g, (i * CW, 0))
out.save(f"{name}_side_walk.png")
travel_cell = meta["cycle_travel_src"] * k
print("saved", out.size, "scale %.3f" % k, "body travel per cycle in cell px %.1f" % travel_cell)
json.dump({"frames": n, "cycle_travel_cell_px": travel_cell}, open(f"{name}_side_walk.json", "w"))
