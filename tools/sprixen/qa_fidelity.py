"""Fidelity check: did the clean-up change Sprixen's drawing INSIDE the character?

The build also makes a reference strip from Sprixen's frames with only the geometry steps
(scale, head size, legs, placement) and no colour/clean-up steps. Inside the body (pixels solid in
both, 2+ px from the edge) the finished strip should look like that reference, except for the
fixes we mean to make. Any patch of 5+ px that changed a lot is reported, so an edit that eats a
neckerchief highlight, darkens an eye or paints a square on the shirt fails the build.

Allowed changes (not reported): gloves (bare fingers repainted as leather, and the enlarged near
glove), the collar behind the neck (see-through collar filled in white), and the outline band.

usage: python3 qa_fidelity.py <final_strip.png> <reference_strip.png> [name]
"""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, __import__("os").path.dirname(__file__))
from cells import CELL_W as CW

DIFF = 70
MIN_PATCH = 5


def cells(p):
    a = np.array(Image.open(p).convert("RGBA")).astype(np.float32)
    return [a[:, i * CW:(i + 1) * CW] for i in range(a.shape[1] // CW)]


def leather(f):
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    return (r > g + 10) & (g >= b - 4) & (r < 170) & (r > 45)


def skin(f):
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    return (r > 180) & (g > 110) & (b > 70) & (r - b > 50)


def main():
    fin, ref = cells(sys.argv[1]), cells(sys.argv[2])
    name = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "--fix" else sys.argv[1]
    fails, counts = [], []
    for i, (f, r) in enumerate(zip(fin, ref)):
        both = (f[..., 3] > 200) & (r[..., 3] > 200)
        inner = ndimage.binary_erosion(both, iterations=2)
        d = np.abs(f[..., :3] - r[..., :3]).max(2)
        ch = inner & (d > DIFF)
        # allowed: glove repaint / enlargement, and light collar fill behind the neck
        ch &= ~(leather(f) & (skin(r) | leather(r) | (r[..., :3].mean(2) < 150)))
        ys = np.where(both.any(1))[0]
        t, b = ys.min(), ys.max()
        collar = np.zeros_like(ch)
        collar[t + int(.22 * (b - t)):t + int(.36 * (b - t))] = True
        ch &= ~(collar & (f[..., :3].min(2) > 165))
        # allowed: a one-frame blink of Sprixen's repaired toward the neighbouring frames
        nb = (fin[i - 1][..., :3] + fin[(i + 1) % len(fin)][..., :3]) / 2
        ch &= ~(np.abs(f[..., :3] - nb).max(2) < np.abs(r[..., :3] - nb).max(2) - 20)
        # allowed: Sprixen's backdrop (pale, colourless) cleared or recoloured
        ch &= ~((r[..., :3].min(2) > 150) & (r[..., :3].max(2) - r[..., :3].min(2) < 40)
                & (f[..., :3].min(2) <= 150))
        # the face (brow to chin) is checked right up to the edge: the far eye sits on the outline
        face = np.zeros_like(ch)
        face[t + int(.07 * (b - t)):t + int(.21 * (b - t))] = True
        sk = skin(r) | skin(f)
        near_face = ndimage.binary_dilation(sk & face, iterations=4)
        ch |= face & near_face & (f[..., 3] > 128) & (r[..., 3] > 200) & (d > 60)
        lab, k = ndimage.label(ch)
        if "--fix" in sys.argv:
            # put Sprixen's own drawing back in patches the clean-up changed by mistake
            for j in range(1, k + 1):
                comp = lab == j
                if comp.sum() >= MIN_PATCH:
                    g = ndimage.binary_dilation(comp, iterations=1) & (inner | face) & (r[..., 3] > 200)
                    f[g] = r[g]          # solid drawing only: never the reference's light edge fringe
            continue
        n = 0
        for j in range(1, k + 1):
            comp = lab == j
            if comp.sum() >= MIN_PATCH:
                yy, xx = np.where(comp)
                n += int(comp.sum())
                fails.append(f"frame {i}: drawing changed inside the body, {int(comp.sum())}px at ({int(xx.mean())},{int(yy.mean())})")
        counts.append(n)
    if "--fix" in sys.argv:
        out = np.concatenate(fin, axis=1)
        Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(sys.argv[1])
        print(f"{sys.argv[1]}: mistaken interior edits restored from Sprixen's drawing")
        return
    print(f"== fidelity {name}: changed px per frame {min(counts)}-{max(counts)}")
    for x in fails[:30]:
        print("   FAIL:", x)
    if len(fails) > 30:
        print(f"   ... {len(fails) - 30} more")
    print("   RESULT:", "PASS" if not fails else f"{len(fails)} issue(s)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
