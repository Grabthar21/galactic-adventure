"""Checks blender_mixamo_retarget.py options on tiny fake skeletons (run: python -I test_retarget_options.py
with the bpy module, or blender -b -P). Clip: walks 1 m forward, left leg swings forward mid-clip.
  mirror   -> the RIGHT leg swings instead, travel unchanged
  in_place -> no pelvis/root travel, leg swing kept
Sideways travel flipping under mirror was checked the same way (27-28 Nov 2026).
"""
import sys, math
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Vector, Quaternion
import blender_mixamo_retarget as R

bpy.ops.wm.read_factory_settings(use_empty=True)
def arm(name, bones):
    a = bpy.data.armatures.new(name); o = bpy.data.objects.new(name, a)
    bpy.context.scene.collection.objects.link(o)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.mode_set(mode="EDIT")
    for n, h, t, p in bones:
        b = a.edit_bones.new(n); b.head = h; b.tail = t
        if p: b.parent = a.edit_bones[p]
    bpy.ops.object.mode_set(mode="OBJECT")
    return o
m = "mixamorig:"
# Mixamo-like: character faces -Y, left side = +X
src = arm("MIX", [
 (m+"Hips",(0,0,1),(0,0,1.1),None), (m+"Spine",(0,0,1.1),(0,0,1.3),m+"Hips"),
 (m+"LeftUpLeg",(0.1,0,1),(0.1,0,0.55),m+"Hips"), (m+"LeftLeg",(0.1,0,0.55),(0.1,0,0.1),m+"LeftUpLeg"),
 (m+"LeftFoot",(0.1,0,0.1),(0.1,-0.1,0.02),m+"LeftLeg"),
 (m+"RightUpLeg",(-0.1,0,1),(-0.1,0,0.55),m+"Hips"), (m+"RightLeg",(-0.1,0,0.55),(-0.1,0,0.1),m+"RightUpLeg"),
 (m+"RightFoot",(-0.1,0,0.1),(-0.1,-0.1,0.02),m+"RightLeg")])
dst = arm("UE", [
 ("root",(0,0,0),(0,0.1,0),None), ("pelvis",(0,0,0.9),(0,0,1.0),"root"), ("spine_01",(0,0,1.0),(0,0,1.2),"pelvis"),
 ("thigh_l",(0.09,0,0.9),(0.09,0,0.5),"pelvis"), ("calf_l",(0.09,0,0.5),(0.09,0,0.09),"thigh_l"), ("foot_l",(0.09,0,0.09),(0.09,-0.1,0.02),"calf_l"),
 ("thigh_r",(-0.09,0,0.9),(-0.09,0,0.5),"pelvis"), ("calf_r",(-0.09,0,0.5),(-0.09,0,0.09),"thigh_r"), ("foot_r",(-0.09,0,0.09),(-0.09,-0.1,0.02),"calf_r")])
# clip: hips travel 1 m along -Y over 20 frames, left thigh swings forward 40 deg at frame 11
src.animation_data_create(); act = bpy.data.actions.new("clip"); src.animation_data.action = act
for f, (dy, ang) in {1:(0,0), 11:(-0.5,40), 21:(-1.0,0)}.items():
    pb = src.pose.bones[m+"Hips"]; pb.location = (0, 0, dy)  # bone local Y=up... set via matrix below
    hp = src.pose.bones[m+"Hips"]
    hp.matrix = __import__("mathutils").Matrix.Translation((0, dy, 1)) @ hp.bone.matrix_local.to_3x3().to_4x4()
    bpy.context.view_layer.update()
    hp.keyframe_insert("location", frame=f)
    lu = src.pose.bones[m+"LeftUpLeg"]; lu.rotation_mode="XYZ"
    lu.rotation_euler = (math.radians(-ang), 0, 0)  # local X; thigh points down, so this swings forward/back
    lu.keyframe_insert("rotation_euler", frame=f)

def foot_y(arm_obj, bone, f):
    bpy.context.scene.frame_set(f)
    return (arm_obj.matrix_world @ arm_obj.pose.bones[bone].matrix).to_translation()

print("SOURCE f11 L foot", foot_y(src, m+"LeftFoot", 11), "R foot", foot_y(src, m+"RightFoot", 11))
res = {}
for label, kw in (("plain", {}), ("mirror", {"mirror": True}), ("in_place", {"in_place": True})):
    a = R.retarget(src, dst, "A_"+label, frames=(1, 21), **kw)
    dst.animation_data.action = a
    src.animation_data.action = act
    bpy.context.scene.frame_set(11)
    fl = foot_y(dst, "foot_l", 11); fr = foot_y(dst, "foot_r", 11)
    p1 = foot_y(dst, "pelvis", 1); p21 = foot_y(dst, "pelvis", 21); r21 = foot_y(dst, "root", 21)
    res[label] = (fl, fr, (p21 - p1).y, r21.y)
    print(f"{label:9s} f11 foot_l {tuple(round(v,3) for v in fl)} foot_r {tuple(round(v,3) for v in fr)} | pelvis travel {round((p21-p1).y,3)} root {round(r21.y,3)}")

pl, mi, ip = res["plain"], res["mirror"], res["in_place"]
assert pl[0].z > 0.2 and pl[1].z < 0.12, "plain: left foot should be lifted"
assert mi[1].z > 0.2 and mi[0].z < 0.12, "mirror: right foot should be lifted"
assert abs(mi[2] - pl[2]) < 1e-3, "mirror keeps forward travel"
assert abs(ip[2]) < 1e-3 and abs(ip[3]) < 1e-3, "in_place: no travel"
assert ip[0].z > 0.2, "in_place keeps the leg swing"
print("ALL OK")
