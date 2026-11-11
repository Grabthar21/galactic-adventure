"""Make an armless side torso that keeps the front details (buttons, neckerchief, buckle):
the front torso piece minus its baked-in near arm, laid over the plain side torso piece
(which supplies the back of the vest that the arm was hiding)."""
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
im = Image.open("right_alpha.png")
T1 = im.crop((88, 224, 262, 460)); T2 = im.crop((272, 224, 414, 460))
a1 = np.array(T1).astype(int); H, W = a1.shape[:2]
r, g, b = a1[:, :, 0], a1[:, :, 1], a1[:, :, 2]
light = (r > 200) & (g > 185) & (b > 160)           # sleeve cloth
skin = (r > 200) & (g > 120) & (g < 190) & (b < 150) & (r - b > 60)
poly = Image.new("L", (W, H), 0)
ImageDraw.Draw(poly).polygon([(0, 30), (58, 26), (78, 42), (90, 78), (97, 120), (97, 168), (84, 186), (0, 186)], fill=255)
inpoly = np.array(poly) > 0
arm = inpoly & (light | skin)
arm = ndimage.binary_closing(arm, iterations=2) & inpoly
arm = ndimage.binary_dilation(arm, iterations=3) & inpoly & (a1[:, :, 3] > 0)   # take its outline too
# keep the vest edge: brown pixels stay
brown = (r > 90) & (r < 190) & (g < 120) & (b < 90) & (r - b > 40)
arm &= ~(brown & ~ndimage.binary_dilation(light | skin, iterations=1))
t1 = a1.copy(); t1[arm] = 0
base = Image.new("RGBA", (W + 40, H), (0, 0, 0, 0))
dx = int(np.median(np.nonzero(np.array(T1)[5, :, 3] > 0)[0])) - int(np.median(np.nonzero(np.array(T2)[5, :, 3] > 0)[0]))
base.alpha_composite(T2, (dx + 20, 0))
base.alpha_composite(Image.fromarray(t1.astype(np.uint8)), (20, 0))
arr = np.array(base)
lab, n = ndimage.label(arr[:, :, 3] > 0, structure=np.ones((3, 3)))
sz = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
arr[lab != (np.argmax(sz) + 1)] = 0
# knock out thin leftover outline slivers (1-2 px wide) left from the removed sleeve
solid = ndimage.binary_opening(arr[:, :, 3] > 0, iterations=2)
arr[~ndimage.binary_dilation(solid, iterations=2)] = 0
Image.fromarray(arr).save("torso_built.png")
Image.fromarray((arm * 255).astype(np.uint8)).save("torso_arm_mask.png")
print("collar shift", dx, "size", base.size)
