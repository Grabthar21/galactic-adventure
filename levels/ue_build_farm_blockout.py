"""Build the greybox level L_Farm_Blockout in Unreal (UE 5.4) from farm_blockout.json.

Run inside the editor (Python). Safe to re-run: it reloads the level, deletes every
actor tagged FarmBlockout and builds again.

Layout units are meters, X = east, Y = south (Unreal +Y), Z up. Unreal works in cm.
Engine basic shapes are 100 cm and pivot-centred.
"""
import json
import math
import os
import random

import unreal

LEVEL_PATH = "/Game/Levels/L_Farm_Blockout"
MAT_DIR = "/Game/Levels/FarmBlockout/Materials"
TAG = "FarmBlockout"
M = 100.0  # cm per meter

if "LAYOUT" not in globals():
    _here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "."
    with open(os.path.join(_here, "farm_blockout.json")) as f:
        LAYOUT = json.load(f)

eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
EAL = unreal.EditorAssetLibrary
MEL = unreal.MaterialEditingLibrary
ML = unreal.MathLibrary

CUBE = EAL.load_asset("/Engine/BasicShapes/Cube")
CYL = EAL.load_asset("/Engine/BasicShapes/Cylinder")
SPHERE = EAL.load_asset("/Engine/BasicShapes/Sphere")
BASE_MAT = EAL.load_asset("/Engine/BasicShapes/BasicShapeMaterial")

# Stylised, Zelda-leaning greybox palette
COLORS = {
    "grass": (0.30, 0.52, 0.22),
    "grass_far": (0.26, 0.45, 0.20),
    "path": (0.72, 0.58, 0.38),
    "wall_house": (0.90, 0.84, 0.70),
    "wall_barn": (0.62, 0.20, 0.15),
    "wall_cottage": (0.80, 0.74, 0.60),
    "roof": (0.35, 0.22, 0.16),
    "door": (0.22, 0.14, 0.09),
    "soil": (0.40, 0.27, 0.16),
    "crop": (0.42, 0.62, 0.25),
    "fence": (0.48, 0.34, 0.20),
    "pen_floor": (0.62, 0.55, 0.38),
    "hay": (0.90, 0.78, 0.38),
    "trunk": (0.36, 0.24, 0.15),
    "leaf": (0.16, 0.36, 0.17),
    "leaf_dark": (0.11, 0.27, 0.13),
    "hill": (0.42, 0.58, 0.30),
    "hill_top": (0.55, 0.66, 0.38),
    "prop": (0.85, 0.85, 0.85),
    "key_prop": (0.95, 0.75, 0.20),
    "wolf_spawn": (0.80, 0.15, 0.15),
    "pup": (0.95, 0.55, 0.20),
    "later": (0.55, 0.55, 0.60),
}
_mats = {}


def mat(name):
    if name in _mats:
        return _mats[name]
    path = f"{MAT_DIR}/MI_Grey_{name}"
    if EAL.does_asset_exist(path):
        mi = EAL.load_asset(path)
    else:
        mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            f"MI_Grey_{name}", MAT_DIR, unreal.MaterialInstanceConstant,
            unreal.MaterialInstanceConstantFactoryNew())
        MEL.set_material_instance_parent(mi, BASE_MAT)
    params = MEL.get_vector_parameter_names(BASE_MAT)
    pname = "Color" if "Color" in [str(p) for p in params] else str(params[0])
    r, g, b = COLORS[name]
    MEL.set_material_instance_vector_parameter_value(mi, pname, unreal.LinearColor(r, g, b, 1))
    EAL.save_loaded_asset(mi)
    _mats[name] = mi
    return mi


def v(x, y, z=0.0):
    """meters -> Unreal vector in cm"""
    return unreal.Vector(x * M, y * M, z * M)


def spawn(mesh, label, folder, loc, scale, color, rot=None, collide=True, hidden=False):
    rot = rot or unreal.Rotator(0, 0, 0)
    a = eas.spawn_actor_from_object(mesh, loc, rot)
    a.set_actor_scale3d(scale)
    a.set_actor_label(label)
    a.set_folder_path(folder)
    a.tags = [TAG]
    smc = a.static_mesh_component
    if color:
        smc.set_material(0, mat(color))
    if not collide:
        smc.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    if hidden:
        a.set_actor_hidden_in_game(True)
    return a


def box(label, folder, cx, cy, cz, sx, sy, sz, color, yaw=0.0, **kw):
    """Axis box: centre and size in meters."""
    return spawn(CUBE, label, folder, v(cx, cy, cz), unreal.Vector(sx, sy, sz), color,
                 unreal.Rotator(roll=0, pitch=0, yaw=yaw), **kw)


def slab(label, folder, a, b, width, thick, color, **kw):
    """A box whose TOP face runs from point a to point b (meters, 3D), `width` across.
    Used for paths, fences, roofs, ramps and hill sides."""
    A = v(*a)
    B = v(*b)
    d = B - A
    length = d.length()
    rot = ML.make_rot_from_x(d)          # local X along a->b, roll 0 so local Y stays level
    up = ML.get_up_vector(rot)
    if up.z < 0:
        up = up * -1.0
    centre = (A + B) * 0.5 - up * (thick * M * 0.5)
    return spawn(CUBE, label, folder, centre,
                 unreal.Vector(length / 100.0, width, thick), color, rot, **kw)


# ----------------------------------------------------------------- level
def open_or_create_level():
    if EAL.does_asset_exist(LEVEL_PATH):
        les.load_level(LEVEL_PATH)
        for a in eas.get_all_level_actors():
            if TAG in [str(t) for t in a.tags]:
                eas.destroy_actor(a)
    else:
        les.new_level(LEVEL_PATH)


def find_class(asset_name):
    reg = unreal.AssetRegistryHelpers.get_asset_registry()
    for ad in reg.get_assets_by_class(unreal.TopLevelAssetPath("/Script/Engine", "Blueprint"), True):
        if str(ad.asset_name) == asset_name:
            return EAL.load_blueprint_class(str(ad.package_name))
    return None


def lighting():
    f = "Lighting"
    sun = eas.spawn_actor_from_class(unreal.DirectionalLight, v(0, 0, 30),
                                     unreal.Rotator(roll=0, pitch=-42, yaw=-35))
    sun.set_actor_label("Sun"); sun.set_folder_path(f); sun.tags = [TAG]
    lc = sun.light_component
    lc.set_editor_property("intensity", 8.0)
    lc.set_editor_property("atmosphere_sun_light", True)
    sky = eas.spawn_actor_from_class(unreal.SkyLight, v(0, 0, 30))
    sky.set_actor_label("SkyLight"); sky.set_folder_path(f); sky.tags = [TAG]
    sky.light_component.set_editor_property("real_time_capture", True)
    sky.light_component.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    for cls, name in ((unreal.SkyAtmosphere, "SkyAtmosphere"),
                      (unreal.ExponentialHeightFog, "HeightFog")):
        a = eas.spawn_actor_from_class(cls, v(0, 0, 0))
        a.set_actor_label(name); a.set_folder_path(f); a.tags = [TAG]


# ----------------------------------------------------------------- pieces
def ground(L):
    g = L["ground"]
    box("Ground", "Ground", g["center"][0], g["center"][1], -0.5,
        g["size"][0], g["size"][1], 1.0, "grass_far")
    (x0, y0), (x1, y1) = L["bounds"]["min"], L["bounds"]["max"]
    # slightly brighter farm lawn, 1 cm proud so it reads as the play space
    box("FarmLawn", "Ground", (x0 + x1) / 2, (y0 + y1) / 2, 0.005, x1 - x0, y1 - y0, 0.01,
        "grass", collide=False)


def buildings(L):
    oh = 0.6  # roof overhang
    wall_col = {"farmhouse": "wall_house", "barn": "wall_barn", "cottage": "wall_cottage"}
    for b in L["buildings"]:
        f = f"Buildings/{b['id']}"
        cx, cy = b["center"]
        w, d = b["size"]
        wh, rh = b["wall_h"], b["ridge_h"]
        box(f"{b['id']}_walls", f, cx, cy, wh / 2, w, d, wh, wall_col.get(b["id"], "wall_house"))
        # gable roof, ridge along X; slabs from each eave up to the ridge
        for side, s in (("S", 1), ("N", -1)):
            run = d / 2 + oh
            drop = (rh - wh) * oh / (d / 2)
            slab(f"{b['id']}_roof_{side}", f,
                 (cx, cy + s * run, wh - drop), (cx, cy, rh), w + 2 * oh, 0.3, "roof")
        # gable end fill (stack of boxes, stepped) so the roof is not see-through
        steps = 6
        for i in range(steps):
            hgt = (rh - wh) / steps
            depth = d * (1 - (i + 1) / steps) - 0.1
            box(f"{b['id']}_gable_{i}", f, cx, cy, wh + hgt * (i + 0.5), w - 0.1, depth, hgt,
                wall_col.get(b["id"], "wall_house"))
        # door on the south face (+Y)
        dw, dh = (2.4, 3.2) if b["id"] == "barn" else (1.2, 2.2)
        box(f"{b['id']}_door", f, cx, cy + d / 2 + 0.05, dh / 2, dw, 0.12, dh, "door")


def paths(L):
    for i, p in enumerate(L["paths"]):
        (x0, y0), (x1, y1) = p["from"], p["to"]
        z = 0.03 + 0.01 * i
        slab(p["id"], "Paths", (x0, y0, z), (x1, y1, z), p["width"], 0.06, "path",
             collide=False)


def field(L):
    fd = L["field"]
    cx, cy = fd["center"]
    w, d = fd["size"]
    box("field_soil", "Field", cx, cy, 0.04, w, d, 0.08, "soil", collide=False)
    n = int(d // fd["row_spacing"])
    y = cy - d / 2 + fd["row_spacing"] / 2
    for i in range(n):
        box(f"field_row_{i:02d}", "Field", cx, y, 0.2, w - 1.0, 0.7, 0.35, "crop", collide=False)
        y += fd["row_spacing"]


def fence_line(label, folder, a, b, h=1.1):
    """Rails as one slab + posts every ~3 m."""
    ax, ay = a
    bx, by = b
    slab(f"{label}_rail", folder, (ax, ay, h), (bx, by, h), 0.15, 0.25, "fence")
    slab(f"{label}_rail_lo", folder, (ax, ay, h * 0.5), (bx, by, h * 0.5), 0.15, 0.2, "fence",
         collide=False)
    length = math.hypot(bx - ax, by - ay)
    n = max(1, int(round(length / 3.0)))
    for i in range(n + 1):
        t = i / n
        box(f"{label}_post_{i:02d}", folder, ax + (bx - ax) * t, ay + (by - ay) * t, h / 2,
            0.2, 0.2, h, "fence", collide=False)


def pen(L):
    p = L["pen"]
    cx, cy = p["center"]
    w, d = p["size"]
    f = "Pen"
    box("pen_floor", f, cx, cy, 0.02, w, d, 0.04, "pen_floor", collide=False)
    x0, x1, y0, y1 = cx - w / 2, cx + w / 2, cy - d / 2, cy + d / 2
    gate = 3.0
    fence_line("pen_N", f, (x0, y0), (x1, y0))
    fence_line("pen_S", f, (x0, y1), (x1, y1))
    fence_line("pen_E", f, (x1, y0), (x1, y1))
    # west side has the gate gap in the middle
    fence_line("pen_W1", f, (x0, y0), (x0, cy - gate / 2))
    fence_line("pen_W2", f, (x0, cy + gate / 2), (x0, y1))
    for i, (hx, hy) in enumerate(p["hay_bales"]):
        spawn(CYL, f"hay_bale_{i}", f, v(hx, hy, 0.6), unreal.Vector(1.2, 1.2, 1.4), "hay",
              unreal.Rotator(roll=90, pitch=0, yaw=20 * i))


def props(L):
    f = "Props"
    for p in L["props"]:
        x, y = p["pos"]
        if p["id"] == "player_start":
            ps = eas.spawn_actor_from_class(unreal.PlayerStart, v(x, y, 1.0),
                                            unreal.Rotator(roll=0, pitch=0, yaw=-90))
            ps.set_actor_label("PlayerStart"); ps.set_folder_path(f); ps.tags = [TAG]
        elif p["id"] == "hen_a_wen":
            box("hen_a_wen", f, x, y, 0.25, 0.5, 0.35, 0.5, "key_prop")
        elif p["id"] == "oil_tub":
            spawn(CYL, "oil_tub", f, v(x, y, 0.45), unreal.Vector(1.0, 1.0, 0.9), "key_prop")
        elif p["id"] == "metal_rod":
            spawn(CYL, "metal_rod", f, v(x, y, 0.06), unreal.Vector(0.06, 0.06, 1.2), "key_prop",
                  unreal.Rotator(roll=90, pitch=0, yaw=30), collide=False)
        else:
            box(p["id"], f, x, y, 0.4, 0.8, 0.8, 0.8, "prop")


def tree(label, folder, x, y, scale=1.0, dark=False):
    h = 3.0 * scale
    spawn(CYL, f"{label}_trunk", folder, v(x, y, h / 2), unreal.Vector(0.6 * scale, 0.6 * scale, h),
          "trunk")
    c = 4.2 * scale
    spawn(SPHERE, f"{label}_canopy", folder, v(x, y, h + c * 0.35),
          unreal.Vector(c / 1.0, c / 1.0, c * 0.85), "leaf_dark" if dark else "leaf",
          collide=False)


def treeline(L, rng):
    t = L["treeline"]
    (x0, y0), (x1, y1) = L["bounds"]["min"], L["bounds"]["max"]
    inset = t["band"] / 2
    sp = t["spacing"]
    gaps = t["gaps"]
    f = "Trees/Treeline"

    def in_gap(side, x):
        return any(g["side"] == side and abs(x - g["x"]) < g["width"] / 2 + 2.0 for g in gaps)

    pts = []
    x = x0 + inset
    while x <= x1 - inset + 0.01:
        if not in_gap("north", x):
            pts.append((x, y0 + inset))
        pts.append((x, y1 - inset))
        x += sp
    y = y0 + inset + sp
    while y < y1 - inset - sp / 2:
        pts.append((x0 + inset, y))
        pts.append((x1 - inset, y))
        y += sp
    for i, (px, py) in enumerate(pts):
        tree(f"tl_{i:03d}", f, px + rng.uniform(-1.2, 1.2), py + rng.uniform(-1.2, 1.2),
             rng.uniform(0.85, 1.25), dark=rng.random() < 0.35)


def wolf_area(L, rng):
    w = L["wolf_area"]
    f = "WolfArea"
    for i, (sx, sy) in enumerate(w["spawns"]):
        box(f"wolf_spawn_{i}", f, sx, sy, 0.05, 1.5, 1.5, 0.1, "wolf_spawn", collide=False,
            hidden=True)
    pf = w["pup_fence"]
    fence_line("pup_fence", f, pf["from"], pf["to"], h=1.0)
    px, py = pf["pup"]
    box("pup_marker", f, px, py, 0.3, 0.7, 0.4, 0.6, "pup")
    fc = w["forest_corner"]
    (fx0, fy0), (fx1, fy1) = fc["min"], fc["max"]
    keep_clear = [tuple(s) for s in w["spawns"]] + [tuple(pf["from"]), tuple(pf["to"]),
                                                    tuple(pf["pup"])]
    placed = []
    tries = 0
    while len(placed) < 34 and tries < 2000:
        tries += 1
        x = rng.uniform(fx0 + 2, fx1 - 4)
        y = rng.uniform(fy0 + 2, fy1 - 4)
        # thicker towards the far corner, never on spawns / fence
        if rng.random() > (x - fx0) / (fx1 - fx0) * 0.6 + (y - fy0) / (fy1 - fy0) * 0.6:
            continue
        if any(math.hypot(x - cx, y - cy) < 6.0 for cx, cy in keep_clear):
            continue
        if any(math.hypot(x - ox, y - oy) < 4.0 for ox, oy in placed):
            continue
        placed.append((x, y))
    for i, (x, y) in enumerate(placed):
        tree(f"forest_{i:02d}", "Trees/WolfForest", x, y, rng.uniform(1.0, 1.4),
             dark=rng.random() < 0.6)


def escape_hill(L):
    """Terraced hill: stacked oval layers (1 m each). Every layer's south edge sits exactly
    on the ramp line, so the ramp is never buried; the other sides step back at ~38 deg."""
    h = L["escape_hill"]
    f = "EscapeHill"
    cx, cy = h["crest"]
    top = h["crest_h"]
    pw, pd = h["plateau"]
    gx, gy = h["path_from"]
    north = cy - pd / 2
    south = cy + pd / 2                       # plateau south edge, where the ramp arrives
    ramp_start = gy - 0.5
    layers = int(round(top))
    for i in range(1, layers + 1):
        z = top * i / layers
        back = (top - z) / math.tan(math.radians(38))
        s_edge = ramp_start + (south - ramp_start) * (z / top)   # where the ramp is at height z
        n_edge = north - back
        hx = pw / 2 + back
        hy = (s_edge - n_edge) / 2
        col = "hill_top" if i == layers else "hill"
        spawn(CYL, f"hill_layer_{i:02d}", f, v(cx, (s_edge + n_edge) / 2, z / 2),
              unreal.Vector(hx * 2, hy * 2, z), col)
    # walkable ramp, 5 m wide, lying on the terrace edges
    slab("hill_ramp", f, (cx, ramp_start, 0.0), (cx, south, top + 0.02), 5.0, 1.0, "hill")
    slab("hill_path", f, (gx, gy, 0.04), (cx, south, top + 0.06), 2.5, 0.06, "path",
         collide=False)
    ramp_deg = math.degrees(math.atan2(top, abs(south - ramp_start)))
    unreal.log(f"[FarmBlockout] escape hill ramp slope = {ramp_deg:.1f} deg")
    return ramp_deg


def invisible_walls(L):
    """Keep the player in the play space; gap at the back gate into the hill corridor."""
    f = "Blocking"
    (x0, y0), (x1, y1) = L["bounds"]["min"], L["bounds"]["max"]
    H, T = 8.0, 1.0
    gate_x = L["escape_hill"]["path_from"][0]
    gw = 6.0
    box("wall_S", f, (x0 + x1) / 2, y1 + T / 2, H / 2, x1 - x0 + 2 * T, T, H, "later", hidden=True)
    box("wall_E", f, x1 + T / 2, (y0 + y1) / 2, H / 2, T, y1 - y0, H, "later", hidden=True)
    box("wall_W", f, x0 - T / 2, (y0 + y1) / 2, H / 2, T, y1 - y0, H, "later", hidden=True)
    lw = (gate_x - gw / 2) - x0
    rw = x1 - (gate_x + gw / 2)
    box("wall_N_left", f, x0 + lw / 2, y0 - T / 2, H / 2, lw, T, H, "later", hidden=True)
    box("wall_N_right", f, x1 - rw / 2, y0 - T / 2, H / 2, rw, T, H, "later", hidden=True)
    # corridor around the hill
    h = L["escape_hill"]
    cx, cy = h["crest"]
    hw = h["plateau"][0] / 2 + 14
    ny = cy - h["plateau"][1] / 2 - 12
    box("hill_wall_W", f, cx - hw, (y0 + ny) / 2, 20, T, y0 - ny, 40, "later", hidden=True)
    box("hill_wall_E", f, cx + hw, (y0 + ny) / 2, 20, T, y0 - ny, 40, "later", hidden=True)
    box("hill_wall_N", f, cx, ny, 20, 2 * hw, T, 40, "later", hidden=True)


def later_markers(L):
    for m in L["out_of_scope_markers"]:
        x, y = m["pos"]
        box(f"LATER_{m['id']}", "Later", x, y, 0.05, 3, 3, 0.1, "later", collide=False,
            hidden=True)


def build():
    rng = random.Random(7)
    open_or_create_level()
    lighting()
    ground(LAYOUT)
    buildings(LAYOUT)
    paths(LAYOUT)
    field(LAYOUT)
    pen(LAYOUT)
    props(LAYOUT)
    treeline(LAYOUT, rng)
    wolf_area(LAYOUT, rng)
    ramp = escape_hill(LAYOUT)
    invisible_walls(LAYOUT)
    later_markers(LAYOUT)

    gm = find_class("BP_ThirdPersonGameMode")
    world = unreal.EditorLevelLibrary.get_editor_world()
    if gm:
        world.get_world_settings().set_editor_property("default_game_mode", gm)
    les.save_current_level()
    n = len([a for a in eas.get_all_level_actors() if TAG in [str(t) for t in a.tags]])
    msg = f"[FarmBlockout] built {n} actors, ramp {ramp:.1f} deg, game mode {'set' if gm else 'NOT FOUND'}"
    unreal.log(msg)
    print(msg)
    return msg


build()
