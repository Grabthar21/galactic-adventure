"""Repair one-frame blinks in the upper body of a finished walk strip.

Finds exactly what qa_shape.py reports: patches in the upper body (outline or shirt-white layer)
that are present in both neighbouring frames but missing in this one (or the reverse), and
one-frame dents in the outline. Each such patch (grown by 2 px) is replaced by the average of the
two neighbouring frames at that spot, after aligning each neighbour to this frame by the best
whole-pixel shift (within 2 px) of the surrounding area. Neighbours agree there by definition,
so the repaired pixels continue the motion instead of blinking. Everything else is untouched.

usage: python3 deflicker.py <walk_strip.png> [out.png]
"""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, __import__("os").path.dirname(__file__))
from cells import CELL_W as CW
from qa_shape import upper, notches, big_notches, MIN_BLINK, MIN_DENT

LINE = np.array([81, 56, 47], np.float32)   # approved drawing's line colour


def layers(f):
    s = f[..., 3] > 128
    return s, s & (f[..., :3].min(2) > 170)


def defects(fr, i):
    n = len(fr)
    p, c, q = fr[i - 1], fr[i], fr[(i + 1) % n]
    U = upper(c)[0]
    out = np.zeros(c.shape[:2], bool)
    for k in range(2):
        P, C, Q = layers(p)[k], layers(c)[k], layers(q)[k]
        on = ndimage.binary_erosion(P, iterations=1) & ndimage.binary_erosion(Q, iterations=1)
        off = ~ndimage.binary_dilation(P, iterations=1) & ~ndimage.binary_dilation(Q, iterations=1)
        for m in (on & ~C, off & C):
            lab, nl = ndimage.label(m & U)
            for j in range(1, nl + 1):
                comp = lab == j
                if comp.sum() >= MIN_BLINK:
                    out |= comp
    Bp, Bc, Bq = big_notches(layers(p)[0]), big_notches(layers(c)[0]), big_notches(layers(q)[0])
    lone_b = Bc & U & ~ndimage.binary_dilation(Bp, iterations=2) & ~ndimage.binary_dilation(Bq, iterations=2)
    lab, nl = ndimage.label(lone_b)
    for j in range(1, nl + 1):
        comp = lab == j
        if comp.sum() >= 10:
            out |= comp                    # filled from the neighbouring frames, like a blink
    dent = np.zeros_like(out)
    Np, Nc, Nq = notches(layers(p)[0]), notches(layers(c)[0]), notches(layers(q)[0])
    lone = Nc & U & ~ndimage.binary_dilation(Np, iterations=1) & ~ndimage.binary_dilation(Nq, iterations=1)
    lab, nl = ndimage.label(lone)
    for j in range(1, nl + 1):
        comp = lab == j
        if comp.sum() >= MIN_DENT:
            dent |= comp
    return out, dent


def aligned(src, dst, box):
    """src shifted by the whole-pixel offset (|d| <= 2) that best matches dst inside box."""
    y0, y1, x0, x1 = box
    best = None
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            sh = np.roll(np.roll(src, dy, 0), dx, 1)
            e = np.abs(sh[y0:y1, x0:x1] - dst[y0:y1, x0:x1]).mean()
            if best is None or e < best[0]:
                best = (e, sh)
    return best[1]


def main():
    a = np.array(Image.open(sys.argv[1]).convert("RGBA")).astype(np.float32)
    n = a.shape[1] // CW
    fr = [a[:, i * CW:(i + 1) * CW].copy() for i in range(n)]
    out = [f.copy() for f in fr]
    fixed = []
    for i in range(n):
        d, dent = defects(fr, i)
        if dent.any():
            # a one-frame dent: filled in as the smooth outline would have it, in the colour of
            # the nearest solid pixel (the edge colour)
            solid = fr[i][..., 3] > 200
            _, (iy, ix) = ndimage.distance_transform_edt(~solid, return_indices=True)
            g = ndimage.binary_dilation(dent, iterations=1) & ~solid
            out[i][g, :3] = fr[i][iy[g], ix[g], :3]
            out[i][g, 3] = 255
            fr[i] = out[i].copy()
        if not d.any():
            fixed.append(int(dent.sum()))
            continue
        region = ndimage.binary_dilation(d, iterations=2)
        yy, xx = np.where(region)
        box = (max(yy.min() - 8, 0), yy.max() + 9, max(xx.min() - 8, 0), xx.max() + 9)
        if d.sum() < 12:      # small dents/blinks: neighbours as they are (what qa_shape compares)
            p, q = fr[i - 1], fr[(i + 1) % n]
        else:
            p = aligned(fr[i - 1], fr[i], box)
            q = aligned(fr[(i + 1) % n], fr[i], box)
        pm = lambda f: np.concatenate([f[..., :3] * f[..., 3:4] / 255.0, f[..., 3:4]], -1)
        avg = (pm(p) + pm(q)) / 2
        # coverage: the middle of the three frames' coverage at each pixel, so a spot both
        # neighbours cover is covered and a spot neither covers is clear (no half-filled dents)
        cov = np.median(np.stack([p[..., 3], fr[i][..., 3], q[..., 3]]), axis=0)
        k = np.where(avg[..., 3] > 0, cov / np.maximum(avg[..., 3], 1e-3), 0)[..., None]
        avg = avg * k
        al = avg[..., 3:4]
        avg[..., :3] = np.where(al > 0, avg[..., :3] * 255.0 / np.maximum(al, 1e-3), 0)
        # soft edge around the repaired patch
        w = ndimage.gaussian_filter(region.astype(np.float32), 0.8)
        w = np.maximum(w, region.astype(np.float32) * 0.0)
        w[region] = 1.0
        w = w[..., None]
        out[i] = fr[i] * (1 - w) + avg * w
        fixed.append(int(d.sum() + dent.sum()))
    from qa_shape import slivers, torso_slivers, arm_strands, grey_gaps
    import os
    rp = os.environ.get("REF_STRIP")
    refc = None
    if rp:
        ra = np.array(Image.open(rp).convert("RGBA")).astype(np.float32)
        refc = [ra[:, i * CW:(i + 1) * CW] for i in range(n)]

    def fill(f, m, i):
        """fill pixels m solid: Sprixen's own colour there when it drew something real (not its
        pale/grey backdrop), else the dark line colour"""
        col = np.broadcast_to(LINE, (int(m.sum()), 3)).copy()
        # below the belt (legs, gloves, the gaps between them) a hole is always a dark gap line
        s_ = f[..., 3] > 128
        navy_ = s_ & (f[..., 2] > f[..., 0] + 8) & (f[..., 0] < 110)
        ys_ = np.where(s_.any(1))[0]
        rows_ = np.where(navy_.sum(1) > 14)[0]
        rows_ = rows_[rows_ > ys_.min() + 0.42 * (ys_.max() - ys_.min())]
        belt_ = rows_.min() if len(rows_) else f.shape[0]
        upper_ = np.zeros_like(s_)
        upper_[:belt_] = True
        if refc is not None:
            r = refc[i]
            rr = r[..., :3]
            real = (r[..., 3] >= 60) & ~((rr.max(2) - rr.min(2) < 40) & (rr.mean(2) > 100))
            ok = (real & upper_)[m]
            col[ok] = rr[m][ok]
        f[m, :3] = col
        f[m, 3] = 255

    for i in range(n):
        f = out[i]
        # light specks sticking out of the hair line / head edge: take the colour of the dark
        # (hair / outline) pixels around them
        sp = slivers(f)
        s_ = f[..., 3] > 128
        ys_ = np.where(s_.any(1))[0]
        crown = np.zeros_like(s_)
        crown[ys_.min():ys_.min() + int(0.09 * (ys_.max() - ys_.min()))] = True
        sp |= crown & (f[..., 3] > 60) & (f[..., :3].mean(2) > 170)     # light specks in the hair
        ts = torso_slivers(f)
        f[ts] = 0                          # backdrop strand under the arm: cleared
        st = arm_strands(f) | grey_gaps(f)
        if st.any():
            # backdrop in the gap between forearm/glove and body: where the gap is open to the
            # outside it becomes see-through again; a closed sliver becomes the dark line colour
            # (two outlines meeting), never a copy of the muddy colours around it
            lab_, k_ = ndimage.label(st, structure=np.ones((3, 3)))
            out_ = ndimage.binary_dilation(f[..., 3] < 30, iterations=2)
            rgbf = f[..., :3]
            shirt_ = (f[..., 3] > 128) & (rgbf.min(2) > 175) & (rgbf[..., 0] >= rgbf[..., 2]) & ~st
            skin_ = (f[..., 3] > 128) & (rgbf[..., 0] > 190) & (rgbf[..., 1] > 120) & (rgbf[..., 0] - rgbf[..., 2] > 55)
            ref_white = np.median(rgbf[shirt_], 0) if shirt_.sum() > 20 else np.array([235, 228, 218], np.float32)
            for j_ in range(1, k_ + 1):
                c_ = lab_ == j_
                ring_ = ndimage.binary_dilation(c_, iterations=2) & ~c_
                if (ring_ & shirt_).sum() >= 3 and (ring_ & skin_).sum() >= 1 and not (c_ & out_).sum() > 0.5 * c_.sum():
                    # the far sleeve, drawn half see-through by Sprixen: painted as sleeve (shirt
                    # white, keeping the light/dark shading of the pixels) and made solid
                    lum_ = rgbf[c_].mean(1, keepdims=True)
                    shade_ = np.clip(lum_ / max(float(np.percentile(lum_, 90)), 1), 0.75, 1.0)
                    f[c_, :3] = ref_white[None, :] * shade_
                    f[c_, 3] = 255
                    continue
                if (c_ & out_).any() or c_.sum() > 60:
                    f[c_] = 0
                else:
                    fill(f, c_, i)
        if sp.any():
            lum = f[..., :3].mean(2)
            dk = (f[..., 3] > 128) & (lum < 120)
            _, (iy, ix) = ndimage.distance_transform_edt(~dk, return_indices=True)
            f[sp, :3] = f[iy[sp], ix[sp], :3]
        # stray specks left apart from the body
        m = f[..., 3] > 0
        lab, k = ndimage.label(m, structure=np.ones((3, 3)))
        if k > 1:
            sizes = ndimage.sum(m, lab, range(1, k + 1))
            main = 1 + int(np.argmax(sizes))
            f[(lab != main) & m] = 0
        # tiny enclosed see-through holes (e.g. left where a strand under the arm was cleared)
        sol = f[..., 3] >= 128               # same rule as qa_strip.py
        # slits closed off by a 1-px line (e.g. the far sleeve's outline with the sleeve itself
        # cleared as backdrop): painted as sleeve when they sit against the white shirt
        clo = ndimage.binary_closing(np.pad(sol, 3), structure=np.ones((3, 3)))[3:-3, 3:-3]
        slits, ns = ndimage.label(ndimage.binary_fill_holes(clo) & ~ndimage.binary_fill_holes(sol) & ~sol)
        rgbf = f[..., :3]
        shirt_ = sol & (rgbf.min(2) > 175) & (rgbf[..., 0] >= rgbf[..., 2])
        ysu = np.where(sol.any(1))[0]
        for j in range(1, ns + 1):
            sm = slits == j
            if sm.sum() > 80 or np.where(sm)[0].mean() > ysu.min() + 0.55 * (ysu.max() - ysu.min()):
                continue
            ring = ndimage.binary_dilation(sm, iterations=2) & ~sm & sol
            if ring.sum() and (ring & shirt_).sum() >= 0.3 * ring.sum():
                col = np.median(rgbf[ring & shirt_], 0)
                f[sm, :3] = col * 0.95
                f[sm, 3] = 255
            else:
                fill(f, sm, i)
        sol = f[..., 3] >= 128
        holes, nh = ndimage.label(ndimage.binary_fill_holes(sol) & ~sol)
        if nh:
            _, (iy, ix) = ndimage.distance_transform_edt(~sol, return_indices=True)
            for j in range(1, nh + 1):
                hm = holes == j
                if hm.sum() <= 18:          # pinhole: Sprixen's own colour there, or the line colour
                    fill(f, hm, i)
        a[:, i * CW:(i + 1) * CW] = f
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(sys.argv[2] if len(sys.argv) > 2 else sys.argv[1])
    print(f"{sys.argv[1]}: one-frame blinks repaired (px per frame): {fixed}")


if __name__ == "__main__":
    main()
