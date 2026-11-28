"""Creates /Game/Creatures/Wolf/BP_Wolf: a stand-in wolf ready for Wolf_AI_Nodes.txt.

Run in the Unreal editor (Python). Safe to run again (rebuilds the stand-in parts only if
the Blueprint is new). It:
  1. creates BP_Wolf (parent Character) with grey block parts under a "Visual" scene
     component (Body, Head, Snout, Ears, Tail, 4 Legs), sized against Arthur (160 cm):
     shoulder ~75 cm, body ~1.4 m nose to tail
  2. sets movement (run 540 cm/s, turns to face where it runs), AI possession for
     placed and spawned wolves, tags Lockable + Enemy
  3. adds variables the AI uses (State, T, CircleSign, DamageTaken, HitPlayer, HoldingToken)
  4. adds AttackersNow (int) to BP_Arthur, the shared attack-token count
  5. places 3 wolves at the farm's wolf spawns in L_Farm_Blockout (and saves)
Then paste Wolf_AI_Nodes.txt into BP_Wolf's Event Graph, compile, save.
When the real wolf model exists, it replaces the Visual parts; the AI stays.
"""
import unreal

FOLDER = "/Game/Creatures/Wolf"
NAME = "BP_Wolf"
ARTHUR_BP = "/Game/Characters/ArthurPipeline/BP_Arthur"
LEVEL_PATH = "/Game/Levels/L_Farm_Blockout"
SPAWNS_M = [(48.75, 31.25), (59.38, 9.38), (31.25, 38.75)]  # farm_blockout.json wolf_area.spawns
RUN_SPEED = 540.0
CAPSULE_R, CAPSULE_HALF = 38.0, 42.0
GREY_MI = "/Game/Levels/FarmBlockout/Materials/MI_Grey_later"

EAL = unreal.EditorAssetLibrary
BEL = unreal.BlueprintEditorLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
SDL = unreal.SubobjectDataBlueprintFunctionLibrary
report = []

CUBE = EAL.load_asset("/Engine/BasicShapes/Cube")
CYL = EAL.load_asset("/Engine/BasicShapes/Cylinder")
grey = EAL.load_asset(GREY_MI)

# name: (mesh, location cm relative to the capsule centre, size cm (x,y,z), rotation (pitch, yaw, roll))
# The capsule centre is 42 cm above the ground. X = forward.
PARTS = {
    "Body":  (CUBE, (0, 0, 16), (95, 34, 34), (0, 0, 0)),
    "Chest": (CUBE, (34, 0, 20), (34, 38, 42), (0, 0, 0)),
    "Head":  (CUBE, (66, 0, 40), (30, 26, 26), (0, 0, 0)),
    "Snout": (CUBE, (88, 0, 34), (22, 13, 13), (0, 0, 0)),
    "EarL":  (CUBE, (62, 8, 58), (6, 7, 14), (0, 0, 10)),
    "EarR":  (CUBE, (62, -8, 58), (6, 7, 14), (0, 0, -10)),
    "Tail":  (CUBE, (-66, 0, 26), (44, 10, 10), (25, 0, 0)),
    "LegFL": (CYL, (34, 11, -18), (10, 10, 48), (0, 0, 0)),
    "LegFR": (CYL, (34, -11, -18), (10, 10, 48), (0, 0, 0)),
    "LegBL": (CYL, (-36, 11, -18), (10, 10, 48), (0, 0, 0)),
    "LegBR": (CYL, (-36, -11, -18), (10, 10, 48), (0, 0, 0)),
}


def handles_by_name(bp):
    out = {}
    for h in sds.k2_gather_subobject_data_for_blueprint(bp):
        d = SDL.get_data(h)
        obj = SDL.get_object(d)
        if obj:
            out[obj.get_name().replace("_GEN_VARIABLE", "")] = (h, obj)
    return out


def add_component(bp, parent_handle, cls, name):
    params = unreal.AddNewSubobjectParams(parent_handle=parent_handle, new_class=cls, blueprint_context=bp)
    h, fail = sds.add_new_subobject(params)
    if fail and str(fail):
        raise RuntimeError(f"add {name}: {fail}")
    sds.rename_subobject(h, unreal.Text(name))
    return h, SDL.get_object(SDL.get_data(h))


def add_var(bp, name, type_name):
    try:
        ok = BEL.add_member_variable(bp, name, BEL.get_basic_type_by_name(type_name))
        report.append(f"{bp.get_name()}.{name}: {'added' if ok else 'already there'}")
    except Exception as e:  # noqa: BLE001
        report.append(f"{bp.get_name()}.{name}: COULD NOT ADD ({e}) - add by hand ({type_name})")


path = f"{FOLDER}/{NAME}"
new = not EAL.does_asset_exist(path)
if new:
    fac = unreal.BlueprintFactory()
    fac.set_editor_property("parent_class", unreal.Character)
    bp = tools.create_asset(NAME, FOLDER, unreal.Blueprint, fac)
else:
    bp = EAL.load_asset(path)

if new:
    comps = handles_by_name(bp)
    cap_h, cap = next(v for k, v in comps.items() if isinstance(v[1], unreal.CapsuleComponent))
    vis_h, _ = add_component(bp, cap_h, unreal.SceneComponent, "Visual")
    for name, (mesh, loc, size, rot) in PARTS.items():
        _, c = add_component(bp, vis_h, unreal.StaticMeshComponent, name)
        c.set_editor_property("static_mesh", mesh)
        c.set_editor_property("relative_location", unreal.Vector(*loc))
        c.set_editor_property("relative_scale3d", unreal.Vector(size[0] / 100, size[1] / 100, size[2] / 100))
        c.set_editor_property("relative_rotation", unreal.Rotator(roll=rot[2], pitch=rot[0], yaw=rot[1]))
        c.set_editor_property("collision_profile_name", "NoCollision")
        if grey:
            c.set_editor_property("override_materials", [grey])
    report.append(f"created {path} with stand-in parts: {', '.join(PARTS)}")

for name, t in (("State", "name"), ("T", "real"), ("CircleSign", "real"), ("DamageTaken", "real"),
                ("HitPlayer", "bool"), ("HoldingToken", "bool")):
    add_var(bp, name, t)
BEL.compile_blueprint(bp)

cdo = unreal.get_default_object(bp.generated_class())
cdo.set_editor_property("tags", ["Lockable", "Enemy"])
cdo.set_editor_property("auto_possess_ai", unreal.AutoPossessAI.PLACED_IN_WORLD_OR_SPAWNED)
cdo.set_editor_property("use_controller_rotation_yaw", False)
cap = cdo.get_editor_property("capsule_component")
cap.set_editor_property("capsule_radius", CAPSULE_R)
cap.set_editor_property("capsule_half_height", CAPSULE_HALF)
mv = cdo.get_editor_property("character_movement")
mv.set_editor_property("max_walk_speed", RUN_SPEED)
mv.set_editor_property("orient_rotation_to_movement", True)
mv.set_editor_property("rotation_rate", unreal.Rotator(0, 720, 0))
mv.set_editor_property("braking_deceleration_walking", 1400.0)
BEL.compile_blueprint(bp)
EAL.save_loaded_asset(bp)
report.append("BP_Wolf: tags Lockable+Enemy, run 540, AI possess placed+spawned")

arthur = EAL.load_asset(ARTHUR_BP)
add_var(arthur, "AttackersNow", "int")
BEL.compile_blueprint(arthur)
EAL.save_loaded_asset(arthur)

# place wolves at the farm's wolf spawns
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
les.load_level(LEVEL_PATH)
for a in eas.get_all_level_actors():
    if "WolfSpawnTest" in [str(t) for t in a.tags]:
        eas.destroy_actor(a)
cls = bp.generated_class()
for i, (x, y) in enumerate(SPAWNS_M):
    w = eas.spawn_actor_from_class(cls, unreal.Vector(x * 100, y * 100, CAPSULE_HALF + 5), unreal.Rotator(0, 180, 0))
    w.set_actor_label(f"Wolf_{i + 1}")
    w.set_folder_path("Gameplay/Wolves")
    w.tags = ["Lockable", "Enemy", "WolfSpawnTest"]
les.save_current_level()
report.append(f"placed {len(SPAWNS_M)} wolves at the farm wolf spawns")
print("\n".join(report))
