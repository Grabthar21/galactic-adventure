"""Pose stress test for Space Piece bipeds (UE Mannequin bone names). Runs in Blender.

Puts a rigged character through a fixed pose suite and measures what went wrong on Arthur:
  - rest pose: foot direction (duck feet), arm angle and hand clearance (hands crossing),
    feet on the ground
  - every pose: body parts passing through each other (hand through hip, legs through
    each other...), stretched or squashed areas, feet sinking or floating
  - fist (if finger bones exist): finger parts passing through each other
and renders one picture strip of all poses with the same camera and lights.

Poses are defined in character space (the character faces -Y, its left is +X), so they mean
the same thing on any rig, whatever the bone roll. Numbers scale with the character's height.

Usage (inside Blender):
    import blender_pose_test as p
    rep = p.run(meshes=["SK_Arthur"], armature="Armature", out_dir=r"C:/.../review", name="Arthur")
"""
import json
import math
import os

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

# --------------------------------------------------------------------- limits
LIMITS = {
    "foot_out_max_deg": 12.0,       # Manny ~6.5 deg; Arthur was 25-30 before the fix
    "arm_angle_deg": [15.0, 50.0],  # upper arm from vertical in the rest pose (A-pose)
    "hand_clearance_frac": 0.012,   # rest: hand at least ~2 cm (on 160 cm) from thigh/hip
    "ground_tol_frac": 0.012,       # supporting foot within ~2 cm of the ground
    "penetration_depth_frac": 0.006,  # deeper than ~1 cm (on 160 cm) counts as passing through
    "penetration_share_max": 0.004,   # share of a part's vertices allowed through (noise)
    "stretch_p99_max": 1.35,
    "squash_p1_min": 0.60,
}

GROUPS = {
    "head": ["head", "neck_01", "neck_02"],
    "torso": ["pelvis", "spine_01", "spine_02", "spine_03", "spine_04", "spine_05",
              "clavicle_l", "clavicle_r"],
    "upperarm_l": ["upperarm_l"], "upperarm_r": ["upperarm_r"],
    "forearm_l": ["lowerarm_l"], "forearm_r": ["lowerarm_r"],
    "hand_l": ["hand_l"], "hand_r": ["hand_r"],
    "leg_l": ["thigh_l", "calf_l"], "leg_r": ["thigh_r", "calf_r"],
    "foot_l": ["foot_l", "ball_l"], "foot_r": ["foot_r", "ball_r"],
}
FINGERS = ["thumb", "index", "middle", "ring", "pinky"]

# Pairs that must not pass through each other.
BAD_PAIRS = [
    ("hand_l", "torso"), ("hand_r", "torso"), ("hand_l", "leg_l"), ("hand_r", "leg_r"),
    ("hand_l", "leg_r"), ("hand_r", "leg_l"), ("hand_l", "head"), ("hand_r", "head"),
    ("forearm_l", "torso"), ("forearm_r", "torso"), ("forearm_l", "leg_l"), ("forearm_r", "leg_r"),
    ("leg_l", "leg_r"), ("foot_l", "foot_r"), ("foot_l", "leg_r"), ("foot_r", "leg_l"),
    ("hand_l", "hand_r"), ("upperarm_l", "head"), ("upperarm_r", "head"),
]

# --------------------------------------------------------------------- pose suite
# Each entry: bone -> list of (axis, degrees) in CHARACTER space, applied in order.
#   swing  = forward (+) / back (-) about the side axis
#   spread = away from the body sideways (+) for that side
#   twist  = turn about the vertical axis, + = towards the character's left
POSES = {
    "rest": {},
    "walk": {
        "thigh_l": [("swing", 28)], "calf_l": [("swing", -8)],
        "thigh_r": [("swing", -18)], "calf_r": [("swing", -30)],
        "upperarm_l": [("swing", -18)], "upperarm_r": [("swing", 20)],
        "lowerarm_l": [("swing", 12)], "lowerarm_r": [("swing", 25)],
    },
    "run": {
        "spine_01": [("swing", 10)],
        "thigh_l": [("swing", 55)], "calf_l": [("swing", -45)],
        "thigh_r": [("swing", -25)], "calf_r": [("swing", -85)],
        "upperarm_l": [("swing", -40)], "upperarm_r": [("swing", 45)],
        "lowerarm_l": [("swing", 75)], "lowerarm_r": [("swing", 85)],
    },
    "crouch": {
        "spine_01": [("swing", 25)],
        "thigh_l": [("swing", 80), ("spread", 8)], "calf_l": [("swing", -115)], "foot_l": [("swing", 35)],
        "thigh_r": [("swing", 80), ("spread", 8)], "calf_r": [("swing", -115)], "foot_r": [("swing", 35)],
        "upperarm_l": [("swing", 25)], "upperarm_r": [("swing", 25)],
    },
    "arms_up": {
        "upperarm_l": [("spread", 150)], "upperarm_r": [("spread", 150)],
        "lowerarm_l": [("spread", 10)], "lowerarm_r": [("spread", 10)],
    },
    "sword_ready": {
        "spine_02": [("twist", 20)],
        "upperarm_r": [("swing", 55), ("spread", 15)], "lowerarm_r": [("swing", 55)],
        "upperarm_l": [("swing", 20), ("spread", 10)], "lowerarm_l": [("swing", 45)],
        "thigh_l": [("swing", 15)], "thigh_r": [("swing", -10)], "calf_r": [("swing", -15)],
    },
    "slash": {
        "spine_02": [("twist", -35)],
        "upperarm_r": [("swing", 70), ("spread", -35)], "lowerarm_r": [("swing", 15)],
        "upperarm_l": [("spread", 35)], "lowerarm_l": [("swing", 30)],
        "thigh_l": [("swing", 25)], "thigh_r": [("swing", -15)],
    },
    "fist": {
        "upperarm_l": [("swing", 60)], "upperarm_r": [("swing", 60)],
        "lowerarm_l": [("swing", 30)], "lowerarm_r": [("swing", 30)],
        "__fingers__": 80,
    },
}
# Feet must touch the floor (z = 0) in the rest pose. Made-up poses can't know which foot is
# planted; real clips are checked for sliding/sinking in Unreal.
STANDING = {"rest": ["foot_l", "foot_r"]}
# Some poses are hard on any mesh (Manny stretches too); they get looser stretch limits.
POSE_LIMITS = {"arms_up": {"stretch_p99_max": 1.6, "squash_p1_min": 0.5},
               "fist": {"stretch_p99_max": 1.6, "squash_p1_min": 0.45},
               "crouch": {"stretch_p99_max": 1.5, "squash_p1_min": 0.5}}
REST_PAIRS = {p for p in BAD_PAIRS if p[0].startswith(("hand", "forearm"))}

FWD = Vector((0, -1, 0))


def _axis(kind, side):
    # character faces -Y, left = +X
    if kind == "swing":
        return Vector((1, 0, 0)), -1.0        # forward swing of a hanging limb moves it to -Y
    if kind == "spread":
        return Vector((0, 1, 0)), (-1.0 if side == "l" else 1.0)
    if kind == "twist":
        return Vector((0, 0, 1)), 1.0
    raise ValueError(kind)


def _side(name):
    return "l" if name.endswith("_l") else "r" if name.endswith("_r") else "c"


# --------------------------------------------------------------------- posing
def reset_pose(arm):
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def apply_pose(arm, pose):
    reset_pose(arm)
    wm = arm.matrix_world.to_3x3().normalized()
    inv = wm.inverted()
    # parents first
    order = sorted(arm.pose.bones, key=lambda b: len(b.parent_recursive))
    fingers = pose.get("__fingers__")
    for pb in order:
        steps = list(pose.get(pb.name, []))
        if fingers and any(pb.name.startswith(f) for f in FINGERS):
            steps = [("spread", -fingers * (0.6 if pb.name.startswith("thumb") else 1.0))]  # curl toward the palm (palms face the body in A-pose)
        if not steps:
            continue
        m = pb.matrix.copy()  # armature space
        head = m.translation.copy()
        rot = Matrix.Identity(3)
        for kind, deg in steps:
            ax, sign = _axis(kind, _side(pb.name))
            rot = Matrix.Rotation(math.radians(deg * sign), 3, inv @ ax) @ rot
        new = (rot @ m.to_3x3()).to_4x4()
        new.translation = head
        pb.matrix = new
        bpy.context.view_layer.update()


# --------------------------------------------------------------------- mesh data
def _evaluated(meshes):
    """World-space verts per mesh after the armature, plus faces and per-vertex group."""
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for o in meshes:
        oe = o.evaluated_get(dg)
        me = oe.to_mesh()
        verts = [o.matrix_world @ v.co for v in me.vertices]
        faces = [tuple(p.vertices) for p in me.polygons]
        edges = [tuple(e.vertices) for e in me.edges]
        oe.to_mesh_clear()
        out.append((o, verts, faces, edges))
    return out


def _vertex_groups(o):
    """Group (body part) of each vertex: the body part of its strongest bone."""
    bone_to_group = {}
    for g, bones in GROUPS.items():
        for b in bones:
            bone_to_group[b] = g
    for f in FINGERS:
        for s in ("l", "r"):
            for i in (1, 2, 3):
                bone_to_group[f"{f}_0{i}_{s}"] = f"hand_{s}"
    idx_to_group = {vg.index: bone_to_group.get(vg.name) for vg in o.vertex_groups}
    finger_of = {vg.index: next((f"{f}_{vg.name[-1]}" for f in FINGERS if vg.name.startswith(f)), None)
                 for vg in o.vertex_groups}
    groups, fingers = [], []
    for v in o.data.vertices:
        best, bw, fb = None, 0.0, None
        for g in v.groups:
            if g.weight > bw and idx_to_group.get(g.group):
                best, bw, fb = idx_to_group[g.group], g.weight, finger_of.get(g.group)
        groups.append(best)
        fingers.append(fb)
    return groups, fingers


def _penetration(verts, faces, groups, a, b, depth, skip=frozenset()):
    """Vertices of part a that are more than `depth` inside part b's surface.
    Returns (count, worst depth, part size, set of vertex indices)."""
    fb = [f for f in faces if all(groups[i] == b for i in f)]
    va = [i for i, g in enumerate(groups) if g == a and i not in skip]
    if not fb or not va:
        return 0, 0.0, len(va), set()
    tree = BVHTree.FromPolygons(verts, fb, all_triangles=False)
    n, worst, hits = 0, 0.0, set()
    for i in va:
        hit = tree.find_nearest(verts[i], abs(depth) * 12 + 1e-4)
        if hit[0] is None:
            continue
        loc, nor, _, dist = hit
        inside = (verts[i] - loc).dot(nor)
        if inside < -depth:
            n += 1
            hits.add(i)
            worst = max(worst, -inside)
    return n, worst, len(va), hits


def _stretch(rest_verts, verts, edges):
    ratios = []
    for i, j in edges:
        r = (rest_verts[i] - rest_verts[j]).length
        if r > 1e-6:
            ratios.append((verts[i] - verts[j]).length / r)
    ratios.sort()
    if not ratios:
        return 1.0, 1.0, 1.0, 1.0
    p = lambda q: ratios[min(len(ratios) - 1, int(q * len(ratios)))]
    return p(0.01), p(0.99), ratios[0], ratios[-1]


def _foot_direction(verts, groups, part):
    """Turn-out of a foot, degrees: + = toes pointing outward. From the sole outline (PCA)."""
    pts = [verts[i] for i, g in enumerate(groups) if g == part]
    if len(pts) < 10:
        return None
    zmin = min(p.z for p in pts)
    h = max(p.z for p in pts) - zmin
    sole = [p for p in pts if p.z < zmin + 0.35 * h] or pts
    cx = sum(p.x for p in sole) / len(sole)
    cy = sum(p.y for p in sole) / len(sole)
    # long axis of the tightest rectangle around the sole (robust to round heels and toes)
    best = None
    for k in range(360):
        a = math.radians(k * 0.5)
        ca, sa = math.cos(a), math.sin(a)
        us = [(p.x - cx) * ca + (p.y - cy) * sa for p in sole]
        vs = [-(p.x - cx) * sa + (p.y - cy) * ca for p in sole]
        lu, lv = max(us) - min(us), max(vs) - min(vs)
        area = lu * lv
        if best is None or area < best[0]:
            best = (area, a if lu >= lv else a + math.pi / 2)
    ang = best[1]
    d = Vector((math.cos(ang), math.sin(ang), 0))
    # make it point toward the toes: the end farther forward (-Y)
    ext = sorted(sole, key=lambda p: (p.x - cx) * d.x + (p.y - cy) * d.y)
    if ext[-1].y > ext[0].y:
        d = -d
    turn = math.degrees(math.atan2(d.x, -d.y))  # + = toward +X
    return turn if part.endswith("_l") else -turn  # + = outward for both feet


def _arm_angle(arm, side):
    b = arm.pose.bones.get(f"upperarm_{side}")
    if not b:
        return None
    d = (arm.matrix_world @ b.tail) - (arm.matrix_world @ b.head)
    return math.degrees(math.atan2(math.hypot(d.x, d.y), -d.z))


def _min_dist(verts, groups, a, b_list):
    pa = [verts[i] for i, g in enumerate(groups) if g == a]
    pb = [verts[i] for i, g in enumerate(groups) if g in b_list]
    if not pa or not pb:
        return None
    tree = BVHTree.FromPolygons(pb, [(i, i, i) for i in range(len(pb))], all_triangles=True)
    best = 1e9
    for p in pa[::max(1, len(pa) // 400)]:
        hit = tree.find_nearest(p)
        if hit[0] is not None:
            best = min(best, hit[3])
    return best


# --------------------------------------------------------------------- render
def _render_strip(meshes, arm, out_dir, name, poses, height):
    """One picture per pose, the character alone, same camera/lights as the review renders."""
    from blender_review_renders import _Stage, _bbox
    st = _Stage(meshes + [arm], "PoseStrip")
    s = st.scn
    s.render.resolution_x, s.render.resolution_y = 600, 800
    cam = st.cam
    cam.data.lens = 60
    cam.data.sensor_fit = "VERTICAL"
    cam.data.sensor_height = 24
    base = arm.location.copy()
    paths = []
    for pname in poses:
        apply_pose(arm, POSES[pname])
        _ground(arm, meshes)
        mn, mx = _bbox(meshes)
        tgt = Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, height * 0.5))
        a = math.radians(30)
        dist = (height * 1.35) / (2 * math.tan(cam.data.angle_y / 2))
        cam.location = tgt + Vector((math.sin(a), -math.cos(a), 0.12)) * dist
        cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
        paths.append(st.render(os.path.join(out_dir, f"{name}_pose_{pname}.png")))
        arm.location = base
    reset_pose(arm)
    st.close()
    return paths


def _ground(arm, meshes):
    """Drop or lift the whole character so its lowest point touches the floor (crouch, run)."""
    bpy.context.view_layer.update()
    low = min(v.z for _, verts, _, _ in _evaluated(meshes) for v in verts)
    arm.location.z -= low
    bpy.context.view_layer.update()


# --------------------------------------------------------------------- main
def run(meshes, armature, out_dir=None, name="character", poses=None, render=True, limits=None):
    lim = dict(LIMITS, **(limits or {}))
    objs = [bpy.data.objects[m] if isinstance(m, str) else m for m in meshes]
    arm = bpy.data.objects[armature] if isinstance(armature, str) else armature
    arm_loc = arm.location.copy()
    poses = poses or list(POSES)
    has_fingers = any(b.name.startswith("index_01") for b in arm.data.bones)
    if not has_fingers and "fist" in poses:
        poses = [p for p in poses if p != "fist"]
    rep = {"name": name, "checks": [], "measured": {"poses": {}}, "limits": lim}

    def res(check, status, detail, value=None, pose=None):
        rep["checks"].append({"check": check, "status": status, "detail": detail,
                              "value": value, "pose": pose})

    groups = {o.name: _vertex_groups(o) for o in objs}
    reset_pose(arm)
    rest = _evaluated(objs)
    allv = [v for _, vs, _, _ in rest for v in vs]
    height = max(v.z for v in allv) - min(v.z for v in allv)
    floor = min(v.z for v in allv)
    rep["measured"]["height_m"] = round(height, 4)
    depth = lim["penetration_depth_frac"] * height
    cm = lambda m: f"{m * 100:.1f} cm"

    # ---- rest-pose checks
    for o, verts, faces, edges in rest:
        g, _ = groups[o.name]
        for part in ("foot_l", "foot_r"):
            t = _foot_direction(verts, g, part)
            if t is None:
                continue
            rep["measured"][f"foot_out_{part}"] = round(t, 1)
            ok = abs(t) <= lim["foot_out_max_deg"]
            res(f"foot direction {part[-1]}", "PASS" if ok else "ASK",
                f"toes turned {'out' if t >= 0 else 'in'} {abs(t):.1f} deg (max {lim['foot_out_max_deg']:.0f}; Manny ~6.5)"
                + ("" if ok else " - will walk duck-footed / pigeon-toed; rotate the leg in the rest pose"), t, "rest")
        for side in ("l", "r"):
            d = _min_dist(verts, g, f"hand_{side}", ["leg_l", "leg_r", "torso"])
            if d is not None:
                need = lim["hand_clearance_frac"] * height
                res(f"hand clearance {side}", "PASS" if d >= need else "ASK",
                    f"hand {cm(d)} from hip/thigh (min {cm(need)}); too close = hands cross the body in shared animations", d, "rest")
    for side in ("l", "r"):
        a = _arm_angle(arm, side)
        if a is not None:
            lo, hi = lim["arm_angle_deg"]
            rep["measured"][f"arm_angle_{side}"] = round(a, 1)
            res(f"arm angle {side}", "PASS" if lo <= a <= hi else "ASK",
                f"upper arm {a:.1f} deg from vertical (allowed {lo:.0f}-{hi:.0f}; A-pose)", a, "rest")

    # ---- rest baseline: where parts already meet (crotch, armpits, joins), so poses only
    # report NEW passing-through. Hands and forearms inside the body at rest are reported.
    baseline = {}
    for o, verts, faces, edges in rest:
        g, _ = groups[o.name]
        for a, b in BAD_PAIRS:
            n, worst, total, hits = _penetration(verts, faces, g, a, b, depth * 0.5)
            near = set()
            # also skip vertices sitting right on b's surface at rest (joins)
            _, _, _, near = _penetration(verts, faces, g, a, b, -depth * 0.5)
            baseline[(o.name, a, b)] = frozenset(hits | near)
            if (a, b) in REST_PAIRS and n >= 3 and n / max(total, 1) > lim["penetration_share_max"]:
                res(f"{a} through {b}", "ASK",
                    f"{n} vertices up to {cm(worst)} inside {b} already in the rest pose", n / total, "rest")

        _, fing = groups[o.name]
        for sd in ("l", "r"):
            names = [f"{f}_{sd}" for f in FINGERS]
            for i in range(len(names) - 1):
                _, _, _, near = _penetration(verts, faces, fing, names[i], names[i + 1], -depth * 0.5)
                baseline[(o.name, "fing", names[i])] = frozenset(near)

    # ---- every pose
    for pname in poses:
        plim = dict(lim, **POSE_LIMITS.get(pname, {}))
        apply_pose(arm, POSES[pname])
        posed = _evaluated(objs)
        pm = {}
        for (o, rverts, _, edges), (_, verts, faces, _) in zip(rest, posed):
            g, fing = groups[o.name]
            for a, b in BAD_PAIRS:
                n, worst, total, _ = _penetration(verts, faces, g, a, b, depth,
                                                  baseline.get((o.name, a, b), frozenset()))
                if total == 0:
                    continue
                share = n / total
                if n >= 3 and share > lim["penetration_share_max"]:
                    res(f"{a} through {b}", "ASK",
                        f"{n} vertices ({share:.1%} of {a}) up to {cm(worst)} inside {b}", share, pname)
                    pm[f"{a}>{b}"] = round(share, 4)
            if pname == "fist" and any(fing):
                fg = [f for f in fing]
                for s in ("l", "r"):
                    names = [f"{f}_{s}" for f in FINGERS]
                    for i in range(len(names) - 1):
                        n, worst, total, _ = _penetration(verts, faces, fg, names[i], names[i + 1], depth * 0.5,
                                                          baseline.get((o.name, "fing", names[i]), frozenset()))
                        if total and n / total > 0.02:
                            res(f"{names[i]} through {names[i + 1]}", "ASK",
                                f"{n} vertices up to {cm(worst)} inside the next finger", n / total, pname)
            lo, hi, mn, mx = _stretch(rverts, verts, edges)
            pm["stretch_p99"] = round(hi, 3)
            pm["squash_p1"] = round(lo, 3)
            if hi > plim["stretch_p99_max"]:
                res("stretching", "ASK", f"top 1% of edges stretched to {hi:.2f}x (max {plim['stretch_p99_max']}); worst {mx:.2f}x", hi, pname)
            if lo < plim["squash_p1_min"]:
                res("squashing", "ASK", f"bottom 1% of edges squashed to {lo:.2f}x (min {plim['squash_p1_min']}); worst {mn:.2f}x", lo, pname)
            for part in STANDING.get(pname, []):
                pts = [verts[i].z for i, gg in enumerate(g) if gg == part]
                if pts:
                    off = min(pts)  # floor is z = 0
                    tol = lim["ground_tol_frac"] * height
                    pm[f"ground_{part}"] = round(off, 4)
                    if abs(off) > tol:
                        res(f"ground contact {part}", "ASK",
                            f"{'floating' if off > 0 else 'sinking'} {cm(abs(off))} (tolerance {cm(tol)})", off, pname)
        rep["measured"]["poses"][pname] = pm
    reset_pose(arm)
    arm.location = arm_loc
    bpy.context.view_layer.update()

    if not any(c["status"] == "ASK" and c["pose"] not in (None, "rest") for c in rep["checks"]):
        res("pose suite", "PASS", f"{len(poses)} poses: nothing passes through, no bad stretching, feet on the ground")
    if not has_fingers:
        res("fist", "INFO", "no finger bones; fist test skipped")
    if render and out_dir:
        os.makedirs(out_dir, exist_ok=True)
        rep["renders"] = _render_strip(objs, arm, out_dir, name, poses, height)
        arm.location = arm_loc
    st = [c["status"] for c in rep["checks"]]
    rep["verdict"] = "ASK" if "ASK" in st else "PASS"
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, f"{name}_pose_report.json"), "w") as f:
            json.dump(rep, f, indent=2, default=float)
    return rep
