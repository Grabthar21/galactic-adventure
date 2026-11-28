"""Mixamo -> Space Piece biped (UE Mannequin bone names) animation transfer, in Blender.

Method (proven on Arthur's sword clips, rewritten 27 Nov 2026):
  1. Rest alignment: each target bone is turned so it points the way the matching Mixamo bone
     points in Mixamo's T-pose (joint -> child joint; UE bones in Blender don't point along
     the limb, so tails are never used).
  2. Every frame, the world rotation CHANGE of each Mixamo bone (from its T-pose) is applied
     on top of that aligned rest, so the target keeps its own proportions and bone axes.
  3. Pelvis movement is scaled by hip height; horizontal travel is moved onto the `root`
     bone (root motion), so the clip moves the character instead of sliding the hips.
  4. ik_* helper bones are baked to follow the feet and hands (UE Mannequin convention).

    import blender_mixamo_retarget as R
    act = R.retarget(src_armature, dst_armature, name="A_Arthur_DodgeRoll", frames=(1, 49))
    R.export_action(dst_armature, act, r"C:/.../A_Arthur_DodgeRoll.fbx")
"""
import bpy
from mathutils import Matrix, Quaternion, Vector

MAP = {
    "Hips": "pelvis", "Spine": "spine_01", "Spine1": "spine_03", "Spine2": "spine_05",
    "Neck": "neck_01", "Head": "head",
}
for side, s in (("Left", "l"), ("Right", "r")):
    MAP.update({
        f"{side}Shoulder": f"clavicle_{s}", f"{side}Arm": f"upperarm_{s}", f"{side}ForeArm": f"lowerarm_{s}",
        f"{side}Hand": f"hand_{s}", f"{side}UpLeg": f"thigh_{s}", f"{side}Leg": f"calf_{s}",
        f"{side}Foot": f"foot_{s}", f"{side}ToeBase": f"ball_{s}",
    })
    for mf, uf in (("Thumb", "thumb"), ("Index", "index"), ("Middle", "middle"), ("Ring", "ring"), ("Pinky", "pinky")):
        for i in (1, 2, 3):
            MAP[f"{side}Hand{mf}{i}"] = f"{uf}_0{i}_{s}"
# bones that keep their own orientation (upright in both T- and A-pose)
NO_ALIGN = {"pelvis", "spine_01", "spine_03", "spine_05", "neck_01", "head"}
# child joint used for the direction of each target bone (target name -> target child)
def _child_of(t):
    side = t[-1]
    table = {f"clavicle_{side}": f"upperarm_{side}", f"upperarm_{side}": f"lowerarm_{side}",
             f"lowerarm_{side}": f"hand_{side}", f"hand_{side}": f"middle_01_{side}",
             f"thigh_{side}": f"calf_{side}", f"calf_{side}": f"foot_{side}", f"foot_{side}": f"ball_{side}"}
    if t in table:
        return table[t]
    for f in ("thumb", "index", "middle", "ring", "pinky"):
        if t.startswith(f + "_0"):
            i = int(t[len(f) + 2])
            return f"{f}_0{i + 1}_{side}" if i < 3 else None
    return None


def _src_name(arm, short):
    for pre in ("mixamorig:", "mixamorig1:", "mixamorig2:", ""):
        if pre + short in arm.data.bones:
            return pre + short
    return None


def _world_rest(arm, bone):
    m = arm.matrix_world @ arm.data.bones[bone].matrix_local
    return m.to_translation(), m.to_quaternion().normalized()


def retarget(src, dst, name, frames=None, root_motion=True, scale=None):
    scn = bpy.context.scene
    act_src = src.animation_data.action
    f0, f1 = frames or (int(act_src.frame_range[0]), int(act_src.frame_range[1]))
    pairs = {}
    for ms, ut in MAP.items():
        sn = _src_name(src, ms)
        if sn and ut in dst.data.bones:
            pairs[ut] = sn
    inv_src = {v: k for k, v in pairs.items()}
    # --- rest alignment (world rotations)
    align = {}
    for t, s in pairs.items():
        _, qt = _world_rest(dst, t)
        if t in NO_ALIGN:
            align[t] = qt
            continue
        tc = _child_of(t)
        sc = pairs.get(tc) if tc else None
        if tc and sc:
            pt, _ = _world_rest(dst, t); pct, _ = _world_rest(dst, tc)
            ps, _ = _world_rest(src, s); pcs, _ = _world_rest(src, sc)
            r = (pct - pt).normalized().rotation_difference((pcs - ps).normalized())
            align[t] = (r @ qt).normalized()
        else:  # last finger joint / ball: same correction as its parent
            par = dst.data.bones[t].parent
            while par and par.name not in align:
                par = par.parent
            if par:
                _, qp = _world_rest(dst, par.name)
                corr = align[par.name] @ qp.inverted()
                align[t] = (corr @ qt).normalized()
            else:
                align[t] = qt
    src_rest = {s: _world_rest(src, s)[1] for s in pairs.values()}
    hips = pairs["pelvis"]
    hips_rest_pos, _ = _world_rest(src, hips)
    pel_rest_pos, _ = _world_rest(dst, "pelvis")
    k = scale or (pel_rest_pos.z / hips_rest_pos.z)
    # --- output action
    if not dst.animation_data:
        dst.animation_data_create()
    act = bpy.data.actions.new(name)
    dst.animation_data.action = act
    aw = dst.matrix_world
    aw_inv = aw.inverted()
    rot_aw = aw.to_quaternion()
    # parents first; ik_* helpers last so they can copy the finished feet/hands
    order = sorted(dst.pose.bones, key=lambda b: (b.name.startswith("ik_") and b.name not in ("ik_foot_root", "ik_hand_root"), len(b.parent_recursive)))
    rest_local = {b.name: b.bone.matrix_local.copy() for b in order}
    start_hips = None
    for f in range(f0, f1 + 1):
        scn.frame_set(f)
        sw = {s: (src.matrix_world @ src.pose.bones[s].matrix) for s in pairs.values()}
        hips_pos = sw[hips].to_translation()
        if start_hips is None:
            start_hips = hips_pos.copy()
        A = {}  # armature-space pose matrices of the target
        for pb in order:
            n = pb.name
            par = pb.parent
            Ap = A[par.name] if par else Matrix.Identity(4)
            Rp = rest_local[par.name] if par else Matrix.Identity(4)
            chain = Ap @ Rp.inverted() @ rest_local[n]  # where the bone sits with no own rotation
            desired = None
            if n in pairs:
                s = pairs[n]
                delta = sw[s].to_quaternion().normalized() @ src_rest[s].inverted()
                qw = (delta @ align[n]).normalized()
                qa = (rot_aw.inverted() @ qw).normalized()
                loc = chain.to_translation()
                if n == "pelvis":  # absolute position; the root bone carries the horizontal travel
                    # horizontal offset is measured from the clip's FIRST frame, not Mixamo's rest,
                    # so a trimmed clip starts with the body over the character (no pop on start/end)
                    start_off = start_hips - hips_rest_pos
                    disp = (hips_pos - hips_rest_pos) - Vector((start_off.x, start_off.y, 0))
                    loc = aw_inv @ (pel_rest_pos + disp * k)
                desired = Matrix.Translation(loc) @ qa.to_matrix().to_4x4()
            elif n == "root" and root_motion:
                rd = (hips_pos - start_hips) * k
                mv = aw_inv.to_3x3() @ Vector((rd.x, rd.y, 0))
                desired = Matrix.Translation(mv) @ rest_local[n]
            elif n.startswith("ik_") and n not in ("ik_foot_root", "ik_hand_root"):
                follow = {"ik_foot_l": "foot_l", "ik_foot_r": "foot_r", "ik_hand_l": "hand_l",
                          "ik_hand_r": "hand_r", "ik_hand_gun": "hand_r"}.get(n)
                if follow and follow in A:
                    desired = A[follow].copy()
            if desired is None:
                A[n] = chain
                basis = Matrix.Identity(4)
            else:
                A[n] = desired
                basis = chain.inverted() @ desired
            if n in pairs or n == "root" or n.startswith("ik_"):
                loc, rot, _ = basis.decompose()
                pb.rotation_mode = "QUATERNION"
                pb.location = loc
                pb.rotation_quaternion = rot
                pb.keyframe_insert("location", frame=f - f0 + 1, group=n)
                pb.keyframe_insert("rotation_quaternion", frame=f - f0 + 1, group=n)
    return act


def export_action(dst, act, path):
    """Armature-only FBX with one baked action, Space Piece recipe (FBX_SCALE_NONE, Y/X axes)."""
    scn = bpy.context.scene
    dst.animation_data.action = act
    scn.frame_start, scn.frame_end = int(act.frame_range[0]), int(act.frame_range[1])
    vl = bpy.context.view_layer
    for o in scn.objects:
        o.select_set(False)
    dst.select_set(True)
    vl.objects.active = dst
    with bpy.context.temp_override(window=bpy.context.window, scene=scn, view_layer=vl,
                                   active_object=dst, selected_objects=[dst]):
        bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"ARMATURE"},
                                 apply_scale_options="FBX_SCALE_NONE", global_scale=1.0,
                                 primary_bone_axis="Y", secondary_bone_axis="X", add_leaf_bones=False,
                                 bake_anim=True, bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
                                 bake_anim_force_startend_keying=True, bake_anim_simplify_factor=0.0)
    return path


def ground_clip(dst, mesh, act, margin=0.005, rest_floor=None):
    """Lift the pelvis on frames where the character's lowest point goes below the floor.
    Different proportions (Arthur vs the Mixamo model) change where the body touches down,
    so contact poses (rolls, falls, crouches) sink. Lift is the minimum needed per frame,
    widened by one frame and smoothed so it never jitters. Returns the lift per frame (m)."""
    import numpy as np
    scn = bpy.context.scene
    dst.animation_data.action = act
    f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
    mw = np.array(mesh.matrix_world)

    def lowest():
        dg = bpy.context.evaluated_depsgraph_get()
        me = mesh.evaluated_get(dg).to_mesh()
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        z = co.reshape(-1, 3) @ mw[2, :3] + mw[2, 3]
        mesh.evaluated_get(dg).to_mesh_clear()
        return float(z.min())
    if rest_floor is None:
        rest_floor = 0.0
    need = []
    for f in range(f0, f1 + 1):
        scn.frame_set(f)
        need.append(max(0.0, rest_floor - margin - lowest()) if lowest() < rest_floor - margin else 0.0)
    need = np.array(need)
    wide = np.maximum.reduce([np.roll(need, 1), need, np.roll(need, -1)])
    wide[0], wide[-1] = max(need[0], need[1]), max(need[-1], need[-2])
    k = np.array([0.25, 0.5, 0.25])
    lift = np.maximum(np.convolve(np.pad(wide, 1, mode="edge"), k, mode="valid"), need)
    pel = dst.data.bones["pelvis"]
    dz_local = pel.matrix_local.to_3x3().inverted() @ (dst.matrix_world.to_3x3().inverted() @ Vector((0, 0, 1)))
    fcs = {i: fc for fc in _fcurves(act) if fc.data_path == 'pose.bones["pelvis"].location' for i in [fc.array_index]}
    for i, f in enumerate(range(f0, f1 + 1)):
        if lift[i] <= 0:
            continue
        for ax in range(3):
            fc = fcs[ax]
            for kp in fc.keyframe_points:
                if int(round(kp.co.x)) == f:
                    kp.co.y += dz_local[ax] * lift[i]
                    kp.handle_left.y += dz_local[ax] * lift[i]
                    kp.handle_right.y += dz_local[ax] * lift[i]
    for fc in fcs.values():
        fc.update()
    return lift


def _fcurves(act):
    """Blender 4.4+ slotted actions keep fcurves in layers/strips/channelbags."""
    if hasattr(act, "fcurves") and len(act.fcurves):
        return list(act.fcurves)
    out = []
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for cb in getattr(strip, "channelbags", []):
                out += list(cb.fcurves)
    return out
