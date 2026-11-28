"""Prepares BP_Arthur and the farm level for the lock-on nodes (Arthur_LockOn_Nodes.txt).

Run in the Unreal editor (Python). It:
  1. adds two variables to BP_Arthur: LockTarget (Actor) and IsLockedOn (bool)
  2. checks the Event Graph for an existing Event Tick or Tab key event (the paste adds both)
  3. places two practice posts tagged "Lockable" near the player start in L_Farm_Blockout
Paste the nodes after this, then compile. Safe to run twice.
"""
import os
import tempfile
import unreal

BP_PATH = "/Game/Characters/ArthurPipeline/BP_Arthur"
LEVEL_PATH = "/Game/Levels/L_Farm_Blockout"
POSTS = [(-16.0, 2.0), (-13.0, -7.0)]  # metres, farm layout coords (X east, Y south); player start is (-23.75, -2.5)
TAG_TEST = "LockOnTest"

BEL = unreal.BlueprintEditorLibrary
EAL = unreal.EditorAssetLibrary
report = []


def pin_type(kind):
    if kind == "bool":
        return BEL.get_basic_type_by_name("bool")
    if hasattr(BEL, "get_object_reference_type"):
        return BEL.get_object_reference_type(unreal.Actor)
    t = unreal.EdGraphPinType()
    t.set_editor_property("pin_category", "object")
    t.set_editor_property("pin_sub_category_object", unreal.Actor.static_class())
    return t


def graph_text(bp):
    """Export the Blueprint to T3D text so we can look for existing events."""
    path = os.path.join(tempfile.gettempdir(), "bp_arthur_lockon_check.t3d")
    task = unreal.AssetExportTask()
    task.object = bp
    task.filename = path
    task.automated = True
    task.prompt = False
    task.replace_identical = True
    try:
        unreal.Exporter.run_asset_export_task(task)
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:  # noqa: BLE001
        report.append(f"graph check skipped ({e})")
        return ""


bp = EAL.load_asset(BP_PATH)
for name, kind in (("LockTarget", "actor"), ("IsLockedOn", "bool")):
    try:
        ok = BEL.add_member_variable(bp, name, pin_type(kind))
        report.append(f"variable {name}: {'added' if ok else 'already there'}")
    except Exception as e:  # noqa: BLE001
        report.append(f"variable {name}: COULD NOT ADD ({e}) - add it by hand in My Blueprint > Variables")
BEL.compile_blueprint(bp)
EAL.save_loaded_asset(bp)

txt = graph_text(bp)
if txt:
    if "ReceiveTick" in txt:
        report.append("WARNING: BP_Arthur already has an Event Tick - after pasting, delete the pasted Event Tick "
                      "and connect the existing one to the lock-on Branch")
    if "InputKey=Tab" in txt:
        report.append("WARNING: a Tab key event already exists - lock-on paste would add a second one")
    if "InputKey=Tab" not in txt and "ReceiveTick" not in txt:
        report.append("graph check: no Event Tick or Tab event yet - paste is clear to go")

# practice posts
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
les.load_level(LEVEL_PATH)
for a in eas.get_all_level_actors():
    if TAG_TEST in [str(t) for t in a.tags]:
        eas.destroy_actor(a)
cyl = EAL.load_asset("/Engine/BasicShapes/Cylinder")
sph = EAL.load_asset("/Engine/BasicShapes/Sphere")
mat = EAL.load_asset("/Game/Levels/FarmBlockout/Materials/MI_Grey_wolf_spawn")
for i, (x, y) in enumerate(POSTS):
    loc = unreal.Vector(x * 100, y * 100, 90)
    post = eas.spawn_actor_from_object(cyl, loc, unreal.Rotator(0, 0, 0))
    post.set_actor_scale3d(unreal.Vector(0.45, 0.45, 1.8))
    post.set_actor_label(f"LockOn_TestPost_{i + 1}")
    post.set_folder_path("Gameplay/LockOnTest")
    post.tags = ["Lockable", TAG_TEST]
    head = eas.spawn_actor_from_object(sph, unreal.Vector(loc.x, loc.y, 200), unreal.Rotator(0, 0, 0))
    head.set_actor_scale3d(unreal.Vector(0.5, 0.5, 0.5))
    head.set_actor_label(f"LockOn_TestPost_{i + 1}_Head")
    head.set_folder_path("Gameplay/LockOnTest")
    head.tags = [TAG_TEST]
    if mat:
        for a in (post, head):
            a.static_mesh_component.set_material(0, mat)
les.save_current_level()
report.append(f"placed {len(POSTS)} practice posts tagged Lockable in {LEVEL_PATH}")
print("\n".join(report))
