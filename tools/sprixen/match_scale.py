"""Rescale a Sprixen sheet so the character is drawn at the same scale as its approved
base sprite (Sprixen draws each animation a few % bigger or smaller).
The scale is found by matching the base sprite's head at different sizes against the
frames (OpenCV template matching), then every frame is resized about its feet/centre.
usage: python3 match_scale.py <sheet.png> <base.png> <out.png> <profile side|front|back>"""
import sys
import cv2
import numpy as np
from PIL import Image
from lock_head import PROFILES, SRC

sheet = Image.open(sys.argv[1]).convert("RGBA")
base = np.array(Image.open(sys.argv[2]).convert("RGBA"))
prof = PROFILES[sys.argv[4]]
n = sheet.width // SRC
frames = [np.array(sheet.crop((i * SRC, 0, (i + 1) * SRC, SRC))) for i in range(n)]


def gray_on_grey(rgba):
    a = rgba[:, :, 3:4].astype(np.float32) / 255
    g = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2GRAY).astype(np.float32)
    return (g[:, :, None] * a + 128 * (1 - a))[:, :, 0]


# upper body (head down to the belt): many more distinctive pixels than the head alone
ys_b = np.where(base[:, :, 3].max(1) > 40)[0]
belt = int(prof["HEAD_TOP"] + 0.55 * (ys_b.max() - prof["HEAD_TOP"]))
head = base[prof["HEAD_TOP"]:belt]
cols = np.where(head[:, :, 3].max(0) > 40)[0]
head = head[:, cols.min():cols.max() + 1]
tmpl0 = gray_on_grey(head)
picks = np.linspace(0, n - 1, min(n, 6)).astype(int)
imgs = [gray_on_grey(frames[i]) for i in picks]
best = None
for k in np.arange(0.85, 1.25, 0.005):
    t = cv2.resize(tmpl0, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
    score = np.mean([cv2.matchTemplate(im, t, cv2.TM_CCOEFF_NORMED).max() for im in imgs])
    if best is None or score > best[0]:
        best = (score, k)
score, k = best
s = 1.0 / k
out = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
for i, f in enumerate(frames):
    im = Image.fromarray(f)
    ys, xs = np.where(f[:, :, 3] > 40)
    bot, cx = ys.max(), xs.mean()
    w2 = round(SRC * s)
    g = im.resize((w2, w2), Image.LANCZOS)
    px, py = round(cx - cx * s), round(bot - bot * s)
    cell = Image.new("RGBA", (SRC, SRC), (0, 0, 0, 0))
    cell.alpha_composite(g, (max(px, 0), max(py, 0)), (max(-px, 0), max(-py, 0)))
    out.paste(cell, (i * SRC, 0))
out.save(sys.argv[3])
print(f"{sys.argv[1]}: drawn at {k:.3f}x the base sprite (match {score:.3f}); rescaled by {s:.3f}")
