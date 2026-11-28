"""Review renders that show a character the way it is actually seen. Runs in Blender.

game_camera(): the UE third-person camera (spring arm 4 m, about 15 deg above, 90 deg FOV,
    1920x1080), from behind and from the front. Judge detail at THIS size: small details that
    don't show here are not worth a fix round. Reports how tall the character is on screen.
lineup(): the character next to Arthur (or a 160 cm marker), a door (2.2 m), a fence (1.1 m)
    and the sword (88 cm), front-on and orthographic at a fixed 250 px per metre, so every
    lineup from every character can be laid side by side and compared.

Usage (inside Blender):
    import blender_review_renders as r
    r.game_camera(["SK_New"], out_dir, "New")
    r.lineup(["SK_New"], out_dir, "New", reference=["SK_Arthur"])
"""
import math
import os

import bpy
from mathutils import Vector

GAME = {"arm_length": 4.0, "pitch_deg": 15.0, "fov_deg": 90.0, "res": (1920, 1080),
        "target_frac": 0.62}  # camera looks at ~62% of the character's height (capsule top-ish)
PX_PER_M = 250
BG = (0.24, 0.24, 0.24, 1)


def _bbox(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    mn = Vector((1e9,) * 3)
    mx = Vector((-1e9,) * 3)
    for o in objs:
        oe = o.evaluated_get(dg)
        for c in oe.bound_box:
            w = o.matrix_world @ Vector(c)
            mn = Vector(map(min, mn, w))
            mx = Vector(map(max, mx, w))
    return mn, mx


class _Stage:
    """Temporary scene holding only the given objects, with the standard lights."""

    def __init__(self, objs, name):
        self.src = bpy.context.window.scene if bpy.context.window else bpy.context.scene
        self.scn = bpy.data.scenes.new(name)
        self.objs = []
        for o in objs:
            if o.name not in self.scn.collection.objects:
                self.scn.collection.objects.link(o)
            if o.parent and o.parent.name not in self.scn.collection.objects:
                self.scn.collection.objects.link(o.parent)
        s = self.scn
        # Eevee on Henry (GPU). PIPELINE_RENDER_ENGINE=CYCLES for machines without a GPU.
        try:
            s.render.engine = os.environ.get("PIPELINE_RENDER_ENGINE", "BLENDER_EEVEE")
        except TypeError:
            s.render.engine = "CYCLES"
        if s.render.engine == "CYCLES":
            s.cycles.samples = 16
            s.cycles.use_denoising = True
        s.view_settings.view_transform = "AgX"
        s.world = bpy.data.worlds.new(name + "_World")
        s.world.use_nodes = True
        s.world.node_tree.nodes["Background"].inputs[0].default_value = BG
        for nm, e, rot in (("Key", 3.0, (50, 0, -35)), ("Fill", 1.0, (60, 0, 40)), ("Rim", 1.5, (60, 0, 180))):
            L = bpy.data.objects.new(f"{name}_{nm}", bpy.data.lights.new(nm, "SUN"))
            L.data.energy = e
            L.data.angle = math.radians(8)
            L.rotation_euler = [math.radians(a) for a in rot]
            s.collection.objects.link(L)
            self.objs.append(L)
        self.cam = bpy.data.objects.new(name + "_Cam", bpy.data.cameras.new(name + "_Cam"))
        s.collection.objects.link(self.cam)
        s.camera = self.cam
        self.objs.append(self.cam)

    def add(self, obj):
        self.scn.collection.objects.link(obj)
        self.objs.append(obj)
        return obj

    def render(self, path):
        self.scn.render.filepath = path
        bpy.ops.render.render(write_still=True, scene=self.scn.name)
        return path

    def close(self):
        for o in self.objs:
            bpy.data.objects.remove(o, do_unlink=True)
        w = self.scn.world
        bpy.data.scenes.remove(self.scn)
        if w:
            bpy.data.worlds.remove(w)
        if bpy.context.window:
            bpy.context.window.scene = self.src


def game_camera(meshes, out_dir, name):
    objs = [bpy.data.objects[m] if isinstance(m, str) else m for m in meshes]
    os.makedirs(out_dir, exist_ok=True)
    mn, mx = _bbox(objs)
    h = mx.z - mn.z
    c = (mn + mx) / 2
    st = _Stage(objs, "GameCam")
    s = st.scn
    s.render.resolution_x, s.render.resolution_y = GAME["res"]
    cam = st.cam
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.angle = math.radians(GAME["fov_deg"])
    target = Vector((c.x, c.y, mn.z + GAME["target_frac"] * h))
    p = math.radians(GAME["pitch_deg"])
    out = {"renders": [], "screen_height_px": None}
    for view, sgn in (("behind", 1), ("front", -1)):
        # character faces -Y: behind = +Y side
        cam.location = target + Vector((0, sgn * math.cos(p), math.sin(p))) * GAME["arm_length"]
        cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
        out["renders"].append(st.render(os.path.join(out_dir, f"{name}_game_{view}.png")))
    # on-screen height with the front camera (pinhole maths; no depsgraph needed)
    from mathutils import Matrix
    view = Matrix.LocRotScale(cam.location, cam.rotation_euler.to_quaternion(), None).inverted()
    w, hh = GAME["res"]
    tan_v = math.tan(math.radians(GAME["fov_deg"]) / 2) * hh / w

    def sy(pt):
        q = view @ pt
        return (q.y / -q.z) / tan_v * hh / 2
    out["screen_height_px"] = round(abs(sy(Vector((c.x, c.y, mx.z))) - sy(Vector((c.x, c.y, mn.z)))))
    st.close()
    return out


def _box(name, size, loc, colour):
    bpy.ops.mesh.primitive_cube_add(size=1)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    o.location = loc
    m = bpy.data.materials.new(name + "_M")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*colour, 1)
    m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
    o.data.materials.append(m)
    for col in list(o.users_collection):
        col.objects.unlink(o)
    return o


def lineup(meshes, out_dir, name, reference=None):
    """Front orthographic lineup at a fixed scale. reference: Arthur's meshes if in the file."""
    objs = [bpy.data.objects[m] if isinstance(m, str) else m for m in meshes]
    refs = [bpy.data.objects[m] if isinstance(m, str) else m for m in (reference or [])
            if (m if not isinstance(m, str) else bpy.data.objects.get(m))]
    os.makedirs(out_dir, exist_ok=True)
    mn, mx = _bbox(objs)
    h = mx.z - mn.z
    st = _Stage(objs + refs, "Lineup")
    s = st.scn
    # place: [Arthur] [character] [door] [fence] [sword]; move things temporarily
    moved = []

    def shift(objlist, dx):
        roots = {o.parent if o.parent else o for o in objlist}
        for r in roots:
            moved.append((r, r.location.copy()))
            r.location.x += dx

    cx = (mn.x + mx.x) / 2
    shift(objs, -cx)
    x = (mx.x - mn.x) / 2 + 0.35
    items = []
    if refs:
        rmn, rmx = _bbox(refs)
        shift(refs, -(rmn.x + rmx.x) / 2 - (x + (rmx.x - rmn.x) / 2))
        left_edge = -(x + (rmx.x - rmn.x))
    else:  # 160 cm marker standing in for Arthur
        items.append(st.add(_box("Arthur160", (0.30, 0.05, 1.60), (-(x + 0.15), 0, 0.80), (0.45, 0.30, 0.22))))
        left_edge = -(x + 0.30)
    door_x = x + 0.6
    items += [st.add(_box("DoorL", (0.10, 0.10, 2.2), (door_x - 0.5, 0, 1.1), (0.35, 0.22, 0.15))),
              st.add(_box("DoorR", (0.10, 0.10, 2.2), (door_x + 0.5, 0, 1.1), (0.35, 0.22, 0.15))),
              st.add(_box("DoorTop", (1.10, 0.10, 0.10), (door_x, 0, 2.2), (0.35, 0.22, 0.15)))]
    fx = door_x + 1.0
    items += [st.add(_box("FencePost", (0.10, 0.10, 1.1), (fx + 0.1, 0, 0.55), (0.48, 0.34, 0.20))),
              st.add(_box("FenceRail", (0.8, 0.06, 0.08), (fx + 0.45, 0, 1.05), (0.48, 0.34, 0.20)))]
    sx = fx + 1.15
    items.append(st.add(_box("Sword88", (0.04, 0.02, 0.88), (sx, 0, 0.44), (0.75, 0.75, 0.78))))
    # height marks every 50 cm behind everything
    right_edge = sx + 0.3
    for k in range(1, 6):
        items.append(st.add(_box(f"Mark{k}", (right_edge - left_edge + 0.6, 0.005, 0.006),
                                 ((left_edge + right_edge) / 2, 0.5, k * 0.5), (0.35, 0.35, 0.35))))
    width_m = right_edge - left_edge + 0.6
    top_m = max(2.6, h + 0.3)
    s.render.resolution_x = int(width_m * PX_PER_M)
    s.render.resolution_y = int(top_m * PX_PER_M)
    cam = st.cam
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = max(width_m, top_m)
    cam.location = ((left_edge + right_edge) / 2, -10, top_m / 2 - 0.05)
    cam.rotation_euler = (math.radians(90), 0, 0)
    path = st.render(os.path.join(out_dir, f"{name}_lineup.png"))
    for r, loc in moved:
        r.location = loc
    mats = [m for o in items for m in o.data.materials]
    st.close()
    for m in mats:
        bpy.data.materials.remove(m)
    return {"renders": [path], "height_cm": round(h * 100, 1),
            "vs_arthur_pct": round(h / 1.60 * 100) if not refs else round(h / (_bbox(refs)[1].z - _bbox(refs)[0].z) * 100)}
