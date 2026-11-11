"""Smooth side-walk generator: skinned mesh deformation + foot IK.

Why this instead of cutting pieces: every layer (far arm, far leg, body, near leg, near arm)
is warped as ONE continuous mesh. Each mesh point follows a blend of nearby bones, like
Spine / Live2D skinning, so knees and elbows bend without gaps and limbs stay attached.

Motion is planned, not hand-posed per frame:
  * each ankle follows a planned path: during stance it slides back along the ground at
    a constant speed (so the foot never skates), during swing it lifts in a smooth arc
  * 2-bone IK turns each ankle target into hip and knee angles
  * the sole tilts for heel strike and toe-off, and the lowest point of the foot always
    touches the ground line
  * the hips bob on a smooth curve twice per cycle (low at contact, high after passing)
  * the arms swing opposite to the legs with an elbow bend
Reference (Ozzbit "male hero" walk): contact frames have the widest stance, body is lowest
at contact and highest just after passing, bob is about 5% of height.

Usage: python3 walk_skin.py rig.json
Writes <name>_side_walk_src.png/.json and <name>_walk_spec.md
"""
import json, math, sys
import numpy as np
import cv2
from PIL import Image, ImageDraw
from scipy import ndimage

# ------------------------------------------------------------------ motion settings
MOTION = dict(
    frames=12,           # frames per full cycle (two steps)
    stride=104.0,        # ankle travel during one stance, in source px (about 1.15x leg length)
    duty=0.56,           # fraction of the cycle a foot is on the ground
    lift=20.0,           # how high the swinging ankle rises (source px)
    stance_fwd=6.0,      # the stance is centred this far in front of the hip
    heel_strike=12.0,    # sole tilt at contact (deg, + = toe up)
    toe_off=-30.0,       # sole tilt as the foot leaves the ground
    bob=6.5,             # hip bob amplitude (source px); total travel = 2x
    bob_phase=0.06,      # highest point comes a little after passing
    arm_swing=24.0,      # near upper-arm swing (deg each way)
    elbow_base=16.0,     # elbow bend at rest (deg)
    elbow_swing=14.0,    # extra elbow bend when the arm swings forward
    far_fore_swing=20.0, # far forearm swing about the elbow (deg each way)
    arm_lag=0.04,        # arms trail the legs slightly
    far_dark=0.86,       # far limbs a touch darker
    ankle_min=-24.0,     # how far the foot may point down relative to the shin (deg)
    ankle_max=16.0,      # how far it may flex up
)


def ddir(a):
    r = math.radians(a)
    return np.array([math.sin(r), math.cos(r)])


def ang(p, q):
    d = np.asarray(q, float) - np.asarray(p, float)
    return math.degrees(math.atan2(d[0], d[1]))


def rot(v, deg):
    """Rotate vectors v (N,2) by deg in the 'from straight down, + = forward' convention."""
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return np.stack([c * v[:, 0] + s * v[:, 1], -s * v[:, 0] + c * v[:, 1]], axis=1)


def smooth(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def seg_dist(P, a, b):
    ab = b - a
    t = np.clip(((P - a) @ ab) / max(ab @ ab, 1e-9), 0, 1)
    return np.linalg.norm(P - (a + t[:, None] * ab), axis=1)


def main(cfg_path):
    cfg = json.load(open(cfg_path))
    M = dict(MOTION, **cfg.get("motion", {}))
    A = np.array(Image.open(cfg["src"]).convert("RGBA"))
    A[A[:, :, 3] < 24] = 0
    H, W = A.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W]
    opaque = A[:, :, 3] > 0
    navy = (A[:, :, 2].astype(int) > A[:, :, 0].astype(int) + 15) & (A[:, :, 2] > 50)
    J = {k: np.array(v, float) for k, v in cfg["joints"].items()}

    def poly(pts):
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).polygon([tuple(p) for p in pts], fill=255)
        return np.array(m) > 0

    def biggest(mask, grow=2):
        lab, n = ndimage.label(mask & (A[:, :, 3] > 160) & ~(A[:, :, :3].max(axis=2) < 45))
        if n == 0:
            return mask
        sz = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
        return mask & ndimage.binary_dilation(lab == (np.argmax(sz) + 1), iterations=grow)

    # ------------------------------------------------ segmentation
    near_arm = biggest(opaque & poly(cfg["near_arm_poly"]) & ~navy)
    far_arm = biggest(opaque & poly(cfg["far_arm_poly"]) & ~navy)
    cy, lt, cx = cfg["crotch_y"], cfg["leg_top"], cfg["crotch_x"]
    lab, n = ndimage.label((A[:, :, 3] > 160) & (yy >= cy))
    sz = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
    ids = list(np.argsort(sz)[::-1][:2] + 1)
    cents = [np.nonzero(lab == k)[1].mean() for k in ids]
    far_id, near_id = (ids[0], ids[1]) if cents[0] < cents[1] else (ids[1], ids[0])
    _, (iy, ix) = ndimage.distance_transform_edt(~np.isin(lab, [far_id, near_id]), return_indices=True)
    nl = lab[iy, ix]
    below = opaque & (yy >= cy) & ~far_arm & ~near_arm
    band = opaque & (yy >= lt - 5) & (yy < cy) & ~far_arm & ~near_arm & (xx > cfg["band_x"][0]) & (xx < cfg["band_x"][1])
    legs = {"far": (below & (nl == far_id)) | (band & (xx < cx)),
            "near": (below & (nl == near_id)) | (band & (xx >= cx))}

    # knee = centre of the trouser/boot seam; ankle = centre of the boot at the given height;
    # toe/heel = ends of the sole
    foot_pts = {}
    for s in ("far", "near"):
        m = legs[s]
        cloth = m & navy
        bootc = m & ~navy & (A[:, :, :3].max(axis=2) > 70)
        _, (i2, j2) = ndimage.distance_transform_edt(~(cloth | bootc), return_indices=True)
        boot = m & ~cloth[i2, j2]
        seam = boot & ndimage.binary_dilation(m & cloth[i2, j2], iterations=2)
        sy, sx = np.nonzero(seam)
        J[s + "_knee"] = np.array([sx.mean(), sy.mean()])
        ay = int(J[s + "_ankle"][1])
        xs_row = np.nonzero(boot[ay])[0]
        J[s + "_ankle"] = np.array([xs_row.mean(), ay])
        by, bx = np.nonzero(boot & (A[:, :, 3] > 160))
        bottom = by.max()
        low = by >= bottom - 6
        J[s + "_toe"] = np.array([bx[low].max(), by[low][np.argmax(bx[low])]])
        J[s + "_heel"] = np.array([bx[low].min(), by[low][np.argmin(bx[low])]])
        foot_pts[s] = bottom   # sole line for this leg

    if cfg.get("far_leg_from_near", True):
        off = J["far_hip"] - J["near_hip"]
        for k in ("knee", "ankle", "toe", "heel"):
            J["far_" + k] = J["near_" + k] + off
        foot_pts["far"] = foot_pts["near"] + off[1] - cfg.get("far_foot_raise", 5.0)
    body = opaque & ~near_arm & ~far_arm & ~((legs["far"] | legs["near"]) & (yy >= lt))
    body_rgba = A.copy()
    body_rgba[~body] = 0
    # Fill what the near arm covered (the vest edge under the sleeve and the back of the
    # torso) by extending the nearest body colours, so nothing looks sliced or hollow when
    # the arm swings away.
    fill_region = near_arm & poly(cfg["torso_poly"])
    if "torso_back_fill" in cfg:
        fill_region |= poly(cfg["torso_back_fill"]) & ~body
    if fill_region.any():
        r_, g_, b_ = (A[:, :, k].astype(int) for k in range(3))
        vest = (r_ > b_ + 55) & (r_ > g_ + 25) & (r_ < 200) & (r_ > 80)          # brown leather/vest tones
        donors = body & (A[:, :, 3] > 200) & vest & poly(cfg["torso_poly"])
        _, (fy, fx) = ndimage.distance_transform_edt(~donors, return_indices=True)
        filled = A[fy, fx, :3].astype(np.float32)
        filled = cv2.GaussianBlur(filled, (0, 0), 1.2)
        body_rgba[fill_region, :3] = filled[fill_region].astype(np.uint8)
        body_rgba[fill_region, 3] = 255
        # soft dark rim on the new outer edge only, matching the art's outlines
        outer = fill_region & ~ndimage.binary_erosion(fill_region | body | near_arm, iterations=1)
        body_rgba[outer, :3] = (body_rgba[outer, :3] * 0.5).astype(np.uint8)

    def layer(mask):
        a = A.copy()
        a[~mask] = 0
        return a

    # ------------------------------------------------ bones (source space)
    # Each bone: (start, end). "root" bones carry the body's bob only.
    hipc = (J["far_hip"] + J["near_hip"]) / 2
    bones = {}
    for s in ("far", "near"):
        bones[s + "_leg"] = {
            "pelvis": (J[s + "_hip"] + np.array([-22.0, -8.0]), J[s + "_hip"] + np.array([22.0, -8.0])),
            "thigh": (J[s + "_hip"], J[s + "_knee"]),
            "shin": (J[s + "_knee"], J[s + "_ankle"]),
            "foot": (J[s + "_ankle"], (J[s + "_toe"] + J[s + "_heel"]) / 2),
        }
    bones["near_arm"] = {
        "torso": (J["near_shoulder"] + np.array([4.0, -16.0]), J["near_shoulder"] + np.array([3.0, -6.0])),
        "upper": (J["near_shoulder"], J["near_elbow"]),
        "fore": (J["near_elbow"], J["near_hand"]),
    }
    bones["far_arm"] = {
        "upper": (J["far_shoulder"], J["far_elbow"]),
        "fore": (J["far_elbow"], J["far_hand"]),
    }
    L = {s: dict(thigh=np.linalg.norm(J[s + "_knee"] - J[s + "_hip"]),
                 shin=np.linalg.norm(J[s + "_ankle"] - J[s + "_knee"])) for s in ("far", "near")}
    nat = {}
    for s in ("far", "near"):
        nat[s + "_thigh"] = ang(J[s + "_hip"], J[s + "_knee"])
        nat[s + "_shin"] = ang(J[s + "_knee"], J[s + "_ankle"])
        nat[s + "_foot"] = ang(J[s + "_ankle"], (J[s + "_toe"] + J[s + "_heel"]) / 2)
        nat[s + "_upper"] = ang(J[s + "_shoulder"], J[s + "_elbow"])
        nat[s + "_fore"] = ang(J[s + "_elbow"], J[s + "_hand"])
    # sole vectors relative to the ankle (for keeping heel/toe on the ground)
    heel_v = {s: J[s + "_heel"] - J[s + "_ankle"] for s in ("far", "near")}
    toe_v = {s: J[s + "_toe"] - J[s + "_ankle"] for s in ("far", "near")}
    ground = {s: float(foot_pts[s]) for s in ("far", "near")}   # each leg keeps its own sole line (3/4 view)

    # ------------------------------------------------ mesh + skin weights per layer
    def make_mesh(mask, bone_set, sigma, extra_dark=None):
        """Regular grid over the layer with FIXED triangles (two per cell), so the warp can
        never tear the art apart the way a re-triangulated (Delaunay) mesh can."""
        ys, xs = np.nonzero(ndimage.binary_dilation(mask, iterations=6))
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        step = 4
        gxs = np.arange(x0, x1 + step, step); gys = np.arange(y0, y1 + step, step)
        gx, gy = np.meshgrid(gxs, gys)
        P = np.stack([gx.ravel(), gy.ravel()], axis=1).astype(float)
        nx, ny = len(gxs), len(gys)
        tris = []
        for r in range(ny - 1):
            for c in range(nx - 1):
                a_, b_, c_, d_ = r * nx + c, r * nx + c + 1, (r + 1) * nx + c, (r + 1) * nx + c + 1
                tris.append((a_, b_, d_)); tris.append((a_, d_, c_))
        names = list(bone_set)
        D = np.stack([seg_dist(P, *bone_set[b]) for b in names], axis=1)
        Wt = np.exp(-(D / sigma) ** 2) + 1e-12
        Wt /= Wt.sum(axis=1, keepdims=True)
        return dict(P=P, W=Wt, names=names, T=np.array(tris))

    # darken far limbs smoothly so the join with the body stays invisible
    def darken(rgba, s_bones, root_name, amount):
        P = np.stack([xx.ravel(), yy.ravel()], axis=1).astype(float)
        names = list(s_bones)
        D = np.stack([seg_dist(P, *s_bones[b]) for b in names], axis=1)
        Wt = np.exp(-(D / 8.0) ** 2) + 1e-12
        Wt /= Wt.sum(axis=1, keepdims=True)
        root_w = Wt[:, names.index(root_name)].reshape(H, W) if root_name in names else np.zeros((H, W))
        f = 1.0 - (1.0 - amount) * (1.0 - root_w)
        out = rgba.copy()
        out[:, :, :3] = np.clip(out[:, :, :3] * f[:, :, None], 0, 255).astype(np.uint8)
        return out

    def far_leg_layer():
        if not cfg.get("far_leg_from_near", True):
            return dict(img=darken(layer(legs["far"]), bones["far_leg"], "pelvis", M["far_dark"]),
                        mesh=make_mesh(legs["far"], bones["far_leg"], 6.5), bones=bones["far_leg"])
        off = J["far_hip"] - J["near_hip"]
        src = layer(legs["near"])
        moved = np.array(Image.fromarray(src).transform((W, H), Image.AFFINE, (1, 0, -off[0], 0, 1, -off[1]), resample=Image.BICUBIC))
        mask = moved[:, :, 3] > 0
        return dict(img=darken(moved, bones["far_leg"], "pelvis", M["far_dark"]), mesh=make_mesh(mask, bones["far_leg"], 6.5), bones=bones["far_leg"])

    layers = {
        "far_arm": dict(img=darken(layer(far_arm), bones["far_arm"], "upper", M["far_dark"]), mesh=make_mesh(far_arm, bones["far_arm"], 6.0), bones=bones["far_arm"]),
        "far_leg": far_leg_layer(),
        "near_leg": dict(img=layer(legs["near"]), mesh=make_mesh(legs["near"], bones["near_leg"], 6.5), bones=bones["near_leg"]),
        "near_arm": dict(img=layer(near_arm), mesh=make_mesh(near_arm, bones["near_arm"], 6.0), bones=bones["near_arm"]),
    }

    # ------------------------------------------------ motion
    N, S, duty = int(M["frames"]), M["stride"], M["duty"]

    def ankle_target(s, p, sole_override=None):
        """Ankle position and sole tilt for leg s at phase p (0 = this foot's heel strike)."""
        p %= 1.0
        hip = J[s + "_hip"]
        cx_ = hip[0] + M["stance_fwd"]
        if p < duty:
            t = p / duty
            x = cx_ + S / 2 - S * t
            if t < 0.15:
                sole = M["heel_strike"] * (1 - smooth(t / 0.15))
            elif t > 0.72:
                sole = M["toe_off"] * smooth((t - 0.72) / 0.28)
            else:
                sole = 0.0
            lift = 0.0
        else:
            u = (p - duty) / (1 - duty)
            x = cx_ - S / 2 + S * smooth(u)
            lift = M["lift"] * math.sin(math.pi * u) ** 1.2
            sole = M["toe_off"] + (M["heel_strike"] - M["toe_off"]) * smooth(u)
        if sole_override is not None:
            sole = sole_override
        # put the lowest point of the tilted foot on the ground
        d_sole = sole - drawn_sole[s]
        hv = rot(heel_v[s][None], d_sole)[0]
        tv = rot(toe_v[s][None], d_sole)[0]
        low = max(hv[1], tv[1])
        y = ground[s] - low - lift
        return np.array([x, y]), sole, lift

    def sole_of(s):
        h, t = J[s + "_heel"], J[s + "_toe"]
        return -math.degrees(math.atan2(t[1] - h[1], t[0] - h[0]))   # + = toe up
    drawn_sole = {s: sole_of(s) for s in ("far", "near")}

    def bob_at(p):
        # low at each contact (p = 0, 0.5), high a little after each passing
        return M["bob"] * math.cos(4 * math.pi * (p - M["bob_phase"]))

    def ik(hip, target, l1, l2):
        d_vec = target - hip
        d = np.linalg.norm(d_vec)
        d = min(d, (l1 + l2) * 0.999)
        base = math.degrees(math.atan2(d_vec[0], d_vec[1]))
        cosA = (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)
        a = math.degrees(math.acos(max(-1.0, min(1.0, cosA))))
        th = base + a                      # knee points forward
        knee = hip + ddir(th) * l1
        sh = ang(knee, target)
        return th, sh, knee

    PAD = 60
    OW, OH = W + 2 * PAD, H + 2 * PAD

    def pose_bones(layer_name, p, bob):
        """Rigid transform (rotation delta, source pivot, destination pivot) per bone."""
        tr = {}
        down = np.array([0.0, bob])
        if layer_name.endswith("leg"):
            s = layer_name.split("_")[0]
            ph = p if s == "near" else p + 0.5
            hip = J[s + "_hip"] + down
            target, sole, lift = ankle_target(s, ph)
            th, sh, knee = ik(hip, target, L[s]["thigh"], L[s]["shin"])
            # a real ankle only flexes so far: limit the foot's turn relative to the shin,
            # then re-plant the (now tilted) foot and solve again
            for _ in range(3):
                rel = (sole - drawn_sole[s]) - (sh - nat[s + "_shin"])
                rel_c = min(max(rel, M["ankle_min"]), M["ankle_max"])
                if abs(rel_c - rel) < 0.05:
                    break
                sole = drawn_sole[s] + (sh - nat[s + "_shin"]) + rel_c
                target, _, lift = ankle_target(s, ph, sole_override=sole)
                th, sh, knee = ik(hip, target, L[s]["thigh"], L[s]["shin"])
            ankle = knee + ddir(sh) * L[s]["shin"]
            tr["pelvis"] = (0.0, J[s + "_hip"], hip)
            tr["thigh"] = (th - nat[s + "_thigh"], J[s + "_hip"], hip)
            tr["shin"] = (sh - nat[s + "_shin"], J[s + "_knee"], knee)
            tr["foot"] = (sole - drawn_sole[s], J[s + "_ankle"], ankle)
            return tr, dict(hip=hip, knee=knee, ankle=ankle, thigh=th, shin=sh, sole=sole, lift=lift)
        lag = M["arm_lag"]
        if layer_name == "near_arm":
            sw = -M["arm_swing"] * math.cos(2 * math.pi * (p - lag))
            up = nat["near_upper"] + sw
            fwd = sw / M["arm_swing"] if M["arm_swing"] else 0.0
            el = M["elbow_base"] + M["elbow_swing"] * (fwd + 1) / 2   # more bend as the arm comes forward
            fo = up + el
            sh_ = J["near_shoulder"] + down
            elbow = sh_ + ddir(up) * np.linalg.norm(J["near_elbow"] - J["near_shoulder"])
            tr["torso"] = (0.0, J["near_shoulder"], sh_)
            tr["upper"] = (up - nat["near_upper"], J["near_shoulder"], sh_)
            tr["fore"] = (fo - nat["near_fore"], J["near_elbow"], elbow)
            return tr, dict(upper=up, fore=fo)
        # far arm: upper arm stays on the torso, forearm swings opposite the near arm
        sw = M["far_fore_swing"] * math.cos(2 * math.pi * (p - lag))
        el_src = J["far_elbow"] + down
        tr["upper"] = (0.0, J["far_shoulder"], J["far_shoulder"] + down)
        tr["fore"] = (sw, J["far_elbow"], el_src)
        return tr, dict(fore=nat["far_fore"] + sw)

    def deform(layer_name, p, bob):
        Ly = layers[layer_name]
        tr, info = pose_bones(layer_name, p, bob)
        P, Wt, names = Ly["mesh"]["P"], Ly["mesh"]["W"], Ly["mesh"]["names"]
        # Joint-aware blending (no "collapsing elbow"): each point picks its two strongest
        # neighbouring bones in the chain, blends their ANGLES, and rotates about the joint
        # they share. Points deep inside one bone move rigidly with it.
        nb = len(names)
        ang_d = np.array([tr[b][0] for b in names])
        k1 = np.argmax(Wt, axis=1)
        lo = np.clip(k1 - 1, 0, nb - 1); hi = np.clip(k1 + 1, 0, nb - 1)
        w_lo = np.where(lo != k1, Wt[np.arange(len(P)), lo], -1)
        w_hi = np.where(hi != k1, Wt[np.arange(len(P)), hi], -1)
        k2 = np.where(w_hi >= w_lo, hi, lo)
        child = np.maximum(k1, k2)
        wa = Wt[np.arange(len(P)), k1]; wb = Wt[np.arange(len(P)), k2]
        wa_n = np.where(k2 != k1, wa / (wa + wb), 1.0); wb_n = 1.0 - wa_n
        blended = wa_n * ang_d[k1] + wb_n * ang_d[k2]
        Q = np.zeros_like(P)
        for k, b in enumerate(names):
            sel = child == k
            if not sel.any():
                continue
            _, src_piv, dst_piv = tr[b]
            r = np.radians(blended[sel])
            v = P[sel] - src_piv
            c_, s_ = np.cos(r), np.sin(r)
            Q[sel] = dst_piv + np.stack([c_ * v[:, 0] + s_ * v[:, 1], -s_ * v[:, 0] + c_ * v[:, 1]], axis=1)
        # rasterise every destination triangle (fixed topology) and map back to the source
        T = Ly["mesh"]["T"]
        Qp = Q + PAD
        tri_id = np.full((OH, OW), -1, np.int32)
        idimg = np.zeros((OH, OW, 3), np.uint8)
        # draw triangles back-to-front by depth-free order; folded triangles are rare with smooth weights
        for k, (i0, i1, i2) in enumerate(T):
            code = k + 1
            col = (code & 255, (code >> 8) & 255, (code >> 16) & 255)
            pts = np.round(Qp[[i0, i1, i2]] * 16).astype(np.int32)
            cv2.fillConvexPoly(idimg, pts, col, lineType=cv2.LINE_8, shift=4)
        tri_id = idimg[:, :, 0].astype(np.int32) | (idimg[:, :, 1].astype(np.int32) << 8) | (idimg[:, :, 2].astype(np.int32) << 16)
        tri_id -= 1
        # affine (dst -> src) per triangle
        Dm = np.concatenate([Qp[T], np.ones((len(T), 3, 1))], axis=2)        # (n,3,3) rows [x y 1]
        Sm = P[T]                                                               # (n,3,2)
        det = np.linalg.det(Dm)
        ok = np.abs(det) > 1e-6
        Aff = np.zeros((len(T), 3, 2))
        Aff[ok] = np.linalg.solve(Dm[ok], Sm[ok])
        ys_, xs_ = np.nonzero(tri_id >= 0)
        tid = tri_id[ys_, xs_]
        v = np.stack([xs_, ys_, np.ones_like(xs_)], axis=1).astype(float)
        src = np.einsum("ni,nij->nj", v, Aff[tid])
        mapx = np.full((OH, OW), -10.0, np.float32); mapy = np.full((OH, OW), -10.0, np.float32)
        mapx[ys_, xs_] = src[:, 0]; mapy[ys_, xs_] = src[:, 1]
        img = Ly["img"].astype(np.float32) / 255.0
        pm = img.copy()
        pm[:, :, :3] *= pm[:, :, 3:4]
        out = cv2.remap(pm, mapx, mapy, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        a = out[:, :, 3:4]
        rgb = np.where(a > 1e-4, out[:, :, :3] / np.maximum(a, 1e-4), 0)
        res = np.concatenate([rgb, a], axis=2)
        return Image.fromarray((np.clip(res, 0, 1) * 255).astype(np.uint8)), info

    def body_at(bob):
        img = Image.new("RGBA", (OW, OH), (0, 0, 0, 0))
        img.alpha_composite(Image.fromarray(body_rgba), (PAD, PAD))
        return img.transform(img.size, Image.AFFINE, (1, 0, 0, 0, 1, -bob), resample=Image.BICUBIC)

    frames, infos, bobs = [], [], []
    for i in range(N):
        p = i / N
        bob = bob_at(p)
        c = Image.new("RGBA", (OW, OH), (0, 0, 0, 0))
        fa, farm = deform("far_arm", p, bob)
        fl, finfo = deform("far_leg", p, bob)
        nlg, ninfo = deform("near_leg", p, bob)
        na, ainfo = deform("near_arm", p, bob)
        for im in (fa, fl, body_at(bob), nlg, na):
            c.alpha_composite(im)
        frames.append(c)
        infos.append(dict(far=finfo, near=ninfo, arm=ainfo, farm=farm))
        bobs.append(bob)

    # identical crop for every frame (no per-frame re-alignment = no jitter)
    box = None
    for f in frames:
        bb = f.getbbox()
        box = bb if box is None else (min(box[0], bb[0]), min(box[1], bb[1]), max(box[2], bb[2]), max(box[3], bb[3]))
    box = (box[0] - 4, box[1] - 4, box[2] + 4, box[3] + 2)
    fw, fh = box[2] - box[0], box[3] - box[1]
    strip = Image.new("RGBA", (fw * N, fh), (0, 0, 0, 0))
    for k, f in enumerate(frames):
        strip.alpha_composite(f.crop(box), (k * fw, 0))
    name = cfg["name"]
    strip.save(f"{name}_side_walk_src.png")
    ground_y = max(ground.values()) + PAD - box[1]
    json.dump({"frame_w": fw, "frame_h": fh, "count": N, "head_x": J["head"][0] + PAD - box[0],
               "ground_y": ground_y, "cycle_travel_src": S / duty},
              open(f"{name}_side_walk_src.json", "w"))

    # ---------------- spec
    rows = ["# %s side walk (skinned): exact per-frame values" % name.capitalize(), "",
            "Angles: degrees from straight down, + = toward the front. Sole: + = toe up. "
            "Hip bob: source px, + = lower. Ankle x is relative to the hip. Source art is about 2x the game cell.", "",
            "| Frame | Hip bob | Near thigh | Near knee bend | Near sole | Near ankle x | Near ankle lift | Far thigh | Far knee bend | Far sole | Far ankle x | Far ankle lift | Near arm | Far forearm |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, inf in enumerate(infos):
        def leg_cols(s):
            d = inf[s]
            return f"{d['thigh']:.1f} | {d['thigh'] - d['shin']:.1f} | {d['sole']:.1f} | {d['ankle'][0] - J[s + '_hip'][0]:.1f} | {d['lift']:.1f}"
        rows.append(f"| {i} | {bobs[i]:.2f} | {leg_cols('near')} | {leg_cols('far')} | {inf['arm']['upper']:.1f} | {inf['farm']['fore']:.1f} |")
    rows += ["", "Motion settings: " + ", ".join(f"{k}={v}" for k, v in M.items()),
             "", f"Body travel per cycle (source px): {S / duty:.1f}. Stance foot slides back at exactly the body speed, so feet don't skate when the game moves the character at the matching speed."]
    open(f"{name}_walk_spec.md", "w").write("\n".join(rows) + "\n")
    print("ok", strip.size, "bob", [round(b, 2) for b in bobs])


if __name__ == "__main__":
    main(sys.argv[1])
