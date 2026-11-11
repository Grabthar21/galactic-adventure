"""Side walk from separately drawn cut-out parts (no warping: every part keeps its drawn
size and shape and only rotates about its joint).

Parts come from a parts sheet (one transparent PNG, parts separated by space). Each part
is located by a box in parts.json and cleaned to its largest connected piece. Joints are
measured automatically from each part's outline (top/bottom centres, sole ends) unless
overridden in parts.json.

Motion: the reference walk's traced foot path, foot lift, fist path and head bob
(ref_walk_tracking.json), scaled to these limb lengths.
  * legs: 2-bone IK (thigh, boot). The boot is rigid, so the foot rolls heel-to-toe with
    the shin, and the leg is lowered/raised so the lowest point of the sole sits exactly on
    the ground while planted
  * arms: 2-bone IK with the elbow pointing back, nearly straight when trailing and bent
    with the fist at the chest when leading
  * body: hips follow the traced bob, never so high that a planted leg over-stretches

Usage: python3 cutout_walk.py parts.json  ->  <name>_cutout_walk_src.png/.json, <name>_cutout_stand_src.png
"""
import json, math, sys
import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.interpolate import CubicSpline

DEFAULT = dict(frames=12, stride_ratio=0.95, lift_ratio=0.30, bob_ratio=0.055,
               reach_back=0.97, reach_fwd=0.55, far_back_scale=0.55, stance_fwd_ratio=0.03,
               far_dark=0.82, ss=1, fist_min_drop=0.35)


def periodic_curve(values, harmonics=None):
    v = np.asarray(values, float); n = len(v)
    if harmonics is not None:
        c = np.fft.rfft(v); c[harmonics + 1:] = 0; v = np.fft.irfft(c, n)
    cs = CubicSpline(np.arange(n + 1) / n, np.append(v, v[0]), bc_type="periodic")
    return lambda p: float(cs(p % 1.0))


def ddir(a):
    r = math.radians(a); return np.array([math.sin(r), math.cos(r)])


def ang(p, q):
    d = np.asarray(q, float) - np.asarray(p, float); return math.degrees(math.atan2(d[0], d[1]))


def rotv(v, deg):
    r = math.radians(deg); c, s = math.cos(r), math.sin(r)
    return np.array([c * v[0] + s * v[1], -s * v[0] + c * v[1]])


class Part:
    def __init__(self, img, joints, name):
        self.img = img; self.j = {k: np.array(v, float) for k, v in joints.items()}; self.name = name


def load_parts(cfg):
    sheet = np.array(Image.open(cfg["sheet"]).convert("RGBA"))
    sheet[sheet[:, :, 3] < 40] = 0
    parts = {}
    for name, box in cfg["boxes"].items():
        x0, y0, x1, y1 = box
        a = sheet[y0:y1, x0:x1].copy()
        lab, n = ndimage.label(a[:, :, 3] > 100)
        sz = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
        keep = ndimage.binary_dilation(lab == (np.argmax(sz) + 1), iterations=2)
        a[~keep] = 0
        parts[name] = a
    return parts


def row_center(mask, y):
    xs = np.nonzero(mask[int(y)])[0]
    return np.array([xs.mean(), y]) if len(xs) else None


def auto_joints(kind, a):
    m = a[:, :, 3] > 100
    ys, xs = np.nonzero(m); top, bot = ys.min(), ys.max(); h = bot - top
    if kind == "thigh":
        return {"hip": row_center(m, top + 0.10 * h), "knee": row_center(m, bot - 0.08 * h)}
    if kind == "boot":
        low = ys >= bot - 5
        return {"knee": row_center(m, top + 0.07 * h), "ankle": row_center(m, top + 0.72 * h),
                "heel": np.array([xs[low].min(), bot]), "toe": np.array([xs[low].max(), bot])}
    if kind == "uarm":
        return {"shoulder": row_center(m, top + 0.10 * h), "elbow": row_center(m, top + 0.67 * h),
                "tip": np.array([xs[ys >= bot - 3].mean(), bot])}
    if kind == "hand":
        return {"top": row_center(m, top + 0.05 * h), "wrist": row_center(m, top + 0.52 * h),
                "end": row_center(m, bot - 0.05 * h)}
    raise ValueError(kind)


def build_forearm(uarm, hand, ju, jh, split_y):
    """Upper arm = sleeve (above the cuff line); forearm = the skin below the cuff plus the
    bracer/hand piece, rotated to continue the forearm's line and overlapping its tip."""
    H, W = uarm.shape[:2]
    upper = uarm.copy(); upper[int(split_y) + 6:] = 0                 # sleeve keeps 6px under the cuff
    stub = uarm.copy(); stub[:int(split_y) - 2] = 0
    ys, xs = np.nonzero(stub[:, :, 3] > 100)
    stub_axis_from = np.array([xs[ys < ys.min() + 8].mean(), ys.min()])
    tip = ju["tip"]
    stub_ang = ang(stub_axis_from, tip)
    hand_ang = ang(jh["top"], jh["wrist"])
    rot = stub_ang - hand_ang
    attach = stub_axis_from + (tip - stub_axis_from) * 0.78           # bracer covers the stub's taper
    pad = 220
    canvas = Image.new("RGBA", (W + 2 * pad, H + 2 * pad), (0, 0, 0, 0))
    canvas.alpha_composite(Image.fromarray(stub), (pad, pad))
    hp = Image.fromarray(hand)
    big = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    big.alpha_composite(hp, (int(round(attach[0] - jh["top"][0] + pad)), int(round(attach[1] - jh["top"][1] + pad))))
    big = big.rotate(rot, resample=Image.BICUBIC, center=(attach[0] + pad, attach[1] + pad))
    canvas.alpha_composite(big)
    wrist = attach + rotv(jh["wrist"] - jh["top"], rot)
    end = attach + rotv(jh["end"] - jh["top"], rot)
    return upper, np.array(canvas), pad, {"elbow": ju["elbow"] + pad, "wrist": wrist + pad, "end": end + pad}


def main(path):
    cfg = json.load(open(path))
    M = dict(DEFAULT, **cfg.get("motion", {}))
    P = load_parts(cfg)
    J = {}
    for side in ("near", "far"):
        J["thigh_" + side] = auto_joints("thigh", P["thigh_" + side])
        J["boot_" + side] = auto_joints("boot", P["boot_" + side])
        J["uarm_" + side] = auto_joints("uarm", P["uarm_" + side])
        J["hand_" + side] = auto_joints("hand", P["hand_" + side])
    for k, v in cfg.get("joints", {}).items():           # manual overrides "part.joint": [x, y]
        part, jn = k.split(".")
        J.setdefault(part, {})[jn] = np.array(v, float)

    # arms: split sleeve / forearm and assemble forearm+hand
    ARM = {}
    for side in ("near", "far"):
        up, fore, pad, fj = build_forearm(P["uarm_" + side], P["hand_" + side], J["uarm_" + side], J["hand_" + side],
                                          J["uarm_" + side]["elbow"][1])
        ARM[side] = dict(upper=up, fore=fore, pad=pad, shoulder=J["uarm_" + side]["shoulder"],
                         elbow=J["uarm_" + side]["elbow"], f_elbow=fj["elbow"], f_wrist=fj["wrist"], f_end=fj["end"])

    def dark(a, f):
        b = a.copy(); b[:, :, :3] = (b[:, :, :3] * f).astype(np.uint8); return b

    TJ = {k: np.array(v, float) for k, v in cfg["torso_joints"].items()}
    HJ = {k: np.array(v, float) for k, v in cfg["head_joints"].items()}

    # ---------- bone lengths & natural angles
    def leg_geom(side):
        t, b = J["thigh_" + side], J["boot_" + side]
        return dict(l1=np.linalg.norm(t["knee"] - t["hip"]), l2=np.linalg.norm(b["ankle"] - b["knee"]),
                    th_nat=ang(t["hip"], t["knee"]), sh_nat=ang(b["knee"], b["ankle"]))
    LG = {s: leg_geom(s) for s in ("near", "far")}

    def arm_geom(side):
        A = ARM[side]
        return dict(l1=np.linalg.norm(A["elbow"] - A["shoulder"]), l2=np.linalg.norm(A["f_wrist"] - A["f_elbow"]),
                    up_nat=ang(A["shoulder"], A["elbow"]), fo_nat=ang(A["f_elbow"], A["f_wrist"]))
    AG = {s: arm_geom(s) for s in ("near", "far")}
    leg_len = LG["near"]["l1"] + LG["near"]["l2"]

    # ---------- reference curves
    REF = json.load(open(cfg["reference"]))
    fx = np.array(REF["near_foot_x_rel_hip"], float); fl = np.array(REF["near_foot_lift"], float)
    foot_x = periodic_curve(fx); foot_l = periodic_curve(fl)
    arm_x = periodic_curve(REF["near_fist_x_rel_shoulder"], harmonics=2)
    arm_y = periodic_curve(REF["near_fist_y_below_shoulder"], harmonics=2)
    top = np.array(REF["head_top_y"], float); down = top - top.min(); half = (down[:5] + down[5:]) / 2
    bobc = periodic_curve(np.concatenate([half, half]), harmonics=4)
    sx = M["stride_ratio"] * leg_len / (fx.max() - fx.min())
    sl = M["lift_ratio"] * leg_len / max(fl.max(), 1e-6)
    bob_amp = M["bob_ratio"] * leg_len * 2.0

    # ---------- world layout: torso fixed (plus bob); ground set from the standing pose
    def torso_pt(name, bob):
        return TJ[name] + np.array([0.0, bob])

    def ik(hip, tgt, l1, l2, knee_fwd=True):
        dv = tgt - hip; d = min(np.linalg.norm(dv), (l1 + l2) * 0.999); base = math.degrees(math.atan2(dv[0], dv[1]))
        a = math.degrees(math.acos(max(-1, min(1, (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)))))
        th = base + a if knee_fwd else base - a
        mid = hip + ddir(th) * l1
        return th, ang(mid, tgt), mid

    def sole_low(side, sh):
        b = J["boot_" + side]; rot = sh - LG[side]["sh_nat"]
        return max(rotv(b["heel"] - b["ankle"], rot)[1], rotv(b["toe"] - b["ankle"], rot)[1])

    # standing reference: ground = where a vertical-ish leg puts the sole
    hip0 = TJ["hip_near"]
    stand_ankle = hip0 + np.array([0.0, leg_len * 0.985])
    GROUND = stand_ankle[1] + sole_low("near", 0.0 + 0.0)

    def leg_pose(side, p, bob, stand=False):
        hip = torso_pt("hip_" + side, bob)
        lg = LG[side]
        if stand:
            x_off, lift = M["stance_fwd_ratio"] * leg_len, 0.0
        else:
            x_off = M["stance_fwd_ratio"] * leg_len + foot_x(p) * sx
            lift = max(foot_l(p), 0.0) * sl
        tgt = np.array([TJ["hip_" + side][0] + x_off, 0.0])
        # solve for ankle height so the lowest sole point is on the ground (+ lift)
        y = GROUND - lift - 20
        for _ in range(6):
            tgt[1] = y
            th, sh, knee = ik(hip, tgt, lg["l1"], lg["l2"])
            y = GROUND - lift - sole_low(side, sh)
        tgt[1] = y
        th, sh, knee = ik(hip, tgt, lg["l1"], lg["l2"])
        return dict(hip=hip, knee=knee, ankle=knee + ddir(sh) * lg["l2"], th=th, sh=sh, lift=lift,
                    reach=np.linalg.norm(tgt - hip) / (lg["l1"] + lg["l2"]))

    def min_down(p):
        need = -1e9
        for side, ph in (("near", p), ("far", p + 0.5)):
            if foot_l(ph) > 0.3:
                continue
            lg = LG[side]; hip0_ = TJ["hip_" + side]
            # find the smallest bob for which the planted leg reaches with 2% slack
            for b in np.linspace(-0.25 * leg_len, 0.25 * leg_len, 121):
                pose = leg_pose(side, ph, b)
                if pose["reach"] < 0.975:
                    need = max(need, b); break
        return need

    S = 96
    raw = np.array([max((bobc(k / S) / max(half.max(), 1e-6) - 0.5) * bob_amp, min_down(k / S)) for k in range(S)])
    md = np.array([min_down(k / S) for k in range(S)])
    md = np.maximum(md, np.roll(md, S // 2))          # both steps get the same bob
    raw = np.maximum(raw, np.roll(raw, S // 2))
    for _ in range(6):
        c = np.fft.rfft(raw); c[1::2] = 0; c[7:] = 0      # keep only the twice-per-cycle rhythm
        raw = np.maximum(np.fft.irfft(c, S), md)
    bob_c = periodic_curve(raw)

    def arm_pose(side, p, bob, stand=False):
        A, ag = ARM[side], AG[side]
        sh_ = torso_pt("shoulder_" + side, bob)
        L = ag["l1"] + ag["l2"]
        if stand:
            hand = sh_ + np.array([0.04 * L, 0.97 * L])
        else:
            k = L / 7.4
            ax = arm_x(p) * k
            if side == "far" and ax < 0:
                ax *= M["far_back_scale"]
            dv = np.array([ax, arm_y(p) * k]); f = max(-1, min(1, dv[0] / (0.6 * L)))
            reach = M["reach_back"] + (M["reach_fwd"] - M["reach_back"]) * (f + 1) / 2
            hand = sh_ + dv / max(np.linalg.norm(dv), 1e-6) * L * reach
            # leading fist rides at the chest/belly, never up at shoulder height
            hand[1] = max(hand[1], sh_[1] + M["fist_min_drop"] * L)
        up, fo, elbow = ik(sh_, hand, ag["l1"], ag["l2"], knee_fwd=False)
        return dict(shoulder=sh_, elbow=elbow, up=up, fo=fo)

    # ---------- rendering
    PAD = 300
    OW = int(TJ["canvas"][0]) + 2 * PAD; OH = int(TJ["canvas"][1]) + 2 * PAD

    def put(canvas, arr, src_joint, dst_joint, rot):
        img = Image.fromarray(arr)
        big = Image.new("RGBA", (OW, OH), (0, 0, 0, 0))
        off = (dst_joint[0] + PAD - src_joint[0], dst_joint[1] + PAD - src_joint[1])
        # rotate about the joint: place, then rotate around the destination joint
        big.alpha_composite(img, (0, 0))
        big = big.transform(big.size, Image.AFFINE, (1, 0, -off[0], 0, 1, -off[1]), resample=Image.BICUBIC)
        big = big.rotate(rot, resample=Image.BICUBIC, center=(dst_joint[0] + PAD, dst_joint[1] + PAD))
        canvas.alpha_composite(big)

    def draw(p, bob, stand=False):
        c = Image.new("RGBA", (OW, OH), (0, 0, 0, 0))
        info = {}
        for side in ("far", "near"):
            ph = p if side == "near" else p + 0.5
            info["leg_" + side] = leg_pose(side, ph, bob, stand)
            info["arm_" + side] = arm_pose(side, ph, bob, stand)
        fd = M["far_dark"]

        def arm(side):
            A, ag, ap = ARM[side], AG[side], info["arm_" + side]
            fore = A["fore"] if side == "near" else dark(A["fore"], fd)
            upper = A["upper"] if side == "near" else dark(A["upper"], fd)
            put(c, fore, A["f_elbow"], ap["elbow"], ap["fo"] - ag["fo_nat"])
            put(c, upper, A["shoulder"], ap["shoulder"], ap["up"] - ag["up_nat"])

        def leg(side):
            lp, lg = info["leg_" + side], LG[side]
            th_img = P["thigh_" + side] if side == "near" else dark(P["thigh_" + side], fd)
            bt_img = P["boot_" + side] if side == "near" else dark(P["boot_" + side], fd)
            put(c, th_img, J["thigh_" + side]["hip"], lp["hip"], lp["th"] - lg["th_nat"])
            put(c, bt_img, J["boot_" + side]["knee"], lp["knee"], lp["sh"] - lg["sh_nat"])

        arm("far")
        leg("far")
        leg("near")
        put(c, P["torso"], np.array([0.0, 0.0]), np.array([0.0, bob]), 0.0)
        put(c, P["head"], HJ["neck"], torso_pt("neck", bob), 0.0)
        arm("near")
        return c, info

    N = int(M["frames"])
    frames, infos, bobs = [], [], []
    for i in range(N):
        p = i / N; b = bob_c(p)
        f, inf = draw(p, b); frames.append(f); infos.append(inf); bobs.append(b)
    stand, _ = draw(0.0, 0.0, stand=True)

    allf = frames + [stand]
    box = None
    for f in allf:
        bb = f.getbbox(); box = bb if box is None else (min(box[0], bb[0]), min(box[1], bb[1]), max(box[2], bb[2]), max(box[3], bb[3]))
    box = (box[0] - 4, box[1] - 4, box[2] + 4, int(GROUND + PAD) + 2)
    fw, fh = box[2] - box[0], box[3] - box[1]
    strip = Image.new("RGBA", (fw * N, fh), (0, 0, 0, 0))
    for k, f in enumerate(frames):
        strip.alpha_composite(f.crop(box), (k * fw, 0))
    name = cfg["name"]
    strip.save(f"{name}_cutout_walk_src.png")
    stand.crop(box).save(f"{name}_cutout_stand_src.png")
    head_x = TJ["neck"][0] + PAD - box[0]
    travel = 2 * (foot_x(0.0) - foot_x(0.5)) * sx
    json.dump({"frame_w": fw, "frame_h": fh, "count": N, "head_x": head_x, "ground_y": GROUND + PAD - box[1],
               "cycle_travel_src": travel, "leg_len": leg_len}, open(f"{name}_cutout_walk_src.json", "w"))
    print("ok", strip.size, "bob", [round(b, 1) for b in bobs], "leg", round(leg_len, 1))


if __name__ == "__main__":
    main(sys.argv[1])
