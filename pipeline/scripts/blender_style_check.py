"""Space Piece style check (Blender). Runs after cleanup/rig, before export.

Checks a character against pipeline/style/style_rules.json and the Art Style Guide:
  - proportions (head, arm and leg size compared with height) from the rig
  - base-colour textures: too dark / too bright / too grey / neon / noisy (photo-like)
  - materials: matte roughness, low specular, no metal except metal parts
  - face: hero has its own eye material, eye texture big enough
and renders the standard review turnaround (same lights, camera and background
every time) so characters are always judged side by side under equal conditions.

Fix rules follow the pipeline standard: material values are auto-fixed (logged),
anything that changes the shape or the painted look is only reported (ASK).

Usage (inside Blender):
    import blender_style_check as s
    rep = s.run(meshes=["SK_Arthur"], armature="Armature", group="human_teen",
                hero=True, height_cm=160, fix=True, out_dir=r"C:/.../review", name="Arthur")
"""
import json
import math
import os

import bpy
from mathutils import Vector

try:
    import numpy as np
except ImportError:  # Blender always ships numpy; this keeps linters quiet
    np = None

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "."
RULES_PATH = os.path.join(HERE, "..", "style", "style_rules.json")


def load_rules(path=None):
    with open(path or RULES_PATH) as f:
        return json.load(f)


# ------------------------------------------------------------------ helpers
def _result(report, check, status, detail, value=None):
    report["checks"].append({"check": check, "status": status, "detail": detail, "value": value})


def _world_bbox(objs):
    mn = Vector((1e9, 1e9, 1e9))
    mx = Vector((-1e9, -1e9, -1e9))
    dg = bpy.context.evaluated_depsgraph_get()
    for o in objs:
        oe = o.evaluated_get(dg)
        for c in oe.bound_box:
            w = o.matrix_world @ Vector(c)
            mn = Vector((min(mn[i], w[i]) for i in range(3)))
            mx = Vector((max(mx[i], w[i]) for i in range(3)))
    return mn, mx


def _bone(arm, *names):
    for n in names:
        b = arm.data.bones.get(n)
        if b:
            return b
    return None


def _bone_len(arm, *names):
    b = _bone(arm, *names)
    if not b:
        return None
    return (arm.matrix_world @ b.tail_local - arm.matrix_world @ b.head_local).length


# ------------------------------------------------------------------ proportions
def check_proportions(report, rules, meshes, arm, group):
    rng = rules["proportions"].get(group)
    mn, mx = _world_bbox(meshes)
    height = mx.z - mn.z
    report["measured"]["height_m"] = round(height, 4)
    if not arm or not rng:
        _result(report, "proportions", "ASK",
                "no armature or no proportion group; check proportions by eye against Arthur")
        return
    head = _bone(arm, "head", "Head")
    if head:
        hz = (arm.matrix_world @ head.head_local).z
        hf = (mx.z - hz) / height
        report["measured"]["head_frac"] = round(hf, 3)
        lo, hi = rng["head_frac"]
        _result(report, "head size", "PASS" if lo <= hf <= hi else "ASK",
                f"head {hf:.3f} of height (allowed {lo}-{hi} for {group}; Arthur 0.151)", hf)
    for side in ("l", "r"):
        ua = _bone_len(arm, f"upperarm_{side}")
        la = _bone_len(arm, f"lowerarm_{side}")
        th = _bone_len(arm, f"thigh_{side}")
        ca = _bone_len(arm, f"calf_{side}")
        if ua and la:
            af = (ua + la) / height
            report["measured"][f"arm_frac_{side}"] = round(af, 3)
            lo, hi = rng["arm_frac"]
            _result(report, f"arm length {side}", "PASS" if lo <= af <= hi else "ASK",
                    f"arm {af:.3f} of height (allowed {lo}-{hi}; Arthur 0.245)", af)
        if th and ca:
            lf = (th + ca) / height
            report["measured"][f"leg_frac_{side}"] = round(lf, 3)
            lo, hi = rng["leg_frac"]
            _result(report, f"leg length {side}", "PASS" if lo <= lf <= hi else "ASK",
                    f"leg {lf:.3f} of height (allowed {lo}-{hi}; Arthur 0.436)", lf)


# ------------------------------------------------------------------ textures
def _image_array(img, max_side=512):
    w, h = img.size
    if w == 0 or h == 0:
        return None
    a = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    a = a.reshape(h, w, 4)
    step = max(1, max(w, h) // max_side)
    return a[::step, ::step]


def _hsv(rgb):
    mx = rgb.max(-1)
    mn = rgb.min(-1)
    s = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    return s, mx


def texture_stats(img):
    a = _image_array(img)
    if a is None:
        return None
    rgb = a[..., :3]
    mask = a[..., 3] > 0.5
    # ignore the flat fill outside UV islands (generators fill it black or near-black)
    corner = rgb[0, 0]
    if corner.max() < 0.03:
        mask &= np.abs(rgb - corner).sum(-1) > 1e-3
    if mask.sum() < 100:
        mask = a[..., 3] > 0.5
    s, v = _hsv(rgb)
    k = 3
    pad = np.pad(rgb, ((1, 1), (1, 1), (0, 0)), mode="edge")
    blur = sum(pad[i:i + rgb.shape[0], j:j + rgb.shape[1]] for i in range(k) for j in range(k)) / 9
    noise = np.abs(rgb - blur).mean(-1)
    m = mask
    return {
        "v": v[m], "s": s[m], "noise": float(noise[m].mean()),
        "size": list(img.size),
    }


def check_textures(report, rules, meshes):
    r = rules["base_colour_texture"]
    seen = set()
    for o in meshes:
        for slot in o.material_slots:
            mat = slot.material
            if not mat or not mat.use_nodes:
                continue
            bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if not bsdf or not bsdf.inputs["Base Color"].is_linked:
                continue
            node = bsdf.inputs["Base Color"].links[0].from_node
            while node and node.type != "TEX_IMAGE" and node.inputs and any(i.is_linked for i in node.inputs):
                node = next(i for i in node.inputs if i.is_linked).links[0].from_node
            if not node or node.type != "TEX_IMAGE" or not node.image or node.image.name in seen:
                continue
            img = node.image
            seen.add(img.name)
            st = texture_stats(img)
            if st is None:
                continue
            v, s = st["v"], st["s"]
            nb = float((v < r["near_black_value"]).mean())
            nw = float((v > r["near_white_value"]).mean())
            neon = float(((s > r["neon"]["saturation"]) & (v > r["neon"]["value"])).mean())
            smean = float(s.mean())
            is_eye = "eye" in mat.name.lower() or "eye" in img.name.lower()
            tag = f"{img.name} ({mat.name})"
            report["measured"].setdefault("textures", {})[img.name] = {
                "size": st["size"], "near_black": round(nb, 4), "near_white": round(nw, 4),
                "neon": round(neon, 4), "saturation_mean": round(smean, 3),
                "detail_noise": round(st["noise"], 4)}
            big = max(st["size"])
            _result(report, f"texture size {tag}", "PASS" if big <= r["max_size"] else "FIX",
                    f"{st['size'][0]}x{st['size'][1]} (max {r['max_size']}; cleanup downsizes)", big)
            _result(report, f"too dark {tag}", "PASS" if nb <= r["max_near_black_frac"] else "ASK",
                    f"{nb:.1%} near-black (max {r['max_near_black_frac']:.0%}); black reads as holes in game", nb)
            if not is_eye:  # eye whites are meant to be bright
                _result(report, f"too bright {tag}", "PASS" if nw <= r["max_near_white_frac"] else "ASK",
                        f"{nw:.1%} near-white (max {r['max_near_white_frac']:.0%}); blows out in sunlight", nw)
            lo, hi = r["saturation_mean"]
            if not is_eye:
                _result(report, f"colour strength {tag}", "PASS" if lo <= smean <= hi else "ASK",
                        f"mean saturation {smean:.2f} (allowed {lo}-{hi}; below = washed-out/grey, above = toy-like)", smean)
            _result(report, f"neon {tag}", "PASS" if neon <= r["max_neon_frac"] else "ASK",
                    f"{neon:.1%} neon pixels (max {r['max_neon_frac']:.0%})", neon)
            _result(report, f"painted look {tag}", "PASS" if st["noise"] <= r["max_detail_noise"] else "ASK",
                    f"detail noise {st['noise']:.3f} (max {r['max_detail_noise']}, provisional); high = photo-like or speckled", st["noise"])


# ------------------------------------------------------------------ materials
def _is_metal_part(name, rules):
    n = name.lower()
    return any(k in n for k in rules["material"]["metal_parts_allowed"])


def check_materials(report, rules, meshes, fix):
    r = rules["material"]
    done = set()
    for o in meshes:
        for slot in o.material_slots:
            mat = slot.material
            if not mat or mat.name in done or not mat.use_nodes:
                continue
            done.add(mat.name)
            bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if not bsdf:
                _result(report, f"material {mat.name}", "ASK", "no Principled BSDF; check by eye")
                continue
            metal_ok = _is_metal_part(mat.name, rules)
            spec_name = "Specular IOR Level" if "Specular IOR Level" in bsdf.inputs else "Specular"
            for inp, target, cond, why in (
                ("Roughness", r["roughness"],
                 lambda x: x >= (r["metal_roughness_min"] if metal_ok else r["roughness_min"]),
                 "matte look"),
                (spec_name, r["specular"], lambda x: x <= r["specular"] + 0.05, "no plastic shine"),
                ("Metallic", r["metallic"], lambda x: metal_ok or x <= 0.05, "metal only on metal parts"),
            ):
                sock = bsdf.inputs.get(inp)
                if sock is None:
                    continue
                if sock.is_linked:
                    _result(report, f"{inp} {mat.name}", "INFO",
                            f"driven by a texture; Unreal material sets the final value ({why})")
                    continue
                val = float(sock.default_value)
                if cond(val):
                    _result(report, f"{inp} {mat.name}", "PASS", f"{val:.2f} ({why})", val)
                elif fix:
                    sock.default_value = target
                    _result(report, f"{inp} {mat.name}", "FIXED", f"{val:.2f} -> {target} ({why})", val)
                else:
                    _result(report, f"{inp} {mat.name}", "FIX", f"{val:.2f}, should be {target} ({why})", val)


# ------------------------------------------------------------------ face
def check_face(report, rules, meshes, hero):
    f = rules["face"]
    eye_mats = {s.material for o in meshes for s in o.material_slots
                if s.material and "eye" in s.material.name.lower()}
    if hero and f["hero_needs_eye_material"]:
        _result(report, "eye material", "PASS" if eye_mats else "ASK",
                "own eye material found" if eye_mats else
                "hero has no separate eye material; rebuild eyes as on Arthur (M_Arthur_Eyes, 1024x512)")
    for m in eye_mats:
        for n in m.node_tree.nodes if m.use_nodes else []:
            if n.type == "TEX_IMAGE" and n.image:
                big = max(n.image.size)
                _result(report, f"eye texture {n.image.name}",
                        "PASS" if big >= f["eye_texture_min"] else "ASK",
                        f"{n.image.size[0]}x{n.image.size[1]} (min {f['eye_texture_min']})", big)
    for item in f["checklist"]:
        _result(report, "face (look at the face render)", "CHECK", item)


# ------------------------------------------------------------------ review renders
def render_turnaround(meshes, out_dir, name, rules, armature=None):
    """Standard review renders: same camera lens, lights, background and exposure every time."""
    rv = rules["review"]
    os.makedirs(out_dir, exist_ok=True)
    src = bpy.context.scene
    scn = bpy.data.scenes.new("StyleReview")
    for o in meshes + ([armature] if armature else []):
        scn.collection.objects.link(o)
    # Eevee on Henry (GPU). PIPELINE_RENDER_ENGINE=CYCLES for machines without a GPU.
    try:
        scn.render.engine = os.environ.get("PIPELINE_RENDER_ENGINE", "BLENDER_EEVEE")
    except TypeError:
        scn.render.engine = "CYCLES"
    if scn.render.engine == "CYCLES":
        scn.cycles.samples = 32
        scn.cycles.use_denoising = True
    scn.render.resolution_x, scn.render.resolution_y = rv["resolution"]
    scn.render.film_transparent = False
    scn.view_settings.view_transform = "AgX"
    w = bpy.data.worlds.new("StyleReviewWorld")
    scn.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (*rv["background"], 1)
    bg.inputs[1].default_value = 1.0

    mn, mx = _world_bbox(meshes)
    h = mx.z - mn.z
    centre = (mn + mx) / 2

    def light(nm, energy, rot):
        L = bpy.data.objects.new(nm, bpy.data.lights.new(nm, "SUN"))
        L.data.energy = energy
        L.data.angle = math.radians(8)
        L.rotation_euler = [math.radians(a) for a in rot]
        scn.collection.objects.link(L)
    light("Key", 3.0, (50, 0, -35))
    light("Fill", 1.0, (60, 0, 40))
    light("Rim", 1.5, (60, 0, 180))

    cam = bpy.data.objects.new("ReviewCam", bpy.data.cameras.new("ReviewCam"))
    scn.collection.objects.link(cam)
    scn.camera = cam
    cam.data.lens = 85
    cam.data.sensor_fit = "VERTICAL"  # so angle_y frames the height exactly
    cam.data.sensor_height = 24

    head_c = Vector((centre.x, centre.y, mx.z - 0.08 * h))
    if armature and armature.data.bones.get("head"):
        b = armature.data.bones["head"]
        head_c = (armature.matrix_world @ b.head_local + Vector((0, 0, 0.09 * h)))
    views = {
        "front": (0, centre, h * 1.15),
        "three_quarter": (35, centre, h * 1.15),
        "side": (90, centre, h * 1.15),
        "back": (180, centre, h * 1.15),
        "face": (15, head_c, h * 0.22),
    }
    paths = []
    for vname in rv["turnaround"]:
        ang, target, frame_h = views[vname]
        a = math.radians(ang)
        dist = frame_h / (2 * math.tan(cam.data.angle_y / 2))
        # 0 deg = in front of the character (it faces -Y), 90 = its left side, 180 = behind
        cam.location = target + Vector((math.sin(a), -math.cos(a), 0)) * dist
        cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
        scn.render.filepath = os.path.join(out_dir, f"{name}_{vname}.png")
        bpy.ops.render.render(write_still=True, scene=scn.name)
        paths.append(scn.render.filepath)
    if bpy.context.window:
        bpy.context.window.scene = src
    return paths


# ------------------------------------------------------------------ main
def run(meshes, armature=None, group="human_teen", hero=False, height_cm=None, fix=True,
        out_dir=None, name="character", rules_path=None, render=True):
    rules = load_rules(rules_path)
    objs = [bpy.data.objects[m] if isinstance(m, str) else m for m in meshes]
    arm = bpy.data.objects[armature] if isinstance(armature, str) else armature
    report = {"name": name, "hero": hero, "group": group, "checks": [], "measured": {}}
    check_proportions(report, rules, objs, arm, group)
    check_textures(report, rules, objs)
    check_materials(report, rules, objs, fix)
    check_face(report, rules, objs, hero)
    if render and out_dir:
        report["renders"] = render_turnaround(objs, out_dir, name, rules, arm)
    st = [c["status"] for c in report["checks"]]
    report["verdict"] = ("ASK" if "ASK" in st else "FIX" if "FIX" in st else "PASS")
    report["summary"] = {k: st.count(k) for k in ("PASS", "FIXED", "FIX", "ASK", "CHECK", "INFO")}
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, f"{name}_style_report.json"), "w") as f:
            json.dump(report, f, indent=2)
        with open(os.path.join(out_dir, f"{name}_style_report.md"), "w") as f:
            f.write(to_markdown(report))
    return report


def to_markdown(rep):
    lines = [f"# Style check: {rep['name']}", "",
             f"Verdict: **{rep['verdict']}**  ·  hero: {rep['hero']}  ·  group: {rep['group']}", "",
             "| Status | Check | Detail |", "|---|---|---|"]
    order = {"ASK": 0, "FIX": 1, "FIXED": 2, "CHECK": 3, "PASS": 4, "INFO": 5}
    for c in sorted(rep["checks"], key=lambda c: order.get(c["status"], 9)):
        lines.append(f"| {c['status']} | {c['check']} | {c['detail']} |")
    return "\n".join(lines) + "\n"
