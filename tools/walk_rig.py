"""Articulated side-walk rig for a side-view character sprite.

The character's one good side pose is cut into pieces:
  body | far upper arm, far forearm | near upper arm, near forearm |
  far thigh, far shin, far foot | near thigh, near shin, near foot
Each piece is rotated about its joint (hip, knee, ankle, shoulder, elbow) and chained
with forward kinematics. Every joint angle in every frame comes from the KEYFRAMES table
below, so the motion is specified exactly in code.

Angle convention: degrees from straight down, positive = toward the front (+x, the way
the character faces). Knee and elbow values are bends: knee bends the shin back,
elbow bends the forearm forward. Foot angle is the sole's tilt: positive = toe up.

Usage: python3 walk_rig.py rig.json   -> writes <name>_side_walk_src.png, <name>_walk_spec.md
"""
import json, math, sys
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageEnhance
from scipy import ndimage

# ---------------------------------------------------------------- keyframes
# 8 frames: 0 contact, 1 down, 2 passing, 3 up, 4 contact (other leg), 5 down, 6 passing, 7 up.
# Values are for the NEAR leg/arm. The far side plays the same table 4 frames later.
KEYFRAMES = {
    "thigh":     [22, 14,  0, -16, -32, -24, -4, 14],   # hip angle
    "knee":      [ 0,  8,  2,   0,   4,  26, 50, 28],   # shin bends back from the thigh
    "foot":      [12,  0,  0,  -8, -30, -38, -34, -8],  # sole tilt: heel strike toe-up -> push off toe-down -> toe hangs in swing
    "upper_arm": [-20, -13, 0, 13,  22,  14,  1, -11],  # shoulder angle (opposite to the same-side leg)
    "elbow":     [ 10, 12, 16, 22,  28,  22, 16, 12],   # forearm bends forward from the upper arm
}
FAR_DARKEN = 0.84        # far limbs are slightly darker so they read as behind
N = 8


def deg_dir(a):
    r = math.radians(a)
    return np.array([math.sin(r), math.cos(r)])


def angle_of(p, q):
    d = np.array(q, float) - np.array(p, float)
    return math.degrees(math.atan2(d[0], d[1]))


def main(cfg_path):
    cfg = json.load(open(cfg_path))
    A = np.array(Image.open(cfg["src"]).convert("RGBA"))
    A[A[:, :, 3] < 24] = 0
    H, W = A.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W]
    opaque = A[:, :, 3] > 0
    navy = (A[:, :, 2].astype(int) > A[:, :, 0].astype(int) + 15) & (A[:, :, 2] > 50)

    def poly(pts):
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).polygon([tuple(p) for p in pts], fill=255)
        return np.array(m) > 0

    def biggest(mask, strong=160, grow=2):
        lab, n = ndimage.label(mask & (A[:, :, 3] > strong))
        if n == 0:
            return mask
        sz = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
        main_ = lab == (np.argmax(sz) + 1)
        return mask & ndimage.binary_dilation(main_, iterations=grow)

    J = {k: np.array(v, float) for k, v in cfg["joints"].items()}

    # ---- arms (polygons from the config, minus the navy cravat / pants)
    far_arm = biggest(opaque & poly(cfg["far_arm_poly"]) & ~navy)
    near_arm = biggest(opaque & poly(cfg["near_arm_poly"]) & ~navy)

    # ---- legs: split below the crotch into two components, hip band by x
    cy = cfg["crotch_y"]; lt = cfg["leg_top"]; cx = cfg["crotch_x"]
    strong = (A[:, :, 3] > 160) & (yy >= cy)
    lab, n = ndimage.label(strong)
    sz = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
    ids = list(np.argsort(sz)[::-1][:2] + 1)
    cents = [np.nonzero(lab == k)[1].mean() for k in ids]
    far_id, near_id = (ids[0], ids[1]) if cents[0] < cents[1] else (ids[1], ids[0])
    keep = np.isin(lab, [far_id, near_id])
    _, (iy, ix) = ndimage.distance_transform_edt(~keep, return_indices=True)
    nl = lab[iy, ix]
    below = opaque & (yy >= cy) & ~far_arm & ~near_arm
    band = opaque & (yy >= lt) & (yy < cy) & ~far_arm & ~near_arm & (xx > cfg["band_x"][0]) & (xx < cfg["band_x"][1])
    far_leg = (below & (nl == far_id)) | (band & (xx < cx))
    near_leg = (below & (nl == near_id)) | (band & (xx >= cx))

    # ---- split a limb into pieces with lines perpendicular to its bones
    def side_of(point, a, b):
        """>0 if pixels are past the line through `point` perpendicular to a->b (toward b)."""
        d = (b - a) / np.linalg.norm(b - a)
        return (xx - point[0]) * d[0] + (yy - point[1]) * d[1]

    def split3(mask, hip, knee, ankle, overlap=4):
        past_knee = side_of(knee, hip, knee)
        past_ankle = side_of(ankle, knee, ankle)
        thigh = mask & (past_knee < overlap)
        shin = mask & (past_knee >= -1) & (past_ankle < 1)
        foot = mask & (past_ankle >= -overlap)
        return thigh, shin, foot

    def split2(mask, shoulder, elbow, overlap=3):
        past = side_of(elbow, shoulder, elbow)
        return mask & (past < overlap), mask & (past >= -1)

    def split_leg(mask, s):
        """Thigh = trouser pixels, shin/foot = boot pixels (split exactly along the boot cuff).
        Knee joint = centre of the seam between trousers and boot; ankle = centre of the boot
        cross-section at the configured ankle height."""
        cloth = mask & navy
        boot_core = mask & ~navy & (A[:, :, :3].max(axis=2) > 70)
        both = cloth | boot_core
        _, (iy2, ix2) = ndimage.distance_transform_edt(~both, return_indices=True)
        is_cloth = cloth[iy2, ix2]
        thigh = mask & is_cloth
        boot = mask & ~is_cloth
        seam = boot & ndimage.binary_dilation(thigh, iterations=2)
        sy, sx = np.nonzero(seam)
        knee = np.array([sx.mean(), sy.mean()])
        hip, ank_guess = J[s + "_hip"], J[s + "_ankle"]
        # ankle: centre of the boot along the line perpendicular to the shin at the guessed height
        d = (ank_guess - knee) / np.linalg.norm(ank_guess - knee)
        perp = np.array([-d[1], d[0]])
        pts = [ank_guess + perp * t for t in range(-40, 41)]
        on = [p for p in pts if 0 <= int(p[1]) < H and 0 <= int(p[0]) < W and boot[int(p[1]), int(p[0])]]
        ankle = np.mean(on, axis=0) if on else ank_guess
        past_ankle = side_of(ankle, knee, ankle)
        shin = boot & (past_ankle < 2)
        foot = boot & (past_ankle >= -3)
        thigh_ext = thigh | (boot & ndimage.binary_dilation(thigh, iterations=3))   # tuck under the cuff
        J[s + "_knee"] = knee
        J[s + "_ankle"] = ankle
        return thigh_ext, shin, foot

    fT, fS, fF = split_leg(far_leg, "far")
    nT, nS, nF = split_leg(near_leg, "near")
    fU, fL = split2(far_arm, J["far_shoulder"], J["far_elbow"])
    nU, nL = split2(near_arm, J["near_shoulder"], J["near_elbow"])

    # ---- body: everything else; patch the hole the near arm leaves on the torso
    body = opaque & ~far_arm & ~near_arm & ~far_leg & ~near_leg
    body |= band & (yy < lt + 6)
    body &= ~((yy >= lt + 6) & (xx >= cfg["band_x"][0] - 14) & (xx <= cfg["band_x"][1] + 6))
    body_img = A.copy()
    body_img[~body] = 0
    torso = poly(cfg["torso_poly"])
    hole = far_arm & torso   # far arm goes behind the torso: repaint the torso where it was
    if hole.any():
        rgb = cv2.cvtColor(A[:, :, :3], cv2.COLOR_RGB2BGR)
        filled = cv2.inpaint(rgb, (hole * 255).astype(np.uint8), 5, cv2.INPAINT_TELEA)
        filled = cv2.cvtColor(filled, cv2.COLOR_BGR2RGB)
        body_img[hole, :3] = filled[hole]
        body_img[hole, 3] = 255
    # pants-colored pelvis underlay so swinging thighs never open a gap
    pants_px = A[(A[:, :, 3] > 200) & near_leg & (yy > cy) & (yy < cy + 20)]
    pc = tuple(int(c) for c in np.median(pants_px[:, :3], axis=0)) + (255,)
    under = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hx = (J["far_hip"][0] + J["near_hip"][0]) / 2
    ImageDraw.Draw(under).ellipse([hx - 17, lt - 6, hx + 17, cy - 2], fill=pc)
    under.alpha_composite(Image.fromarray(body_img))
    body_layer = under

    def piece(mask, dark=1.0):
        a = A.copy()
        a[~mask] = 0
        if dark != 1.0:
            a[:, :, :3] = (a[:, :, :3] * dark).astype(np.uint8)
        return Image.fromarray(a)

    # natural (as-drawn) angles of every bone
    nat = {}
    for s in ("far", "near"):
        nat[s + "_thigh"] = angle_of(J[s + "_hip"], J[s + "_knee"])
        nat[s + "_shin"] = angle_of(J[s + "_knee"], J[s + "_ankle"])
        nat[s + "_upper"] = angle_of(J[s + "_shoulder"], J[s + "_elbow"])
        nat[s + "_fore"] = angle_of(J[s + "_elbow"], J[s + "_wrist"])
    L = {s + "_" + k: np.linalg.norm(J[s + "_" + b] - J[s + "_" + a])
         for s in ("far", "near") for k, a, b in (("thigh", "hip", "knee"), ("shin", "knee", "ankle"),
                                                   ("upper", "shoulder", "elbow"))}

    def sole_angle(mask, ankle):
        """Tilt of the bottom edge of the foot piece (deg, + = toe up)."""
        ys, xs = np.nonzero(mask & (A[:, :, 3] > 160))
        cols = {}
        for x_, y_ in zip(xs, ys):
            cols[x_] = max(cols.get(x_, -1), y_)
        xs_ = np.array(sorted(cols)); ys_ = np.array([cols[x_] for x_ in xs_])
        lo, hi = np.percentile(xs_, 15), np.percentile(xs_, 85)
        sel = (xs_ >= lo) & (xs_ <= hi)
        k = np.polyfit(xs_[sel], ys_[sel], 1)[0]
        return -math.degrees(math.atan(k))
    nat["far_foot"] = sole_angle(fF, J["far_ankle"])
    nat["near_foot"] = sole_angle(nF, J["near_ankle"])

    P = {
        "far": dict(T=piece(fT, FAR_DARKEN), S=piece(fS, FAR_DARKEN), F=piece(fF, FAR_DARKEN),
                    U=piece(fU, FAR_DARKEN), Lo=piece(fL, FAR_DARKEN)),
        "near": dict(T=piece(nT), S=piece(nS), F=piece(nF), U=piece(nU), Lo=piece(nL)),
    }

    PAD = 80
    CW, CH = W + 2 * PAD, H + 2 * PAD

    def put(canvas, img, src_joint, dst_joint, rot, clip_hip=None):
        """Rotate img about src_joint by rot degrees (CCW = toward front for hanging limbs),
        then move src_joint onto dst_joint."""
        big = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        big.alpha_composite(img, (PAD, PAD))
        c = (src_joint[0] + PAD, src_joint[1] + PAD)
        big = big.rotate(rot, resample=Image.BICUBIC, center=c)
        dx, dy = dst_joint[0] - src_joint[0], dst_joint[1] - src_joint[1]
        big = big.transform(big.size, Image.AFFINE, (1, 0, -dx, 0, 1, -dy), resample=Image.BICUBIC)
        if clip_hip is not None:
            a = np.array(big)
            Y, X = np.mgrid[0:CH, 0:CW]
            inside = ((X - (hx + PAD)) / 26.0) ** 2 + ((Y - (clip_hip + PAD)) / 15.0) ** 2 <= 1.0
            a[(Y < clip_hip + PAD + 4) & ~inside] = 0
            big = Image.fromarray(a)
        canvas.alpha_composite(big)

    def kf(name, i):
        return KEYFRAMES[name][i % N]

    def draw_leg(canvas, s, i, info):
        hip = J[s + "_hip"]
        th = kf("thigh", i); sh = th - kf("knee", i); ft = kf("foot", i)
        knee = hip + deg_dir(th) * L[s + "_thigh"]
        ankle = knee + deg_dir(sh) * L[s + "_shin"]
        put(canvas, P[s]["T"], J[s + "_hip"], hip, th - nat[s + "_thigh"], clip_hip=hip[1])
        put(canvas, P[s]["F"], J[s + "_ankle"], ankle, ft - nat[s + "_foot"])
        put(canvas, P[s]["S"], J[s + "_knee"], knee, sh - nat[s + "_shin"])
        info[s] = dict(knee=knee, ankle=ankle)

    def draw_arm(canvas, s, i):
        sh_ = J[s + "_shoulder"]
        up = kf("upper_arm", i); fo = up + kf("elbow", i)
        if s == "far" and cfg.get("far_upper_fixed"):
            up = nat[s + "_upper"]   # upper arm hidden behind the torso: only the forearm swings
        elbow = sh_ + deg_dir(up) * L[s + "_upper"]
        put(canvas, P[s]["U"], J[s + "_shoulder"], sh_, up - nat[s + "_upper"])
        put(canvas, P[s]["Lo"], J[s + "_elbow"], elbow, fo - nat[s + "_fore"])

    frames, infos = [], []
    for i in range(N):
        c = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        info = {}
        draw_arm(c, "far", i + 4)
        draw_leg(c, "far", i + 4, info)
        c.alpha_composite(body_layer, (PAD, PAD))
        draw_leg(c, "near", i, info)
        draw_arm(c, "near", i)
        frames.append(c); infos.append(info)

    # ground the planted foot: lowest opaque pixel of each frame sits on one baseline
    out, bobs, bottoms = [], [], []
    for f in frames:
        a = np.array(f)[:, :, 3] > 100
        bottoms.append(np.nonzero(a.any(1))[0].max())
    base = max(bottoms)
    for f, b in zip(frames, bottoms):
        g = Image.new("RGBA", f.size, (0, 0, 0, 0))
        g.alpha_composite(f, (0, int(base - b)))
        out.append(g); bobs.append(int(base - b))
    # crop all frames identically
    box = None
    for g in out:
        bb = g.getbbox()
        box = bb if box is None else (min(box[0], bb[0]), min(box[1], bb[1]), max(box[2], bb[2]), max(box[3], bb[3]))
    box = (box[0] - 6, box[1] - 6, box[2] + 6, box[3] + 2)
    fw, fh = box[2] - box[0], box[3] - box[1]
    strip = Image.new("RGBA", (fw * N, fh), (0, 0, 0, 0))
    for k, g in enumerate(out):
        strip.alpha_composite(g.crop(box), (k * fw, 0))
    name = cfg["name"]
    strip.save(f"{name}_side_walk_src.png")
    head_x = J["head"][0] + PAD - box[0]
    json.dump({"frame_w": fw, "frame_h": fh, "count": N, "head_x": head_x}, open(f"{name}_side_walk_src.json", "w"))

    # parts debug image
    dbg = np.zeros((H, W, 4), np.uint8)
    colors = [(body, (190, 190, 190)), (fT, (40, 40, 200)), (fS, (90, 90, 255)), (fF, (160, 160, 255)),
              (nT, (20, 140, 20)), (nS, (60, 200, 60)), (nF, (150, 240, 150)),
              (fU, (200, 40, 40)), (fL, (255, 120, 120)), (nU, (220, 150, 0)), (nL, (255, 210, 80))]
    for m, col in colors:
        dbg[m] = col + (255,)
    Image.fromarray(dbg).save(f"{name}_parts_debug.png")

    # ---- spec sheet: exact numbers per frame
    stride = []
    for i, inf in enumerate(infos):
        stride.append(abs(inf["near"]["ankle"][0] - inf["far"]["ankle"][0]))
    lift = []
    for i, inf in enumerate(infos):
        ys = [inf[s]["ankle"][1] for s in ("near", "far")]
        lift.append(abs(ys[0] - ys[1]))
    names = ["contact", "down", "passing", "up", "contact", "down", "passing", "up"]
    lines = [f"# {name.capitalize()} side walk: exact keyframes", "",
             "Angles in degrees from straight down; + = toward the front. Knee = shin bends back; "
             "elbow = forearm bends forward; foot = sole tilt (+ toe up). Far limbs play the same "
             "values 4 frames later. Distances are in source-art pixels (the game cell is about 0.5x).", "",
             "| Frame | Pose | Near thigh | Near knee | Near foot | Far thigh | Far knee | Far foot | Near arm | Near elbow | Far arm | Far elbow | Body lowered (px) | Ankle gap (px) | Foot lift (px) |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i in range(N):
        lines.append(f"| {i} | {names[i]} | {kf('thigh', i)} | {kf('knee', i)} | {kf('foot', i)} | "
                     f"{kf('thigh', i + 4)} | {kf('knee', i + 4)} | {kf('foot', i + 4)} | "
                     f"{kf('upper_arm', i)} | {kf('elbow', i)} | {kf('upper_arm', i + 4)} | {kf('elbow', i + 4)} | "
                     f"{bobs[i] - min(bobs)} | {stride[i]:.0f} | {lift[i]:.0f} |")
    lines += ["", "Bone lengths (source px): " + ", ".join(f"{k} {v:.0f}" for k, v in sorted(L.items())),
              "", "As-drawn angles of the source pose: " + ", ".join(f"{k} {v:.0f}" for k, v in sorted(nat.items()))]
    open(f"{name}_walk_spec.md", "w").write("\n".join(lines) + "\n")
    print("ok", strip.size, "bobs", bobs)


if __name__ == "__main__":
    main(sys.argv[1])
