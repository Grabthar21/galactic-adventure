"""Builds Arthur's lock-on movement set (strafe left/right, walk back) from Mixamo clips.

Run inside Blender with Arthur_rigged.blend open (Mixamo clips imported as MIX_* armatures):

    import blender_lockon_set as L
    L.build(out_dir=r"C:/Users/johnn/Documents/SpacePiece_Blender/ArthurAdv/pipeline/anims")

For every source clip it works out which way the character travels (forward, back, left,
right), transfers it onto Arthur IN PLACE (no travel; the game moves him), fixes floor
contact, and exports A_Arthur_LockOn_<Dir>.fbx. A missing side is made by mirroring the
other one (strafe left <-> right). It writes lockon_set.json with each clip's real walking
speed (cm/s) so the Unreal blend space puts every clip at the speed it was made for.
"""
import json
import os

import bpy
from mathutils import Vector

import blender_mixamo_retarget as R

KEYWORDS = ("strafe", "back", "walkingbackward", "walk_back")
OPPOSITE = {"Left": "Right", "Right": "Left"}


def _clip_range(src):
    a = src.animation_data.action
    return int(a.frame_range[0]), int(a.frame_range[1])


def classify(src, dst=None, frames=None):
    """Return (direction, speed in cm/s on Arthur's scale) of a Mixamo clip."""
    scn = bpy.context.scene
    f0, f1 = frames or _clip_range(src)
    hips = R._src_name(src, "Hips")
    lt, rt = R._src_name(src, "LeftUpLeg"), R._src_name(src, "RightUpLeg")
    left = R._world_rest(src, lt)[0] - R._world_rest(src, rt)[0]
    left.z = 0
    left.normalize()
    fwd = left.cross(Vector((0, 0, 1)))

    def hp(f):
        scn.frame_set(f)
        return (src.matrix_world @ src.pose.bones[hips].matrix).to_translation()
    travel = hp(f1) - hp(f0)
    travel.z = 0
    k = 1.0
    if dst is not None:
        k = R._world_rest(dst, "pelvis")[0].z / R._world_rest(src, hips)[0].z
    secs = max(1, f1 - f0) / (scn.render.fps / scn.render.fps_base)
    speed = travel.length * k * 100.0 / secs
    if travel.length * k < 0.05:  # "In Place" download: no travel to read, go by the clip's name
        n = src.name.lower()
        d = "Left" if "left" in n else "Right" if "right" in n else "Back" if "back" in n else "Fwd"
        return d, 150.0
    a, b = travel.dot(fwd), travel.dot(left)
    if abs(b) > abs(a):
        return ("Left" if b > 0 else "Right"), speed
    return ("Fwd" if a > 0 else "Back"), speed


def find_sources():
    out = []
    for o in bpy.data.objects:
        if o.type == "ARMATURE" and o.name.startswith("MIX_") and o.animation_data and o.animation_data.action:
            if any(k in o.name.lower().replace(" ", "") for k in KEYWORDS):
                out.append(o)
    return out


def _arthur():
    dst = bpy.data.objects.get("Armature")
    mesh = next((c for c in dst.children if c.type == "MESH"), None) if dst else None
    return dst, mesh


def build(out_dir, sources=None, dst=None, mesh=None, prefix="A_Arthur_LockOn_"):
    if dst is None:
        dst, mesh = _arthur()
    sources = sources or find_sources()
    os.makedirs(out_dir, exist_ok=True)
    made = {}
    for src in sources:
        d, speed = classify(src, dst)
        if d in made or d == "Fwd":  # forward comes from Arthur's normal walk
            continue
        act = R.retarget(src, dst, prefix + d, in_place=True)
        if mesh:
            R.ground_clip(dst, mesh, act)
        path = R.export_action(dst, act, os.path.join(out_dir, prefix + d + ".fbx"))
        made[d] = {"file": path, "speed": round(speed, 1), "source": src.name, "mirrored": False}
    for d, other in OPPOSITE.items():
        if d in made or other not in made:
            continue
        src = bpy.data.objects[made[other]["source"]]
        act = R.retarget(src, dst, prefix + d, in_place=True, mirror=True)
        if mesh:
            R.ground_clip(dst, mesh, act)
        path = R.export_action(dst, act, os.path.join(out_dir, prefix + d + ".fbx"))
        made[d] = dict(made[other], file=path, mirrored=True)
    with open(os.path.join(out_dir, "lockon_set.json"), "w") as f:
        json.dump(made, f, indent=2)
    missing = [d for d in ("Left", "Right", "Back") if d not in made]
    print("lock-on set:", {d: (v["speed"], v["source"], v["mirrored"]) for d, v in made.items()},
          "missing:", missing or "none")
    return made
