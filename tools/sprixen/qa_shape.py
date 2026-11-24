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
import os
import numpy as np
TOL = int(os.environ.get("MOTION_TOL", "1"))   # px of motion between frames treated as normal (runs move faster)
from PIL import Image
from scipy import ndimage

sys.path.insert(0, __import__("os").path.dirname(__file__))
from cells import CELL_W as CW

MIN_BLINK = 6
MIN_DENT = 3
HIP = 0.50


def cells(p, w=None):
    a = np.array(Image.open(p).convert("RGBA")).astype(np.float32)
    w = w or CW
    return [a[:, i * w:(i + 1) * w] for i in range(a.shape[1] // w)]


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


def slivers(f, reach=1):
    """reach 2 (runs) also finds a light pixel tucked one pixel inside the dark edge line"""
    s = f[..., 3] > 128
    up, top, bot = upper(f)
    neck = np.zeros_like(s)
    neck[top:top + int(.36 * (bot - top))] = True   # whole head and neck
    if reach > 1:
        neck[:] = True      # runs: light specks along the whole silhouette (e.g. at a wrist)
    lum = f[..., :3].mean(2)
    light = (f[..., 3] > 30) & (lum > 160)
    outer = ndimage.binary_dilation(f[..., 3] < 30, iterations=reach)
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


def cuffs(f, m):
    """the parts of m that are a sleeve cuff, not backdrop: closed off from the background by the
    ink line and lying against forearm skin. In a run the elbow bends toward the camera and the
    rolled cuff shows as a thin light band, which the strand / grey-gap checks would mistake for
    backdrop."""
    rgb = f[..., :3]
    s = f[..., 3] > 128
    dark = s & (rgb.mean(2) < 110)
    reach, _ = ndimage.label(~dark)
    border = set(np.unique(np.concatenate([reach[0], reach[-1], reach[:, 0], reach[:, -1]]))) - {0}
    outside = np.isin(reach, list(border))
    skin = s & (rgb[..., 0] > 170) & (rgb[..., 1] > 110) & (rgb[..., 0] - rgb[..., 2] > 45)
    shirt = s & (rgb.min(2) > 175) & (rgb[..., 0] >= rgb[..., 2])
    out = np.zeros_like(m)
    lab, k = ndimage.label(m, structure=np.ones((3, 3)))
    for j in range(1, k + 1):
        c = lab == j
        ring = ndimage.binary_dilation(c, iterations=2) & ~c
        inside = (c & outside).sum() <= 0.2 * c.sum()
        if np.median(rgb[c][:, 0] - rgb[c][:, 2]) >= 12:
            out |= c          # warm white/grey is the shirt sleeve; Sprixen's backdrop is cool/neutral
            continue
        if inside and ((ring & skin).sum() >= 2 or (ring & shirt).sum() >= 0.3 * (ring & s).sum()):
            out |= c
    return out


def boot_gaps(f):
    """runs: light neutral grey/white between the lower legs and boots (bottom quarter of the
    figure). Boots are brown and trousers navy, so a colourless light patch there is Sprixen's
    backdrop showing through the gap between the legs. Buckles (gold/tan) are not neutral."""
    s = f[..., 3] > 60
    ys = np.where(s.any(1))[0]
    top, bot = ys.min(), ys.max()
    rgb = f[..., :3]
    lum = rgb.mean(2)
    sat = rgb.max(2) - rgb.min(2)
    m = s & (sat < 30) & (lum > 90)
    m[:top + int(0.70 * (bot - top))] = False
    lab, k = ndimage.label(m, structure=np.ones((3, 3)))
    out = np.zeros_like(m)
    for j in range(1, k + 1):
        c = lab == j
        if c.sum() >= 3:
            out |= c
    return out


def inner_halo(f, ref_alpha):
    """runs: light pixels just inside the ink line where Sprixen's frame was still a soft,
    half-transparent edge (its pale matte fringe), noticeably lighter than the drawing further in.
    Returns (mask, the colour to give them: the nearest pixel deeper in)."""
    a = f[..., 3]
    sol = a >= 128
    depth = ndimage.distance_transform_edt(sol)
    lum = f[..., :3].mean(2)
    deep = sol & (depth >= 4) & (ref_alpha >= 250)
    _, (iy, ix) = ndimage.distance_transform_edt(~deep, return_indices=True)
    inner = lum[iy, ix]
    m = sol & (depth <= 3) & (ref_alpha < 235) & (lum > inner + 30) & (lum > 150)
    ys = np.where(sol.any(1))[0]
    m[ys.min() + int(0.22 * (ys.max() - ys.min())):] = False   # head only (hair tips, ears): the
    # collar's white edge meets the neck lower down and must keep its own colour
    m &= ~((iy == 0) & (ix == 0) & ~deep[0, 0])
    return m, f[iy, ix, :3]


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
    walk = cells(sys.argv[1])
    ih = Image.open(sys.argv[2]).height
    idle = cells(sys.argv[2], round(ih * 98 / 148))    # the standing strip keeps the normal cell
    name = sys.argv[3] if len(sys.argv) > 3 else sys.argv[1]
    n = len(walk)
    fails = []
    S = [f[..., 3] > 128 for f in walk]
    U = [upper(f)[0] for f in walk]
    # shirt/collar white, as its own layer: a white patch that blinks is a flashing collar
    Wt = [(f[..., 3] > 128) & (f[..., :3].min(2) > 170) for f in walk]
    # one-frame checks compare a frame with its neighbours; a run changes pose too much between
    # frames for that, so runs are checked against Sprixen's own frames instead (check 12)
    temporal = TOL < 2
    for layer, L in (("outline", S), ("white", Wt)) if temporal else ():
        for i in range(n):
            p, c, q = L[i - 1], L[i], L[(i + 1) % n]
            both_on = ndimage.binary_erosion(p, iterations=TOL) & ndimage.binary_erosion(q, iterations=TOL)
            both_off = ~ndimage.binary_dilation(p, iterations=TOL) & ~ndimage.binary_dilation(q, iterations=TOL)
            for kind, m in (("missing", both_on & ~c), ("extra", both_off & c)):
                lab, k = ndimage.label(m & U[i])
                for j in range(1, k + 1):
                    comp = lab == j
                    if comp.sum() >= MIN_BLINK:
                        yy, xx = np.where(comp)
                        fails.append(f"frame {i}: {layer} patch {kind} for one frame, {int(comp.sum())}px at ({int(xx.mean())},{int(yy.mean())})")
    N = [notches(s) & u for s, u in zip(S, U)]
    ref_notch = int((notches(idle[0][..., 3] > 128) & upper(idle[0])[0]).sum())
    for i in range(n if temporal else 0):
        lone = N[i] & ~ndimage.binary_dilation(N[i - 1], iterations=TOL) & ~ndimage.binary_dilation(N[(i + 1) % n], iterations=TOL)
        lab, k = ndimage.label(lone)
        for j in range(1, k + 1):
            comp = lab == j
            if comp.sum() >= MIN_DENT:
                yy, xx = np.where(comp)
                fails.append(f"frame {i}: one-frame dent in the outline, {int(comp.sum())}px at ({int(xx.mean())},{int(yy.mean())})")
    # wide bites present in this frame only (not in the frames before/after, and not in the
    # standing drawing's own outline)
    BN = [big_notches(s) & u for s, u in zip(S, U)]
    for i in range(n if temporal else 0):
        lone = BN[i] & ~ndimage.binary_dilation(BN[i - 1], iterations=2) & ~ndimage.binary_dilation(BN[(i + 1) % n], iterations=2)
        lab, k = ndimage.label(lone)
        for j in range(1, k + 1):
            comp = lab == j
            if comp.sum() >= 10:
                yy, xx = np.where(comp)
                fails.append(f"frame {i}: bite out of the outline, {int(comp.sum())}px at ({int(xx.mean())},{int(yy.mean())})")
    # slits: see-through areas closed off by a 1-px line in the upper body (a part drawn as an
    # outline with nothing inside)
    for i, (sh, u) in enumerate(zip(S, U) if temporal else ()):
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
    sl = [int(slivers(f, 1 if temporal else 2).sum()) for f in walk]
    for i, v in enumerate(sl):
        if v > ref_sl + 2:
            fails.append(f"frame {i}: {v}px of thin light sliver on the head/neck edge (standing drawing {ref_sl})")
    # 5. BACKDROP: pale bluish-white patches (Sprixen's old backdrop; the shirt is a warm white)
    for i, f in enumerate(walk):
        cw = (f[..., 3] > 60) & (f[..., :3].min(2) > 165) & (f[..., 2] >= f[..., 0] + 5) \
            & (f[..., :3].max(2) - f[..., :3].min(2) < 30)
        if not temporal:     # runs: cool shading inside the shirt's ink line is the shirt
            cw &= ~cuffs(f.astype(float), cw)
            # ... and so is a cool patch nowhere near the see-through background (backdrop only
            # shows at the silhouette's edge or in a gap open to it)
            near_clear = ndimage.binary_dilation(f[..., 3] < 30, iterations=3)
            lab_, k_ = ndimage.label(cw)
            for j_ in range(1, k_ + 1):
                if not (near_clear & (lab_ == j_)).any():
                    cw &= lab_ != j_
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
        if not temporal:
            m &= ~cuffs(f, m)
        if m.sum():
            yy, xx = np.where(m)
            fails.append(f"frame {i}: thin white strand by the forearm, {int(m.sum())}px around ({int(xx.mean())},{int(yy.mean())})")
    # 10. GREY BACKDROP in the gaps between forearm, glove, hip and trousers
    for i, f in enumerate(walk):
        m = grey_gaps(f)
        if not temporal:
            m &= ~cuffs(f, m)
        if m.sum():
            yy, xx = np.where(m)
            fails.append(f"frame {i}: grey backdrop between arm and body, {int(m.sum())}px around ({int(xx.mean())},{int(yy.mean())})")
    from collar_median import collar_consistency
    # the collar behind the neck is only seen in the side view
    cc = collar_consistency(walk) if "side" in name else [0] * n
    for i, v in enumerate(cc):
        if v > 24:
            fails.append(f"frame {i}: collar behind the neck differs from the rest of the loop ({v}px: background or a dark patch)")
    # 12. HOLES WE MADE: solid in Sprixen's own frame, see-through in ours
    rp = os.environ.get("REF_STRIP")
    if rp and not temporal:
        R = np.array(Image.open(rp).convert("RGBA")).astype(int)
        cw = R.shape[1] // n
        for i in range(n):
            ra = R[:, i * cw:(i + 1) * cw, 3]
            sa = walk[i][..., 3] if walk[i].shape[:2] == ra.shape else None
            if sa is None:
                continue
            lab, k = ndimage.label((ra > 200) & (sa < 100))
            for j in range(1, k + 1):
                comp = lab == j
                rr = R[:, i * cw:(i + 1) * cw, :3][comp]
                backdrop = (rr.max(1) - rr.min(1) < 40) & (rr.mean(1) > 100)   # Sprixen's grey/white backdrop
                if comp.sum() >= 6 and backdrop.mean() < 0.5:
                    yy, xx = np.nonzero(comp)
                    fails.append(f"frame {i}: see-through hole that Sprixen's drawing doesn't have, {int(comp.sum())}px at ({int(xx.mean())},{int(yy.mean())})")
    # 14. BACKDROP BETWEEN THE BOOTS (runs)
    if not temporal:
        for i, f in enumerate(walk):
            m = boot_gaps(f)
            if m.sum():
                yy, xx = np.where(m)
                fails.append(f"frame {i}: grey backdrop between the legs/boots, {int(m.sum())}px around ({int(xx.mean())},{int(yy.mean())})")
    # 13. LIGHT HALO JUST INSIDE THE INK LINE (runs): Sprixen's pale soft edge left behind the line
    if rp and not temporal:
        for i in range(n):
            ra = R[:, i * cw:(i + 1) * cw, 3]
            m, _ = inner_halo(walk[i].astype(float), ra)
            lab, k = ndimage.label(m, structure=np.ones((3, 3)))
            for j in range(1, k + 1):
                comp = lab == j
                if comp.sum() >= 2:
                    yy, xx = np.nonzero(comp)
                    fails.append(f"frame {i}: light halo inside the outline, {int(comp.sum())}px at ({int(xx.mean())},{int(yy.mean())})")
    # 11. GHOSTING: a frame that looks like two neighbouring frames blended (double face / limbs):
    #     its face area is much closer to the average of its neighbours than to either one alone
    for i in range(n):
        f, p, q = walk[i], walk[i - 1], walk[(i + 1) % n]
        ys_ = np.where((f[..., 3] > 128).any(1))[0]
        t0, t1 = ys_.min(), ys_.min() + int(0.22 * (ys_.max() - ys_.min()))
        A, P, Q = f[t0:t1, :, :3], p[t0:t1, :, :3], q[t0:t1, :, :3]
        m = (f[t0:t1, :, 3] > 128) & (p[t0:t1, :, 3] > 128) & (q[t0:t1, :, 3] > 128)
        if m.sum() < 200:
            continue
        d_avg = np.abs(A - (P + Q) / 2)[m].mean()
        d_one = min(np.abs(A - P)[m].mean(), np.abs(A - Q)[m].mean())
        if d_one > 12 and d_avg < 0.55 * d_one:
            fails.append(f"frame {i}: face looks like a blend of the frames either side (ghosting)")
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
