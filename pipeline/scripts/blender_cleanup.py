"""Blender cleanup step for Space Piece characters (standard section 6, step 3).

Run inside Blender after blender_import_check.run(), which leaves the source in a scene
named "PipelineCheck". Steps, always in this order:
  1. keep the source untouched as <name>_HI (hidden), work on a copy <name>_LO
  2. scale to the entry's height, apply transforms
  3. delete debris (pieces under 10 faces)
  4. reduce in two passes on selections: the head region keeps more detail
     (head_ratio) than the body (body_ratio). Reducing per selection, not with one
     crushing pass, is what protects the face and the edges of separate clothing pieces.
  5. copy the material, downscale textures to 2048 and save them with standard names
  6. save a .blend copy

Pilot (Arthur, 26 Nov 2026): head_ratio 0.35, body_ratio 0.175 -> 191,104 to 39,329
triangles; face visually unchanged.
"""
import os

import bmesh
import bpy

DEBRIS_FACES = 10


def run(name, height_cm, out_dir, head_frac=0.80, head_ratio=0.35, body_ratio=0.175,
        tex_size=2048, scene="PipelineCheck"):
    scn = bpy.data.scenes[scene]
    bpy.context.window.scene = scn
    src = [o for o in scn.objects if o.type == "MESH"][0]
    src.name = f"{name}_HI"
    if src.parent:
        mw = src.matrix_world.copy()
        src.parent = None
        src.matrix_world = mw
    bpy.ops.object.select_all(action="DESELECT")
    src.select_set(True)
    bpy.context.view_layer.objects.active = src
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    s = (height_cm / 100) / src.dimensions.z
    src.scale = (s, s, s)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    lo = src.copy()
    lo.data = src.data.copy()
    lo.name = f"{name}_LO"
    scn.collection.objects.link(lo)
    src.hide_set(True)

    bm = bmesh.new()
    bm.from_mesh(lo.data)
    bm.faces.ensure_lookup_table()
    seen, kill = set(), []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, isl = [f], []
        seen.add(f.index)
        while stack:
            c = stack.pop()
            isl.append(c)
            for e in c.edges:
                for g in e.link_faces:
                    if g.index not in seen:
                        seen.add(g.index)
                        stack.append(g)
        if len(isl) < DEBRIS_FACES:
            kill += isl
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    zs = [v.co.z for v in bm.verts]
    cut = min(zs) + head_frac * (max(zs) - min(zs))
    bm.to_mesh(lo.data)
    bm.free()

    bpy.ops.object.select_all(action="DESELECT")
    lo.select_set(True)
    bpy.context.view_layer.objects.active = lo
    for is_head, ratio in ((True, head_ratio), (False, body_ratio)):
        bpy.ops.object.mode_set(mode="EDIT")
        ebm = bmesh.from_edit_mesh(lo.data)
        for f in ebm.faces:
            f.select_set((f.calc_center_median().z > cut) == is_head)
        ebm.select_flush_mode()
        bmesh.update_edit_mesh(lo.data)
        bpy.ops.mesh.decimate(ratio=ratio)
        bpy.ops.object.mode_set(mode="OBJECT")

    os.makedirs(out_dir, exist_ok=True)
    mat = lo.material_slots[0].material.copy()
    mat.name = f"M_{name}"
    lo.material_slots[0].material = mat
    suffix = {"basecolor": "_D", "normal": "_N", "rm": "_RM"}
    for n in mat.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image:
            key = next((k for k in suffix if k in n.image.name.lower()), None)
            if not key:
                continue
            img = n.image.copy()
            img.name = f"T_{name}{suffix[key]}"
            img.scale(tex_size, tex_size)
            ext = ".png" if key == "normal" else ".jpg"
            img.filepath_raw = os.path.join(out_dir, img.name + ext)
            img.file_format = "PNG" if ext == ".png" else "JPEG"
            img.save()
            n.image = img
    lo.name = f"SK_{name}_Clean"
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, f"{name}_clean.blend"), copy=True)
    tris = sum(len(p.vertices) - 2 for p in lo.data.polygons)
    print(f"{name}: {tris:,} triangles, saved to {out_dir}")
    return lo
