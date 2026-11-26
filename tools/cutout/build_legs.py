"""Side legs: thigh = the front sheet's thigh piece (the side sheet has none);
lower leg = the side sheet's navy knee/shin piece tucked into the boot cuff, as one rigid piece."""
import json, numpy as np
from PIL import Image
from scipy import ndimage
R = Image.open("right_alpha.png"); F = Image.open("front_alpha.png")
def clean(img):
    a = np.array(img); lab, n = ndimage.label(a[:, :, 3] > 100)
    sz = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
    a[~ndimage.binary_dilation(lab == (np.argmax(sz) + 1), iterations=2)] = 0
    ys, xs = np.nonzero(a[:, :, 3]); return Image.fromarray(a[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
joints = {}
thigh = clean(F.crop((122, 469, 236, 704)))
thigh.save("thigh_side.png")
for side, shin_box, boot_box in (("near", (75, 714, 192, 846), (68, 839, 226, 1017)),
                                 ("far", (246, 701, 361, 845), (244, 837, 408, 1016))):
    shin = clean(R.crop(shin_box)); boot = clean(R.crop(boot_box))
    sa = np.array(shin)[:, :, 3] > 100; ba = np.array(boot)[:, :, 3] > 100
    def rc(m, y): xs = np.nonzero(m[int(y)])[0]; return xs.mean()
    shin_bot_x = rc(sa, shin.height - 8); boot_top_x = rc(ba, 8)
    tuck = 22                                        # trouser bottom fills the cuff opening
    W = max(shin.width, boot.width) + 60
    Hh = shin.height + boot.height - tuck
    c = Image.new("RGBA", (W, Hh), (0, 0, 0, 0))
    bx = 30; sx = int(round(bx + boot_top_x - shin_bot_x))
    c.alpha_composite(boot, (bx, shin.height - tuck)); c.alpha_composite(shin, (sx, 0))   # trouser over the cuff opening
    c.save(f"lower_{side}.png")
    by0 = shin.height - tuck
    ys, xs = np.nonzero(ba); bot = ys.max(); low = ys >= bot - 5
    joints[f"boot_{side}.knee"] = [sx + rc(sa, 14), 14]
    joints[f"boot_{side}.ankle"] = [bx + rc(ba, int(0.70 * boot.height)), by0 + int(0.70 * boot.height)]
    joints[f"boot_{side}.heel"] = [bx + xs[low].min(), by0 + bot]
    joints[f"boot_{side}.toe"] = [bx + xs[low].max(), by0 + bot]
json.dump({k: [float(v[0]), float(v[1])] for k, v in joints.items()}, open("leg_joints.json", "w"), indent=1)
print(joints, thigh.size)
