"""Scale the cut-out walk into 98x148 game cells. Same scale and offset for every frame
(head over the cell centre, ground on the cell floor) so nothing jitters."""
import json, sys
from PIL import Image
import numpy as np
name = sys.argv[1]; target_h = float(sys.argv[2]) if len(sys.argv) > 2 else 134.0
m = json.load(open(f"{name}_cutout_walk_src.json"))
strip = Image.open(f"{name}_cutout_walk_src.png"); stand = Image.open(f"{name}_cutout_stand_src.png")
a = np.array(stand)[:, :, 3]; top = np.nonzero(a.any(1))[0].min()
k = target_h / (m["ground_y"] - top)
CW, CH = 98, 148
ox = CW / 2 - m["head_x"] * k; oy = (CH - 2) - m["ground_y"] * k
def cell(img):
    big = img.transform((CW * 4, CH * 4), Image.AFFINE, (1 / (k * 4), 0, -ox / k, 0, 1 / (k * 4), -oy / k), resample=Image.BICUBIC)
    return big.resize((CW, CH), Image.LANCZOS)
n, fw = m["count"], m["frame_w"]
out = Image.new("RGBA", (CW * n, CH), (0, 0, 0, 0))
for i in range(n):
    out.alpha_composite(cell(strip.crop((i * fw, 0, (i + 1) * fw, m["frame_h"]))), (i * CW, 0))
out.save(f"{name}_side_walk.png"); cell(stand).save(f"{name}_side_idle.png")
travel = m["cycle_travel_src"] * k
print("scale %.3f" % k, "cycle travel cell px %.1f" % travel, "-> walk speed at 20fps/12f: %.0f px/s" % (travel * 0.75 / (n / 20.0)))
