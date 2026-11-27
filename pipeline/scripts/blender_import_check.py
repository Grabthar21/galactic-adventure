"""Blender import check for Space Piece characters and creatures.

Run inside Blender. Imports a source model (GLB/GLTF/FBX) into a fresh scene named
"PipelineCheck" and reports raw-model health against the pipeline standard
(claude project doc `Character_Pipeline_Standard.md`).

Usage:
    import blender_import_check as c
    c.run(r"C:/path/model.glb", cls="hero", height_cm=160)
"""
import time

import bmesh
import bpy

BUDGETS = {"hero": 40000, "background": 20000, "creature": 15000,
           "creature_large": 25000, "attachment": 2000}
MAX_TEXTURE = 2048
DEBRIS_FACES = 10


def _islands(bm):
    seen, sizes = set(), []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, n = [f], 0
        seen.add(f.index)
        while stack:
            c = stack.pop()
            n += 1
            for e in c.edges:
                for g in e.link_faces:
                    if g.index not in seen:
                        seen.add(g.index)
                        stack.append(g)
        sizes.append(n)
    return sizes


def _flipped(bm):
    flips = 0
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        v1, v2 = e.verts

        def forward(f):
            vs = list(f.verts)
            i = vs.index(v1)
            return vs[(i + 1) % len(vs)] is v2

        f1, f2 = e.link_faces
        if forward(f1) == forward(f2):
            flips += 1
    return flips


def run(path, cls="hero", height_cm=None):
    t0 = time.time()
    scn = bpy.data.scenes.new("PipelineCheck")
    bpy.context.window.scene = scn
    before = set(bpy.data.objects)
    if path.lower().endswith((".glb", ".gltf")):
        bpy.ops.import_scene.gltf(filepath=path)
    else:
        bpy.ops.import_scene.fbx(filepath=path)
    objs = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in objs if o.type == "MESH"]
    arms = [o for o in objs if o.type == "ARMATURE"]

    tris = nonman = loose = flips = 0
    sizes, mats, imgs = [], set(), set()
    mn, mx = [1e9] * 3, [-1e9] * 3
    for o in meshes:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.transform(o.matrix_world)
        bm.faces.ensure_lookup_table()
        tris += sum(len(f.verts) - 2 for f in bm.faces)
        nonman += sum(1 for e in bm.edges if len(e.link_faces) > 2)
        loose += sum(1 for v in bm.verts if not v.link_edges)
        flips += _flipped(bm)
        sizes += _islands(bm)
        for v in bm.verts:
            for i in range(3):
                mn[i] = min(mn[i], v.co[i])
                mx[i] = max(mx[i], v.co[i])
        bm.free()
        for s in o.material_slots:
            if s.material:
                mats.add(s.material.name)
                if s.material.node_tree:
                    for n in s.material.node_tree.nodes:
                        if n.type == "TEX_IMAGE" and n.image:
                            imgs.add((n.image.name, tuple(n.image.size)))

    out = []
    limit = BUDGETS[cls]
    out.append(("AUTO-FIX" if tris > limit else "PASS", "triangles", f"{tris:,} (limit {limit:,})"))
    debris = [s for s in sizes if s < DEBRIS_FACES]
    out.append(("AUTO-FIX" if debris else "PASS", "debris", f"{len(debris)} tiny pieces under {DEBRIS_FACES} faces"))
    out.append(("INFO", "shells", f"{len(sizes)} separate pieces, largest {max(sizes) if sizes else 0:,} faces"))
    out.append(("AUTO-FIX" if loose else "PASS", "loose verts", str(loose)))
    out.append(("AUTO-FIX" if flips else "PASS", "flipped normals", f"{flips} inconsistent edges"))
    out.append(("ASK" if nonman else "PASS", "non-manifold", f"{nonman} edges"))
    h = round((mx[2] - mn[2]) * 100)
    if height_cm:
        ok = abs(h - height_cm) / height_cm < 0.1
        out.append(("PASS" if ok else "AUTO-FIX", "scale", f"{h} cm tall, target {height_cm} cm"))
    else:
        out.append(("INFO", "scale", f"{h} cm tall"))
    big = [i for i in imgs if max(i[1]) > MAX_TEXTURE]
    out.append(("AUTO-FIX" if big else "PASS", "textures", f"{len(imgs)}; {len(big)} above {MAX_TEXTURE}px"))
    out.append(("PASS" if len(mats) <= 4 else "AUTO-FIX", "materials", str(len(mats))))
    out.append(("PASS" if arms else "NEEDS RIG", "armature",
                f"{len(arms[0].data.bones)} bones" if arms else "none"))
    for s, c, d in out:
        print(f"{s:<9} | {c} | {d}")
    print(f"time {time.time() - t0:.1f} s")
    return out
