"""Shape-consistency checks on a finished walk strip: what the eye catches when it plays.
(Added 23 Nov 2026 after the per-frame checks missed a flashing collar, a white sliver behind the
head and dents along the sleeve.)

Upper body only (head to hips): the legs legitimately change a lot between frames.

1. FLICKER: a patch (>= 6 px) that is solid in the frames before and after but missing in
   between, or the reverse. At walk speed neighbouring frames move 1-2 px, so the neighbours'
   agreement is shrunk/grown by 1 px first; what is left is something blinking for one frame
   (background flashing through a collar, a sleeve edge disappearing, a stray patch appearing).
2. DENTS: notches cut into the outline. The outline is compared with its own smooth version (a
   radius-2 closing); notch pixels that don't exist in either neighbouring frame are one-frame
   dents. A frame whose total is far above the approved standing drawing's is rough-edged.
4. COLLAR: the collar behind the neck, aligned to the body, compared with the loop's median:
   a frame where it is see-through or holds a dark/brown patch fails.
3. SLIVERS: thin (1-2 px) light strands on the outer edge of the head/neck/shoulders - painted-in
   collar or backdrop leftovers - compared with the approved standing drawing.

usage: python3 qa_shape.py <walk_strip.png> <idle_strip.png> [name]   -> exit 1 on failure
"""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, __import__("os").path.dirname(__file__))
from cells import CELL_W as CW

MIN_BLINK = 6
MIN_DENT = 3
HIP = 0.50


def cells(p):
    a = np.array(Image.open(p).convert("RGBA")).astype(np.float32)
    return [a[:, i * CW:(i + 1) * CW] for i in range(a.shape[1] // CW)]


def disk(r):
    y, x = np.mgrid[-r:r + 1, -r:r + 1]
    return (x * x + y * y) <= r * r


def upper(f):
    s = f[..., 3] > 128
    ys = np.where(s.any(1))[0]
    top, bot = ys.min(), ys.max()
    m = np.zeros_like(s)
    m[:top + int(HIP * (bot - top))] = True
    return m, top, bot


def notches(s):
    cl = ndimage.binary_closing(np.pad(s, 4), structure=disk(2))[4:-4, 4:-4]
    return cl & ~s


def slivers(f):
    s = f[..., 3] > 128
    up, top, bot = upper(f)
    neck = np.zeros_like(s)
    neck[top + int(.15 * (bot - top)):top + int(.36 * (bot - top))] = True
    light = s & (f[..., :3].min(2) > 150)
    thin = light & ~ndimage.binary_opening(light, structure=np.ones((3, 3)))
    outer = ndimage.binary_dilation(~s, iterations=2)
    return thin & outer & neck


def main():
    walk, idle = cells(sys.argv[1]), cells(sys.argv[2])
    name = sys.argv[3] if len(sys.argv) > 3 else sys.argv[1]
    n = len(walk)
    fails = []
    S = [f[..., 3] > 128 for f in walk]
    U = [upper(f)[0] for f in walk]
    # shirt/collar white, as its own layer: a white patch that blinks is a flashing collar
    Wt = [(f[..., 3] > 128) & (f[..., :3].min(2) > 170) for f in walk]
    for layer, L in (("outline", S), ("white", Wt)):
        for i in range(n):
            p, c, q = L[i - 1], L[i], L[(i + 1) % n]
            both_on = ndimage.binary_erosion(p, iterations=1) & ndimage.binary_erosion(q, iterations=1)
            both_off = ~ndimage.binary_dilation(p, iterations=1) & ~ndimage.binary_dilation(q, iterations=1)
            for kind, m in (("missing", both_on & ~c), ("extra", both_off & c)):
                lab, k = ndimage.label(m & U[i])
                for j in range(1, k + 1):
                    comp = lab == j
                    if comp.sum() >= MIN_BLINK:
                        yy, xx = np.where(comp)
                        fails.append(f"frame {i}: {layer} patch {kind} for one frame, {int(comp.sum())}px at ({int(xx.mean())},{int(yy.mean())})")
    N = [notches(s) & u for s, u in zip(S, U)]
    ref_notch = int((notches(idle[0][..., 3] > 128) & upper(idle[0])[0]).sum())
    for i in range(n):
        lone = N[i] & ~ndimage.binary_dilation(N[i - 1], iterations=1) & ~ndimage.binary_dilation(N[(i + 1) % n], iterations=1)
        lab, k = ndimage.label(lone)
        for j in range(1, k + 1):
            comp = lab == j
            if comp.sum() >= MIN_DENT:
                yy, xx = np.where(comp)
                fails.append(f"frame {i}: one-frame dent in the outline, {int(comp.sum())}px at ({int(xx.mean())},{int(yy.mean())})")
    rough = [int(x.sum()) for x in N]
    for i, v in enumerate(rough):
        if v > 2 * ref_notch + 25:
            fails.append(f"frame {i}: rough outline, {v} notch px (standing drawing {ref_notch})")
    ref_sl = int(slivers(idle[0]).sum())
    sl = [int(slivers(f).sum()) for f in walk]
    for i, v in enumerate(sl):
        if v > ref_sl + 6:
            fails.append(f"frame {i}: {v}px of thin light sliver on the head/neck edge (standing drawing {ref_sl})")
    # 5. BACKDROP: pale bluish-white patches (Sprixen's old backdrop; the shirt is a warm white)
    for i, f in enumerate(walk):
        cw = (f[..., 3] > 60) & (f[..., :3].min(2) > 165) & (f[..., 2] >= f[..., 0] + 3)
        lab, k = ndimage.label(cw)
        for j in range(1, k + 1):
            comp = lab == j
            if comp.sum() >= 10:
                yy, xx = np.where(comp)
                fails.append(f"frame {i}: pale backdrop-coloured patch, {int(comp.sum())}px at ({int(xx.mean())},{int(yy.mean())})")
    from collar_median import collar_consistency
    # the collar behind the neck is only seen in the side view
    cc = collar_consistency(walk) if "side" in name else [0] * n
    for i, v in enumerate(cc):
        if v > 18:
            fails.append(f"frame {i}: collar behind the neck differs from the rest of the loop ({v}px: background or a dark patch)")
    print(f"== shape {name}: {n} frames; collar odd px {min(cc)}-{max(cc)}; outline notch px {min(rough)}-{max(rough)} (standing {ref_notch}); "
          f"edge slivers {min(sl)}-{max(sl)} (standing {ref_sl})")
    for x in fails[:30]:
        print("   FAIL:", x)
    if len(fails) > 30:
        print(f"   ... {len(fails) - 30} more")
    print("   RESULT:", "PASS" if not fails else f"{len(fails)} issue(s)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
