"""Imports Arthur's lock-on clips and builds the blend space BS_Arthur_LockOn.

Run in the Unreal editor after blender_lockon_set.build(...) wrote the FBX files and
lockon_set.json. Blend space axes: Direction (-180..180, 0 = forward, 90 = right,
-90 = left, +-180 = back) and Speed (0..500 cm/s). Idle sits on the Speed 0 row, each
clip at the speed it was made for, and again at full speed played faster.
"""
import json
import os
import unreal

ANIM_DIR = r"C:\Users\johnn\Documents\SpacePiece_Blender\ArthurAdv\pipeline\anims"
DEST = "/Game/Characters/ArthurPipeline/LockOn"
SKELETON = "/Game/Characters/Mannequins/Meshes/SK_Mannequin"
MANNY = "/Game/Characters/Mannequins/Animations/Manny"
BS_NAME = "BS_Arthur_LockOn"
MAX_SPEED = 500.0
DIRS = {"Fwd": 0.0, "Right": 90.0, "Left": -90.0, "Back": 180.0}

EAL = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
skel = EAL.load_asset(SKELETON)
report = []


def import_clip(path, name):
    ui = unreal.FbxImportUI()
    ui.import_mesh = False
    ui.import_animations = True
    ui.import_materials = False
    ui.import_textures = False
    ui.skeleton = skel
    ui.mesh_type_to_import = unreal.FBXImportType.FBXIT_ANIMATION
    ui.anim_sequence_import_data.animation_length = unreal.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME
    ui.anim_sequence_import_data.import_bone_tracks = True
    t = unreal.AssetImportTask()
    t.filename = path
    t.destination_path = DEST
    t.destination_name = name
    t.replace_existing = True
    t.automated = True
    t.save = True
    t.options = ui
    tools.import_asset_tasks([t])
    seq = EAL.load_asset(f"{DEST}/{name}")
    if seq:
        seq.set_editor_property("enable_root_motion", False)
        seq.set_editor_property("force_root_lock", True)  # in-place clips: keep the root still
        EAL.save_loaded_asset(seq)
    return seq


manifest_path = os.path.join(ANIM_DIR, "lockon_set.json")
with open(manifest_path) as f:
    manifest = json.load(f)

clips = {}  # dir -> (sequence, speed)
for d, info in manifest.items():
    name = os.path.splitext(os.path.basename(info["file"]))[0]
    seq = import_clip(info["file"], name)
    if seq:
        clips[d] = (seq, float(info["speed"]))
        report.append(f"imported {name} ({info['speed']} cm/s{', mirrored' if info['mirrored'] else ''})")
    else:
        report.append(f"FAILED to import {name}")

idle = EAL.load_asset(f"{MANNY}/MM_Idle")
walk = EAL.load_asset(f"{MANNY}/MM_Walk_Fwd")
run = EAL.load_asset(f"{MANNY}/MM_Run_Fwd")

# blend space asset
bs_path = f"{DEST}/{BS_NAME}"
bs = EAL.load_asset(bs_path) if EAL.does_asset_exist(bs_path) else None
if bs is None:
    fac = unreal.BlendSpaceFactoryNew()
    fac.set_editor_property("target_skeleton", skel)
    bs = tools.create_asset(BS_NAME, DEST, unreal.BlendSpace, fac)


def param(name, lo, hi, grid, wrap=False):
    p = unreal.BlendParameter()
    p.set_editor_property("display_name", name)
    p.set_editor_property("min", lo)
    p.set_editor_property("max", hi)
    p.set_editor_property("grid_num", grid)
    p.set_editor_property("wrap_input", wrap)
    return p


def sample(anim, direction, speed, rate=1.0):
    s = unreal.BlendSample()
    s.set_editor_property("animation", anim)
    s.set_editor_property("sample_value", unreal.Vector(direction, speed, 0))
    s.set_editor_property("rate_scale", rate)
    return s


samples = []
for d in (-180.0, -90.0, 0.0, 90.0, 180.0):
    samples.append(sample(idle, d, 0.0))
walk_speed = 150.0  # Manny MM_Walk_Fwd
samples.append(sample(walk, 0.0, walk_speed))
samples.append(sample(run, 0.0, MAX_SPEED))
for d, (seq, speed) in clips.items():
    angles = [DIRS[d]] + ([-180.0] if d == "Back" else [])
    for a in angles:
        samples.append(sample(seq, a, min(speed, MAX_SPEED - 1)))
        samples.append(sample(seq, a, MAX_SPEED, rate=min(2.0, MAX_SPEED / max(speed, 1.0))))

try:
    bs.set_editor_property("blend_parameters", [param("Direction", -180, 180, 4, wrap=True),
                                                param("Speed", 0, MAX_SPEED, 4), param("None", 0, 100, 4)])
    bs.set_editor_property("sample_data", samples)
    EAL.save_loaded_asset(bs)
    report.append(f"{BS_NAME}: {len(samples)} samples set")
except Exception as e:  # noqa: BLE001
    report.append(f"{BS_NAME} created but samples could not be set from Python ({e}); "
                  f"place them in the blend space editor: idle row at Speed 0, clips at their speed")
missing = [d for d in ("Left", "Right", "Back") if d not in clips]
if missing:
    report.append("missing directions: " + ", ".join(missing))
print("\n".join(report))
