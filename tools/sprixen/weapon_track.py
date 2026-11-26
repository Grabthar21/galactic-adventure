"""Attack strips with a swappable weapon: take the weapon OUT of Sprixen's attack video and record
where it was, so the game can draw any weapon in its place.

Sprixen draws the hero swinging a SOLID LIME-GREEN sword (a stand-in, asked for in the prompt). For
every frame this script:
  - finds the green blade and fits a line to it: which end is the point (the blade narrows to it)
    and which the pommel (the cross-guard, the widest part, sits near it), the grip (middle of the
    handle), the angle and the visible length (shorter when the blade swings toward or away from
    the camera), and whether it passes behind the body (green missing where it crosses him);
  - erases the green, and Sprixen's motion smears, filling the body where the blade crossed it.
The game (scripts/player.gd) draws the equipped MeleeWeapon picture on that track, blended between
frames, plus its own swing trail.

The three slashes and the recovery are cut from ONE take, so slash 2 starts in the very pose slash 1
ends in. They are built as one strip (one placement for every frame, so the body never jumps between
slashes) and split afterwards.

Steps (build_char.py calls them):
  prep <raw.png> <segments.json> <combo_raw.png> <raw_track.json>
      segments.json: {"attack1": [s, e, count(, [skip frames])], ..., "attack_rec": [...]} (raw
      frame numbers; e < s plays backwards). Writes the picked frames, weapon erased (256px cells), and the track
      in raw-frame pixels.
  finish <combo_strip.png> <combo_raw.png> <raw_track.json> <segments.json> <out_prefix> <fps.json>
      splits the built strip (+ its _mask) into <out_prefix>_attack1.png ... _attack_rec.png and
      writes <out_prefix>_attack_track.json in strip-cell pixels (what the game reads).
"""
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage

SRC = 256


# ---------------------------------------------------------------- detection

def green_masks(f):
    r, g, b, a = (f[..., i].astype(int) for i in range(4))
    # lime to olive green (Sprixen paints the stand-in anywhere from bright lime to a dull olive):
    # clearly greener than red, far greener than blue -- nothing on him is
    strong = (g >= r + 10) & (g >= b + 35) & (a > 100)
    # weak green: the blade's dark outline, the olive hilt, antialiased edges -- only next to
    # strong green, so nothing greenish elsewhere on him is touched (his browns, skin and gold
    # are all redder than they are green)
    weak = (g >= r + 3) & (g > b + 12) & (a > 10)
    near = ndimage.binary_dilation(strong, iterations=8)
    full = (weak & near) | strong
    # a smeared, half-blended stretch of the stand-in (olive over his clothes) far from the
    # solid blade: a patch of weak green that is still clearly green on the whole
    lab, n = ndimage.label(weak & ~full)
    for k in range(1, n + 1):
        m = lab == k
        if m.sum() >= 20 and np.median((g - b)[m]) >= 35 and np.median((g - r)[m]) >= 5:
            full |= m
    return strong, full


def cool_pale(f):
    """Sprixen's white motion smear: a cool or greenish white (the shirt's white, the skin and
    the gold are all warm: more red than green)."""
    r, g, b, a = (f[..., i].astype(int) for i in range(4))
    return (a > 60) & (r > 160) & (g >= r - 2) & (b >= r - 40) & ~((g >= r + 10) & (g >= b + 35))


def _thin(strong):
    """The blade is a thin bar; a motion smear is a wide sheet. Keep only the thin parts."""
    disk = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    thick = cv2.morphologyEx(strong.astype(np.uint8), cv2.MORPH_OPEN, disk) > 0
    return strong & ~ndimage.binary_dilation(thick, iterations=2)


def _elong(mask):
    ys, xs = np.nonzero(mask)
    if len(xs) < 60:
        return 0.0
    w, _ = np.linalg.eigh(np.cov(np.c_[xs, ys].T.astype(float)))
    return float(np.sqrt(w[1] / max(w[0], 1e-6)))


def fit_blade(strong, body=None):
    """Line fit of the blade. None if no blade-shaped part is found (all smear, or hidden)."""
    best, bk = None, -1
    for src in (strong, _thin(strong)):
        lab, n = ndimage.label(src)
        for k in range(1, n + 1):
            m = lab == k
            sz = int(m.sum())
            if sz < 60:
                continue
            e = _elong(m)
            if e >= 4.0 and sz * min(e, 12) > bk:
                best, bk = m, sz * min(e, 12)
        if best is not None:
            break       # the whole green part is already blade-shaped: no smear to strip
    if best is None:
        return None
    ys, xs = np.nonzero(best)
    pts = np.c_[xs, ys].astype(float)
    c = pts.mean(0)
    w, v = np.linalg.eigh(np.cov((pts - c).T))
    axis = v[:, 1]
    if w[0] <= 0 or np.sqrt(w[1] / max(w[0], 1e-6)) < 4.0:
        return None          # not a straight thin thing: a smear
    t = (pts - c) @ axis
    perp = (pts - c) @ np.array([-axis[1], axis[0]])
    lo, hi = t.min(), t.max()
    if hi - lo < 25:
        return None
    # width along the blade, in 12 bins: the cross-guard is the widest bin; the end nearer to it
    # is the pommel
    bins = np.linspace(lo, hi, 13)
    wid = []
    for i in range(12):
        sel = (t >= bins[i]) & (t <= bins[i + 1])
        wid.append(np.ptp(perp[sel]) if sel.sum() > 2 else 0)
    gi = int(np.argmax(wid))
    gpos = (bins[gi] + bins[gi + 1]) / 2
    guard_lo = gpos - lo < hi - gpos
    # the hand: the end held in his fist touches the body; the point is out in the air (unless
    # the blade lies across him). A part touching the body at neither end is a smear wisp.
    pommel_lo = guard_lo
    if body is not None:
        def contact(tv):
            x, y = c + axis * tv
            x0, y0 = int(round(x)), int(round(y))
            win = body[max(y0 - 7, 0):y0 + 8, max(x0 - 7, 0):x0 + 8]
            return int(win.sum())
        c_lo, c_hi = contact(lo), contact(hi)
        if max(c_lo, c_hi) < 5:
            return None
        if c_lo > 2 * c_hi + 4:
            pommel_lo = True
        elif c_hi > 2 * c_lo + 4:
            pommel_lo = False
    if pommel_lo:
        pommel, tip = lo, hi
    else:
        pommel, tip = hi, lo
    # the cross-guard sits between the hand and the point: if the widest part is at the far end
    # (the point's smear, say), put it a fifth of the way up from the hand
    if abs(gpos - pommel) > 0.5 * (hi - lo):
        gpos = pommel + 0.2 * (tip - pommel)
    # the grip: the middle of the handle, between the guard and the pommel end
    grip = gpos + 0.5 * (pommel - gpos)
    gp = c + axis * grip
    tp = c + axis * tip
    d = tp - gp
    return {"g": gp, "tip": tp, "a": float(np.degrees(np.arctan2(d[1], d[0]))),
            "l": float(np.hypot(*d)), "seg": (gp, tp)}


def erase(f, full):
    """Remove the green blade (+ smears): where it crossed the body, fill the body back in."""
    out = f.copy()
    m = ndimage.binary_dilation(full, iterations=3)
    if not m.any():
        return out, m
    m8 = m.astype(np.uint8) * 255
    rgb = np.ascontiguousarray(f[..., :3])
    # colour from the surrounding body; alpha: inpainted from what is around (body around ->
    # opaque, empty around -> clear)
    a = f[..., 3].copy()
    a[m] = 0
    a_in = cv2.inpaint(np.where(m, 0, f[..., 3]).astype(np.uint8), m8, 3, cv2.INPAINT_TELEA)
    # body support: opaque non-green pixels around the hole
    body = (f[..., 3] > 200) & ~m
    # the blade's hole is filled where body lies on both sides of it (a closing wider than the
    # blade); where it stuck out into the air it stays clear. Where a blade in front of him is
    # filled in, the game draws the weapon over that very spot again.
    disk = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (23, 23))
    closed = cv2.morphologyEx(body.astype(np.uint8), cv2.MORPH_CLOSE, disk) > 0
    keep = m & closed
    col = cv2.inpaint(cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2BGR), m8, 4, cv2.INPAINT_TELEA)
    col = cv2.cvtColor(col, cv2.COLOR_BGR2RGB)
    out[m, 3] = 0
    out[keep, :3] = col[keep]
    out[keep, 3] = 255
    # leftover wisps of smear floating free of him: keep only the body (and any big part of it)
    lab, n = ndimage.label(out[..., 3] > 20)
    if n > 1:
        sz = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
        big = sz.max()
        for k in range(1, n + 1):
            if sz[k - 1] < 0.25 * big:
                out[lab == k, 3] = 0
    # pale smear left on him: whitish, semi-transparent pixels where the green swept
    # (only patches reaching out into the empty background: the cool shading of a white sleeve,
    # enclosed by his outline, stays)
    swept = ndimage.binary_dilation(m, iterations=8)
    cp = swept & cool_pale(f)
    if cp.any():
        air = ndimage.binary_dilation(f[..., 3] < 20, iterations=2)
        lab, n = ndimage.label(cp)
        touch = ndimage.maximum(air, lab, range(1, n + 1))
        for k in range(1, n + 1):
            if touch[k - 1]:
                out[lab == k, 3] = 0
    return out, m


def behind(f_orig, strong_full, body_alpha, seg):
    """True if the blade passes behind the body: where the line crosses the body, no green."""
    (x0, y0), (x1, y1) = seg
    n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    inside = hidden = 0
    for k in range(n):
        x = int(round(x0 + (x1 - x0) * k / max(n - 1, 1)))
        y = int(round(y0 + (y1 - y0) * k / max(n - 1, 1)))
        if 0 <= x < SRC and 0 <= y < SRC and body_alpha[y, x]:
            inside += 1
            win = strong_full[max(y - 2, 0):y + 3, max(x - 2, 0):x + 3]
            hidden += not win.any()
    return inside >= 6 and hidden > 0.5 * inside


def seg_frames(s, e, count, bad):
    step = 1 if e >= s else -1
    cand = [i for i in range(s, e + step, step) if i not in bad or i in (s, e)]
    idx = np.round(np.linspace(0, len(cand) - 1, count)).astype(int)
    return [cand[i] for i in idx]


def prep(raw_path, seg_path, out_path, track_path):
    segs = json.load(open(seg_path))
    sheet = np.array(Image.open(raw_path).convert("RGBA"))
    n = sheet.shape[1] // SRC
    frames = [sheet[:, i * SRC:(i + 1) * SRC] for i in range(n)]
    # frames swamped by a white motion smear are left out (green smears are simply erased); the
    # game's own swing trail stands in for them
    cools = np.array([int(cool_pale(f).sum()) for f in frames])
    r_, g_, b_ = (sheet[..., i].astype(int) for i in range(3))
    pale_all = (sheet[..., 3] > 100) & (np.abs(r_ - g_) < 22) & (np.abs(g_ - b_) < 28) & (r_ > 175)
    pales = np.array([int(pale_all[:, i * SRC:(i + 1) * SRC].sum()) for i in range(n)])
    cleaned = [erase(f, green_masks(f)[1]) for f in frames]
    areas = np.array([int((c[0][..., 3] > 128).sum()) for c in cleaned])
    # also out: a frame where the smear covered part of him (erasing it leaves him cut short)
    bad = set(np.where((cools > max(1400, 6 * np.median(cools))) | (pales > 2 * np.median(pales))
                       | (areas < 0.85 * np.median(areas)))[0].tolist())
    picks, names = [], []
    for name, seg in segs.items():
        s, e, count = seg[:3]
        # an optional 4th entry lists raw frames to leave out by hand (a smear on him the
        # automatic checks can't see)
        p = seg_frames(s, e, count, bad | set(seg[3] if len(seg) > 3 else []))
        picks += p
        names += [name] * len(p)
    out = np.zeros((SRC, SRC * len(picks), 4), np.uint8)
    track = []
    for j, i in enumerate(picks):
        f = frames[i]
        strong, full = green_masks(f)
        clean = cleaned[i][0]
        out[:, j * SRC:(j + 1) * SRC] = clean
        body = (f[..., 3] > 200) & ~ndimage.binary_dilation(full, iterations=2)
        fit = fit_blade(strong, body)
        rec = {"raw": int(i), "seg": names[j], "ok": fit is not None, "green": int(strong.sum())}
        if fit:
            rec.update({"g": [float(v) for v in fit["g"]], "a": fit["a"], "l": fit["l"],
                        "b": bool(behind(f, full, clean[..., 3] > 200, fit["seg"]))})
        track.append(rec)
    # a short find far shorter than the blade usually is: a wisp of smear, not the blade
    lens = [t["l"] for t in track if t["ok"]]
    if lens:
        med = float(np.median(lens))
        for t in track:
            if t["ok"] and t["l"] < 0.4 * med:
                t["ok"] = False
    Image.fromarray(out).save(out_path)
    json.dump({"picks": picks, "names": names, "frames": track, "bad": sorted(bad)},
              open(track_path, "w"), indent=0)
    print(f"picked {len(picks)} frames, blade found in {sum(t['ok'] for t in track)}, "
          f"smear frames skipped: {sorted(bad)}")


# ---------------------------------------------------------------- mapping to the strip

def _alpha_bbox(a):
    ys, xs = np.nonzero(a)
    return xs.min(), ys.min(), xs.max(), ys.max()


def align(raw_a, cell_a):
    """Uniform scale + offset mapping a raw frame onto its strip cell (the build only scales and
    moves frames): scale from the bodies' heights, offset by matching the silhouettes."""
    rb, cb = _alpha_bbox(raw_a), _alpha_bbox(cell_a)
    k = (cb[3] - cb[1] + 1) / (rb[3] - rb[1] + 1)
    return k


def fill_gaps(fr, spins):
    """Frames where no blade was found (a smear, or hidden behind him): blend from the found
    frames either side. Angles turn the way the slash turns (spins: +1 / -1 per segment)."""
    ok = [i for i, f in enumerate(fr) if f["ok"]]
    for i, f in enumerate(fr):
        if f["ok"]:
            continue
        lo = max([j for j in ok if j < i], default=None)
        hi = min([j for j in ok if j > i], default=None)
        if lo is None or hi is None:
            src = fr[lo if hi is None else hi]
            for k in ("g", "a", "l"):
                f[k] = src[k]
            f["b"] = True if f["green"] < 30 else src["b"]
            continue
        u = (i - lo) / (hi - lo)
        a0, a1 = fr[lo]["a"], fr[hi]["a"]
        d = (a1 - a0 + 180) % 360 - 180
        sp = spins.get(f["seg"], 0)
        if sp and abs(d) > 100 and np.sign(d) != sp:
            d += 360 * sp
        f["a"] = a0 + d * u
        f["g"] = [fr[lo]["g"][0] + (fr[hi]["g"][0] - fr[lo]["g"][0]) * u,
                  fr[lo]["g"][1] + (fr[hi]["g"][1] - fr[lo]["g"][1]) * u]
        f["l"] = fr[lo]["l"] + (fr[hi]["l"] - fr[lo]["l"]) * u
        # nearly no green at all: the blade is hidden behind him
        f["b"] = True if f["green"] < 30 else (fr[lo]["b"] if u < 0.5 else fr[hi]["b"])
    return fr


def unwrap(fr, spins):
    """Continuous angles (no 359 -> 0 jumps), so the game can blend between neighbours."""
    for i in range(1, len(fr)):
        d = (fr[i]["a"] - fr[i - 1]["a"] + 180) % 360 - 180
        sp = spins.get(fr[i]["seg"], 0)
        if sp and abs(d) > 120 and np.sign(d) != sp:
            d += 360 * sp
        fr[i]["a"] = fr[i - 1]["a"] + d
    return fr


def finish(strip_path, combo_raw, track_path, seg_path, out_prefix, fps_path, cell_w, cell_h):
    tr = json.load(open(track_path))
    segs = json.load(open(seg_path))
    meta = json.load(open(fps_path))
    raw = np.array(Image.open(combo_raw).convert("RGBA"))
    strip = Image.open(strip_path).convert("RGBA")
    st = np.array(strip)
    fr = tr["frames"]
    n = len(fr)
    spins = meta.get("spins", {})
    fill_gaps(fr, spins)
    # raw (256 cell) -> strip cell: one scale for the strip, an offset per frame (normally the
    # same for all; the build keeps the hair of a high frame inside the cell)
    ks = []
    for j in range(n):
        ra = raw[:, j * SRC:(j + 1) * SRC, 3] > 128
        ca = st[:, j * cell_w:(j + 1) * cell_w, 3] > 128
        if ra.any() and ca.any():
            ks.append(align(ra, ca))
    k = float(np.median(ks))
    out_frames = []
    for j in range(n):
        ra = (raw[:, j * SRC:(j + 1) * SRC, 3] > 128).astype(np.uint8)
        ca = (st[:, j * cell_w:(j + 1) * cell_w, 3] > 128).astype(np.float32)
        rs = cv2.resize(ra, (round(SRC * k), round(SRC * k)), interpolation=cv2.INTER_AREA).astype(np.float32)
        # best offset: phase-free brute force around the bbox guess
        rb, cb = _alpha_bbox(rs > 0.5), _alpha_bbox(ca > 0.5)
        gx, gy = cb[0] - rb[0], cb[3] - rb[3]
        best, bo = -1, (gx, gy)
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                ox, oy = gx + dx, gy + dy
                M = np.float32([[1, 0, ox], [0, 1, oy]])
                w_ = cv2.warpAffine(rs, M, (cell_w, cell_h))
                sc = (w_ * ca).sum() / (w_.sum() + ca.sum() - (w_ * ca).sum() + 1e-6)
                if sc > best:
                    best, bo = sc, (ox, oy)
        f = fr[j]
        # "h": no blade to be seen at all in Sprixen's frame (behind his back, or not yet drawn /
        # put away): the game draws no weapon on that frame
        out_frames.append({"g": [round(f["g"][0] * k + bo[0], 2), round(f["g"][1] * k + bo[1], 2)],
                           "a": round(f["a"], 2), "l": round(f["l"] * k, 2), "b": bool(f["b"]),
                           "h": (not f["ok"]) and f["green"] < 30,
                           "iou": round(float(best), 3)})
    # one continuous angle path through the whole combo
    tmp = [dict(o, seg=fr[j]["seg"]) for j, o in enumerate(out_frames)]
    unwrap(tmp, spins)
    for j, o in enumerate(out_frames):
        o["a"] = round(tmp[j]["a"], 2)
    full_len = float(np.percentile([o["l"] for o in out_frames], 90))
    result = {"full_len": round(full_len, 2), "scale_raw_to_cell": round(k, 4)}
    mask = Image.open(strip_path.replace(".png", "_mask.png")) if os.path.exists(strip_path.replace(".png", "_mask.png")) else None
    j0 = 0
    for name in segs:
        idx = [j for j in range(n) if fr[j]["seg"] == name]
        a, b = idx[0], idx[-1] + 1
        box = (a * cell_w, 0, b * cell_w, cell_h)
        strip.crop(box).save(f"{out_prefix}_{name}.png")
        if mask is not None:
            mask.crop(box).save(f"{out_prefix}_{name}_mask.png")
        hit_frac = meta.get("hit", {}).get(name)
        seg = {"frames": [{k_: v for k_, v in o.items() if k_ != "iou"} for o in out_frames[a:b]]}
        if hit_frac is not None:
            seg["hit"] = int(round(hit_frac * (b - a - 1)))
        result[name] = seg
        j0 = b
    with open(f"{out_prefix}_attack_track.json", "w") as fh:
        json.dump(result, fh, indent=1)
    ious = [o["iou"] for o in out_frames]
    print(f"track: {n} frames, raw->cell scale {k:.3f}, silhouette match min {min(ious):.2f} "
          f"median {np.median(ious):.2f}, full length {full_len:.1f} cell px")
    return result


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "prep":
        prep(*sys.argv[2:6])
    elif cmd == "finish":
        a = sys.argv[2:]
        finish(*a[:6], int(a[6]), int(a[7]))
    else:
        raise SystemExit(__doc__)
