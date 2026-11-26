"""Keep the near hand (glove) the same size in every frame of a finished walk strip.

Sprixen draws the near glove at different sizes through the stride (Arthur's side walk: 260-400 px
of glove, against 395 in the approved standing drawing). This step measures the glove in the
approved standing pose (idle frame 0) and in every walk frame, then enlarges each glove that is
drawn too small about its wrist, so the hand stays one size. Only the glove (and its outline)
is resampled; the arm, body and motion are untouched. Gloves already the right size are left alone.

The glove is found from the forearm: the screen-left bare-skin forearm patch below the shoulders,
then the leather connected to its lower (wrist) end.

usage: python3 match_glove.py <walk_strip.png> <idle_strip.png> [out.png]
"""
import sys
import cv2
import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, __import__("os").path.dirname(__file__))
from cells import CELL_W as CW

MAX_GROW = 1.25


def near_glove(f):
    r, g, b, a = [f[..., i] for i in range(4)]
    op = a > 160
    ys = np.where(op.any(1))[0]
    top, bot = ys.min(), ys.max()
    h = bot - top
    skin = op & (r > 195) & (g > 125) & (b > 80) & (r - b > 55) & (g < 210)
    skin[:top + int(.33 * h)] = False
    leather = op & (r > g + 15) & (g > b) & (r < 165) & (r > 60) & (r + g + b < 400)
    lab, n = ndimage.label(skin)
    comps = []
    for k in range(1, n + 1):
        c = lab == k
        if c.sum() < 15:
            continue
        yy, xx = np.where(c)
        comps.append((xx.mean(), int(yy.max()), float(xx[yy >= yy.max() - 2].mean())))
    if not comps:
        return None
    comps.sort()
    _, wy, wx = comps[0]
    reg = leather.copy()
    reg[:wy - 1] = False
    reg &= np.abs(np.arange(f.shape[1])[None, :] - wx) <= 17
    seed = np.zeros_like(reg)
    seed[max(wy - 1, 0):wy + 4, int(wx) - 6:int(wx) + 7] = True
    gl, _ = ndimage.label(reg)
    ids = set(np.unique(gl[seed & reg])) - {0}
    if not ids:
        return None
    G = np.isin(gl, list(ids))
    return G, wx, wy


def main():
    strip = np.array(Image.open(sys.argv[1]).convert("RGBA")).astype(np.float32)
    idle = np.array(Image.open(sys.argv[2]).convert("RGBA")).astype(np.float32)[:, :CW]
    out_path = sys.argv[3] if len(sys.argv) > 3 else sys.argv[1]
    ref = near_glove(idle)
    target = float(ref[0].sum())
    n = strip.shape[1] // CW
    report = []
    for i in range(n):
        f = strip[:, i * CW:(i + 1) * CW]
        m = near_glove(f)
        if m is None:
            report.append("-")
            continue
        G, wx, wy = m
        k = min(np.sqrt(target / G.sum()), MAX_GROW)
        if k < 1.02:
            report.append("1.00")
            continue
        # the glove with its outline ring, as a premultiplied patch scaled about the wrist
        R = ndimage.binary_dilation(G, iterations=2) & (f[..., 3] > 0)
        R &= np.arange(f.shape[0])[:, None] >= wy - 1
        patch = f.copy()
        patch[~R] = 0
        pm = patch.copy()
        pm[..., :3] *= pm[..., 3:4] / 255.0
        M = np.float32([[k, 0, wx * (1 - k)], [0, k, wy * (1 - k)]])
        sc = cv2.warpAffine(pm, M, (f.shape[1], f.shape[0]), flags=cv2.INTER_CUBIC,
                            borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        sc = np.clip(sc, 0, 255)
        sa = sc[..., 3:4] / 255.0
        base = f.copy()
        base[..., :3] *= base[..., 3:4] / 255.0
        comp = sc + base * (1 - sa)
        ca = comp[..., 3:4]
        comp[..., :3] = np.where(ca > 0, comp[..., :3] * 255.0 / np.maximum(ca, 1e-3), 0)
        strip[:, i * CW:(i + 1) * CW] = comp
        report.append(f"{k:.2f}")
    Image.fromarray(np.clip(strip, 0, 255).astype(np.uint8)).save(out_path)
    print(f"{sys.argv[1]}: glove matched to the standing drawing ({int(target)} px); scale per frame: {' '.join(report)}")


if __name__ == "__main__":
    main()
