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


def big_notches(s):
    """wider bites out of the outline (up to ~8 px across) that a radius-2 closing misses"""
    cl = ndimage.binary_closing(np.pad(s, 6), structure=disk(4))[6:-6, 6:-6]
    return cl & ~s


def notches(s):
    cl = ndimage.binary_closing(np.pad(s, 4), structure=disk(2))[4:-4, 4:-4]
    return cl & ~s


def slivers(f):
    s = f[..., 3] > 128
    up, top, bot = upper(f)
    neck = np.zeros_like(s)
    neck[top:top + int(.36 * (bot - top))] = True   # whole head and neck
    lum = f[..., :3].mean(2)
    light = (f[..., 3] > 30) & (lum > 160)
    outer = ndimage.binary_dilation(f[..., 3] < 30, iterations=1)
    # a light pixel on the outer edge whose solid neighbours are mostly much darker (hair, outline)
    # is a speck sticking out of the drawing (white/peach dots along the hair line)
    sol = f[..., 3] > 128
    dark_nb = ndimage.convolve((sol & (lum < 120)).astype(np.float32), np.ones((3, 3)), mode="constant")
    sol_nb = ndimage.convolve(sol.astype(np.float32), np.ones((3, 3)), mode="constant")
    speck = light & outer & (dark_nb >= np.maximum(2, 0.6 * (sol_nb - 1)))
    return speck & neck


def torso_slivers(f):
    """thin (1-2 px) light strands on the outside edge between arm and torso (shoulders to hips):
    backdrop left in the gap under the arm"""
    s = f[..., 3] > 30
    ys = np.where(s.any(1))[0]
    top, bot = ys.min(), ys.max()
    band = np.zeros_like(s)
    band[top + int(.30 * (bot - top)):top + int(.62 * (bot - top))] = True
    light = s & (f[..., :3].min(2) > 165)
    thin = light & ~ndimage.binary_opening(light, structure=np.ones((3, 3)))
    outer = ndimage.binary_dilation(f[..., 3] < 30, iterations=1)
    m = thin & outer & band
    lab, k = ndimage.label(m, structure=np.ones((3, 3)))
    keep = np.zeros_like(m)
    for j in range(1, k + 1):
        comp = lab == j
        yy, xx = np.where(comp)
        if comp.sum() >= 4 and np.ptp(yy) >= 2:          # a strand, not a single edge pixel
            keep |= comp
    return keep


def arm_strands(f):
    """narrow (<= 3 px wide) light strands between the forearm and the body (elbow to hip): the
    sleeve and shirt are wide patches; a thin white line there is backdrop showing through the gap"""
    s = f[..., 3] > 60
    ys = np.where(s.any(1))[0]
    top, bot = ys.min(), ys.max()
    band = np.zeros_like(s)
    band[top + int(.44 * (bot - top)):top + int(.72 * (bot - top))] = True
    rgb = f[..., :3]
    sat = rgb.max(2) - rgb.min(2)
    # white, or the light grey / blue-grey of Sprixen's backdrop blended into the gap
    skinlike = (rgb[..., 0] - rgb[..., 2] > 40)
    light = s & band & ~skinlike & ((rgb.min(2) > 160) | ((rgb.min(2) > 115) & (sat < 40)))
    lab, k = ndimage.label(light, structure=np.ones((3, 3)))
    out = np.zeros_like(s)
    for j in range(1, k + 1):
        comp = lab == j
        yy, xx = np.where(comp)
        widths = [np.ptp(xx[yy == y]) + 1 for y in np.unique(yy)]
        if comp.sum() >= 3 and np.median(widths) <= 4 and np.ptp(yy) >= 1:
            # a sleeve cuff sits directly above the forearm skin; backdrop runs beside it
            r_, g_, b_ = f[..., 0], f[..., 1], f[..., 2]
            sk = s & (r_ > 190) & (g_ > 120) & (r_ - b_ > 55)
            ring = ndimage.binary_dilation(comp, iterations=2) & ~comp & sk
            if ring.sum() >= 3 and np.where(ring)[0].mean() > yy.mean() + 1 \
                    and abs(np.where(ring)[1].mean() - xx.mean()) < 3:
                continue
            out |= comp
    return out


def grey_gaps(f):
    """neutral grey patches between forearm, glove, hip and trousers (elbow to thigh): Sprixen's
    backdrop blended into a narrow gap. Nothing in the outfit there is a neutral mid grey (the
    trousers are dark navy, gloves/vest saturated brown); the shirt's grey fold lines sit inside the
    white shirt, so patches mostly surrounded by shirt white are skipped."""
    s = f[..., 3] > 60
    ys = np.where(s.any(1))[0]
    top, bot = ys.min(), ys.max()
    band = np.zeros_like(s)
    band[top + int(.44 * (bot - top)):top + int(.75 * (bot - top))] = True
    rgb = f[..., :3]
    lum = rgb.mean(2)
    sat = rgb.max(2) - rgb.min(2)
    grey = s & band & (((sat < 26) & (lum > 85)) | ((sat < 40) & (lum > 100))) & (lum < 215)
    # the belt and its buckle have light grey-gold edges: the belt rows are skipped
    navy = s & (rgb[..., 2] > rgb[..., 0] + 8) & (rgb[..., 0] < 110)
    rows = np.where(navy.sum(1) > 14)[0]
    rows = rows[rows > top + 0.42 * (bot - top)]
    if len(rows):
        grey[max(rows.min() - 10, 0):rows.min() + 3] = False
    shirt = s & (rgb.min(2) > 175)
    lab, k = ndimage.label(grey, structure=np.ones((3, 3)))
    out = np.zeros_like(s)
    for j in range(1, k + 1):
        comp = lab == j
        if comp.sum() < 3:
            continue
        ring = ndimage.binary_dilation(comp, iterations=2) & ~comp & s
        if ring.sum() and (ring & shirt).sum() >= 0.3 * ring.sum():
            continue
        out |= comp
    return out


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
    # wide bites present in this frame only (not in the frames before/after, and not in the
    # standing drawing's own outline)
    BN = [big_notches(s) & u for s, u in zip(S, U)]
    for i in range(n):
        lone = BN[i] & ~ndimage.binary_dilation(BN[i - 1], iterations=2) & ~ndimage.binary_dilation(BN[(i + 1) % n], iterations=2)
        lab, k = ndimage.label(lone)
        for j in range(1, k + 1):
            comp = lab == j
            if comp.sum() >= 10:
                yy, xx = np.where(comp)
                fails.append(f"frame {i}: bite out of the outline, {int(comp.sum())}px at ({int(xx.mean())},{int(yy.mean())})")
    # slits: see-through areas closed off by a 1-px line in the upper body (a part drawn as an
    # outline with nothing inside)
    for i, (sh, u) in enumerate(zip(S, U)):
        clo = ndimage.binary_closing(np.pad(sh, 3), structure=np.ones((3, 3)))[3:-3, 3:-3]
        sl = ndimage.binary_fill_holes(clo) & ~ndimage.binary_fill_holes(sh) & ~sh & u
        lab, k = ndimage.label(sl)
        for j in range(1, k + 1):
            comp = lab == j
            if comp.sum() >= 6:
                yy, xx = np.where(comp)
                fails.append(f"frame {i}: see-through slit inside the outline, {int(comp.sum())}px at ({int(xx.mean())},{int(yy.mean())})")
    rough = [int(x.sum()) for x in N]
    for i, v in enumerate(rough):
        if v > 2 * ref_notch + 25:
            fails.append(f"frame {i}: rough outline, {v} notch px (standing drawing {ref_notch})")
    ref_sl = int(slivers(idle[0]).sum())
    sl = [int(slivers(f).sum()) for f in walk]
    for i, v in enumerate(sl):
        if v > ref_sl + 2:
            fails.append(f"frame {i}: {v}px of thin light sliver on the head/neck edge (standing drawing {ref_sl})")
    # 5. BACKDROP: pale bluish-white patches (Sprixen's old backdrop; the shirt is a warm white)
    for i, f in enumerate(walk):
        cw = (f[..., 3] > 60) & (f[..., :3].min(2) > 165) & (f[..., 2] >= f[..., 0] + 5) \
            & (f[..., :3].max(2) - f[..., :3].min(2) < 30)
        lab, k = ndimage.label(cw)
        for j in range(1, k + 1):
            comp = lab == j
            if comp.sum() >= 10:
                yy, xx = np.where(comp)
                fails.append(f"frame {i}: pale backdrop-coloured patch, {int(comp.sum())}px at ({int(xx.mean())},{int(yy.mean())})")
    # 6. WHITE BELOW THE BELT: nothing in the outfit below the belt is white, so light colourless
    #    patches there are backdrop between arm, hip and legs
    for i, f in enumerate(walk):
        s_ = f[..., 3] > 128
        navy = s_ & (f[..., 2] > f[..., 0] + 8) & (f[..., 0] < 110)
        ys_ = np.where(s_.any(1))[0]
        rows = np.where(navy.sum(1) > 14)[0]
        rows = rows[rows > ys_.min() + 0.42 * (ys_.max() - ys_.min())]   # trousers, not the neckerchief
        if not len(rows):
            continue
        pale = (f[..., 3] > 60) & (f[..., :3].min(2) > 140) & (f[..., :3].max(2) - f[..., :3].min(2) < 45)
        pale[:rows.min() + 2] = False
        lab, k = ndimage.label(pale)
        for j in range(1, k + 1):
            comp = lab == j
            if comp.sum() >= 4:
                yy, xx = np.where(comp)
                fails.append(f"frame {i}: white patch below the belt (between arm and body), {int(comp.sum())}px at ({int(xx.mean())},{int(yy.mean())})")
    # 7. HAIR CROWN: nothing light belongs in the top of the hair (light specks there are backdrop
    #    made solid and recoloured)
    for i, f in enumerate(walk):
        s_ = f[..., 3] > 128
        ys_ = np.where(s_.any(1))[0]
        crown = np.zeros_like(s_)
        crown[ys_.min():ys_.min() + int(0.09 * (ys_.max() - ys_.min()))] = True
        lt = crown & (f[..., 3] > 60) & (f[..., :3].mean(2) > 170)
        lab, k = ndimage.label(lt)
        for j in range(1, k + 1):
            comp = lab == j
            if comp.sum() >= 2:
                yy, xx = np.where(comp)
                fails.append(f"frame {i}: light speck in the hair, {int(comp.sum())}px at ({int(xx.mean())},{int(yy.mean())})")
    # 8. UNDER THE ARM: thin white strands on the outside edge between arm and torso
    for i, f in enumerate(walk):
        m = torso_slivers(f)
        if m.sum():
            yy, xx = np.where(m)
            fails.append(f"frame {i}: white strand between arm and body, {int(m.sum())}px around ({int(xx.mean())},{int(yy.mean())})")
    # 9. BETWEEN FOREARM AND BODY: thin white strands
    for i, f in enumerate(walk):
        m = arm_strands(f)
        if m.sum():
            yy, xx = np.where(m)
            fails.append(f"frame {i}: thin white strand by the forearm, {int(m.sum())}px around ({int(xx.mean())},{int(yy.mean())})")
    # 10. GREY BACKDROP in the gaps between forearm, glove, hip and trousers
    for i, f in enumerate(walk):
        m = grey_gaps(f)
        if m.sum():
            yy, xx = np.where(m)
            fails.append(f"frame {i}: grey backdrop between arm and body, {int(m.sum())}px around ({int(xx.mean())},{int(yy.mean())})")
    from collar_median import collar_consistency
    # the collar behind the neck is only seen in the side view
    cc = collar_consistency(walk) if "side" in name else [0] * n
    for i, v in enumerate(cc):
        if v > 24:
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
