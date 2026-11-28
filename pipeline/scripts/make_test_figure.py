"""Builds rigged stand-in figures for testing the pipeline checks without real art.

make_figure("Good", x=-0.6)                    -> on-style teen: A-pose, feet straight
make_figure("Bad", x=0.6, feet_out=28,
            arm_angle=4, big_head=1.5)         -> Arthur's old faults: duck feet, hands on the
                                                  thighs, oversized head
Bones use UE Mannequin names (incl. fingers), the character faces -Y, left = +X, 160 cm tall.
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

H = 1.60


def _skin_body(name, pts, edges, radii):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in pts], edges, [])
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    mod = ob.modifiers.new("Skin", "SKIN")
    mod.use_smooth_shade = True
    for i, r in enumerate(radii):
        ob.data.skin_vertices[0].data[i].radius = (r, r)
    ob.data.skin_vertices[0].data[0].use_root = True
    ob.modifiers.new("Sub", "SUBSURF").levels = 1
    bpy.context.view_layer.objects.active = ob
    for m in list(ob.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)
    return ob


def _texture(name, colours, noise=0.0, black=0.0, size=256, seed=1):
    rng = np.random.default_rng(seed)
    a = np.ones((size, size, 4), dtype=np.float32)
    n = len(colours)
    for i, c in enumerate(colours):
        a[i * size // n:(i + 1) * size // n, :, :3] = c
    if noise:
        a[..., :3] = np.clip(a[..., :3] + rng.normal(0, noise, (size, size, 3)), 0, 1)
    if black:
        a[: int(size * black), :, :3] = 0.01
    img = bpy.data.images.new(name, size, size, alpha=True)
    img.pixels.foreach_set(a.ravel())
    img.pack()  # keep the pixels when the .blend is saved
    return img


def _material(name, img, rough=0.85, spec=0.25, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    t = m.node_tree.nodes.new("ShaderNodeTexImage")
    t.image = img
    m.node_tree.links.new(t.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    b.inputs["Specular IOR Level"].default_value = spec
    b.inputs["Metallic"].default_value = metal
    return m


def make_figure(tag, x=0.0, feet_out=6.0, arm_angle=28.0, big_head=1.0, photo=False):
    s = H / 0.98  # proportions from Arthur's measured joints (model 0.98 tall)
    J = {
        "pelvis": (0, 0, .505), "spine_01": (0, 0, .555), "spine_02": (0, 0, .615),
        "spine_03": (0, 0, .690), "neck_01": (0, 0, .795), "head": (0, 0, .832),
        "head_top": (0, 0, .832 + 0.10 * big_head),
        "thigh_l": (.05, 0, .505), "calf_l": (.065, 0, .29), "foot_l": (.083, .01, .082),
        "thigh_r": (-.05, 0, .505), "calf_r": (-.065, 0, .29), "foot_r": (-.083, .01, .082),
    }
    # arms: shoulder fixed, hang at arm_angle from vertical
    for side, sx in (("l", 1), ("r", -1)):
        sh = Vector((sx * .087, 0, .752))
        a = math.radians(arm_angle)
        d = Vector((sx * math.sin(a), -0.05, -math.cos(a))).normalized()
        J[f"clavicle_{side}"] = (sx * .012, 0, .775)
        J[f"upperarm_{side}"] = tuple(sh)
        J[f"lowerarm_{side}"] = tuple(sh + d * .124)
        J[f"hand_{side}"] = tuple(sh + d * .240)
        J[f"handend_{side}"] = tuple(sh + d * .275)
        J[f"fingertip_{side}"] = tuple(sh + d * .318)
        f = math.radians(feet_out)
        toe = Vector((J[f"foot_{side}"][0] + sx * math.sin(f) * .11, J[f"foot_{side}"][1] - math.cos(f) * .11, .02))
        J[f"ball_{side}"] = tuple(Vector(J[f"foot_{side}"]) + (toe - Vector(J[f"foot_{side}"])) * 0.62 + Vector((0, 0, -.04)))
        J[f"toe_{side}"] = tuple(toe)
    P = {k: Vector(v) * s + Vector((x, 0, 0)) for k, v in J.items()}

    # ---- skin skeleton (body mesh)
    names = ["pelvis", "spine_02", "neck_01", "head",
             "thigh_l", "calf_l", "foot_l", "toe_l", "thigh_r", "calf_r", "foot_r", "toe_r",
             "upperarm_l", "lowerarm_l", "hand_l", "fingertip_l",
             "upperarm_r", "lowerarm_r", "hand_r", "fingertip_r"]
    idx = {n: i for i, n in enumerate(names)}
    E = [("pelvis", "spine_02"), ("spine_02", "neck_01"), ("neck_01", "head"),
         ("pelvis", "thigh_l"), ("thigh_l", "calf_l"), ("calf_l", "foot_l"), ("foot_l", "toe_l"),
         ("pelvis", "thigh_r"), ("thigh_r", "calf_r"), ("calf_r", "foot_r"), ("foot_r", "toe_r"),
         ("spine_02", "upperarm_l"), ("upperarm_l", "lowerarm_l"), ("lowerarm_l", "hand_l"), ("hand_l", "fingertip_l"),
         ("spine_02", "upperarm_r"), ("upperarm_r", "lowerarm_r"), ("lowerarm_r", "hand_r"), ("hand_r", "fingertip_r")]
    R = {"pelvis": .085, "spine_02": .075, "neck_01": .03, "head": .03, "thigh_l": .045, "calf_l": .035,
         "foot_l": .03, "toe_l": .028, "upperarm_l": .03, "lowerarm_l": .025, "hand_l": .02, "fingertip_l": .018}
    radii = [R.get(n, R.get(n[:-1] + "l", .03)) * s for n in names]
    body = _skin_body(f"{tag}_Body", [P[n] for n in names], [(idx[a], idx[b]) for a, b in E], radii)
    # head sphere joined into the body
    bm = bmesh.new()
    bm.from_mesh(body.data)
    hc = (P["head"] + P["head_top"]) / 2 + Vector((0, -0.005, 0.02 * s))
    r = 0.085 * s * big_head
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16, radius=r,
                              matrix=__import__("mathutils").Matrix.Translation(hc))
    bm.to_mesh(body.data)
    bm.free()
    J_top = hc.z + r

    # ---- armature with UE names + fingers
    ad = bpy.data.armatures.new(f"{tag}_Rig")
    arm = bpy.data.objects.new(f"{tag}_Armature", ad)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = ad.edit_bones

    def bone(n, h, t, parent=None):
        b = eb.new(n)
        b.head, b.tail = h, t
        if parent:
            b.parent = eb[parent]
        return b
    bone("root", Vector((x, 0, 0)), Vector((x, -0.1, 0)))
    bone("pelvis", P["pelvis"], P["spine_01"], "root")
    bone("spine_01", P["spine_01"], P["spine_02"], "pelvis")
    bone("spine_02", P["spine_02"], P["spine_03"], "spine_01")
    bone("spine_03", P["spine_03"], P["neck_01"], "spine_02")
    bone("neck_01", P["neck_01"], P["head"], "spine_03")
    bone("head", P["head"], Vector((x, 0, J_top)), "neck_01")
    for sd in ("l", "r"):
        bone(f"clavicle_{sd}", P[f"clavicle_{sd}"], P[f"upperarm_{sd}"], "spine_03")
        bone(f"upperarm_{sd}", P[f"upperarm_{sd}"], P[f"lowerarm_{sd}"], f"clavicle_{sd}")
        bone(f"lowerarm_{sd}", P[f"lowerarm_{sd}"], P[f"hand_{sd}"], f"upperarm_{sd}")
        bone(f"hand_{sd}", P[f"hand_{sd}"], P[f"handend_{sd}"], f"lowerarm_{sd}")
        # five fingers fanned across the hand, 3 bones each
        d = (P[f"fingertip_{sd}"] - P[f"handend_{sd}"])
        for k, fname in enumerate(["thumb", "index", "middle", "ring", "pinky"]):
            off = Vector((0, (k - 2) * 0.008 * s, 0))
            a0 = P[f"handend_{sd}"] + off
            prev = f"hand_{sd}"
            for j in (1, 2, 3):
                h0 = a0 + d * ((j - 1) / 3)
                t0 = a0 + d * (j / 3)
                bone(f"{fname}_0{j}_{sd}", h0, t0, prev)
                prev = f"{fname}_0{j}_{sd}"
        bone(f"thigh_{sd}", P[f"thigh_{sd}"], P[f"calf_{sd}"], "pelvis")
        bone(f"calf_{sd}", P[f"calf_{sd}"], P[f"foot_{sd}"], f"thigh_{sd}")
        bone(f"foot_{sd}", P[f"foot_{sd}"], P[f"ball_{sd}"], f"calf_{sd}")
        bone(f"ball_{sd}", P[f"ball_{sd}"], P[f"toe_{sd}"], f"foot_{sd}")
    bpy.ops.object.mode_set(mode="OBJECT")

    # ---- weights (heat), parenting
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    if not body.vertex_groups or not any(len(v.groups) for v in body.data.vertices):
        raise RuntimeError("automatic weights failed")

    # ---- material
    warm = [(0.28, 0.19, 0.15), (0.35, 0.24, 0.20), (0.52, 0.32, 0.24), (0.73, 0.54, 0.44), (0.76, 0.64, 0.56)]
    img = _texture(f"T_{tag}_D", warm, noise=0.14 if photo else 0.0, black=0.2 if photo else 0.0)
    body.data.materials.append(_material(f"M_{tag}", img, rough=0.3 if photo else 0.85,
                                         spec=0.5 if photo else 0.25, metal=0.5 if photo else 0.0))
    # UVs so the texture shows
    uv = body.data.uv_layers.new(name="UVMap")
    top = max(v.co.z for v in body.data.vertices)
    for loop in body.data.loops:
        co = body.data.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = (0.5 + math.atan2(co.x - x, co.y) / (2 * math.pi), co.z / top)
    return body, arm
