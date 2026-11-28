# Arthur — Lock-on and strafe (v1, 28 Nov 2026)

Zelda-style targeting. Press **Tab** (keyboard) or **Left Trigger** (gamepad) to lock onto the
nearest target within 15 m. The camera swings onto it and Arthur keeps facing it: W/S move toward
and away, A/D circle it, and sword swings aim at it. Press again to let go. The lock also drops by
itself past 22 m or when the target is gone (killed, despawned).

Anything can be a target by giving the actor the tag **`Lockable`**. The wolf will get it.

## Status
| Part | State |
|---|---|
| Lock-on Blueprint nodes (`pipeline/scripts/ue_paste/Arthur_LockOn_Nodes.txt`, 40 nodes) | ready; made by `gen_lockon_nodes.py` |
| BP_Arthur variables + practice posts (`pipeline/scripts/ue_lockon_setup.py`) | ready |
| Retarget: `in_place` and `mirror` options (`blender_mixamo_retarget.py`) | done, tested in Blender 5.3 (`test_retarget_options.py`) |
| Strafe set builder (`pipeline/scripts/blender_lockon_set.py`) | ready, tested on a stand-in rig |
| Clip import + blend space `BS_Arthur_LockOn` (`pipeline/scripts/ue_lockon_strafe_import.py`) | ready; setting blend-space samples from Python is untested in UE 5.4 |
| ABP_Arthur: play `BS_Arthur_LockOn` while `IsLockedOn` | to do on Henry (needs seeing the anim graph) |

## Tuning numbers (top of `gen_lockon_nodes.py`; re-run it to rebuild the paste file)
- `LOCK_RANGE` 1500: how far away a target can be picked (cm).
- `BREAK_RANGE` 2200: when the lock lets go (cm).
- `CAM_PITCH` -12: how much the camera looks down while locked (degrees).
- `TURN_SPEED` 8: how quickly the camera swings onto the target.

## How it works
- **Lock:** all actors tagged `Lockable` are checked → nearest one → if within range: store it
  in `LockTarget`, set `IsLockedOn`, and switch Character Movement from "turn toward movement"
  to "turn toward the camera" (Orient Rotation to Movement off, Use Controller Desired Rotation on).
- **Every frame while locked:** the camera's yaw eases toward the target (RInterpTo), and its
  pitch is fixed at -12°. Arthur turns with the camera at his normal turn rate.
- **Release:** clears both variables and puts the two movement settings back.
- No Disable Movement anywhere, so the root-motion dodge and combo still work while locked.

## Why strafe animations are needed
While locked, Arthur faces the target but walks sideways or backwards. With only the forward
walk he would glide sideways while walking forward. `BS_Arthur_LockOn` blends idle, forward
walk/run (Manny), strafe left/right and walk back by **Direction** and **Speed**.

### Clips
- On hand: `MIX_Strafe` (Mixamo "Strafe", already in the MixamoRT scene). The builder works
  out which way it goes and mirrors it for the other side.
- Still wanted from Mixamo (free): a **walking backwards** clip. "Sword And Shield Walk" has
  a backwards version; otherwise use "Walking Backwards". Download it **without** "In Place"
  ticked if possible (then its speed can be measured). FBX, with skin, 30 fps.
- Optional for nicer strafes: "Sword And Shield Strafe" (left and right).

## Henry steps (I do these by remote; nothing for you to paste)
1. Unreal: run `ue_lockon_setup.py` (variables, graph check, two red practice posts east of the
   player start in `L_Farm_Blockout`).
2. Paste `Arthur_LockOn_Nodes.txt` into `/Game/Characters/ArthurPipeline/BP_Arthur` Event Graph →
   Compile → Save. Test: Play, walk to the posts, press Tab.
3. Blender (`Arthur_rigged.blend`): import any new Mixamo clips as `MIX_*`, then
   `blender_lockon_set.build(out_dir=...\ArthurAdv\pipeline\anims)`.
4. Unreal: run `ue_lockon_strafe_import.py` → clips in `/Game/Characters/ArthurPipeline/LockOn/`
   plus `BS_Arthur_LockOn`. If samples can't be set from Python, place them in the blend-space
   editor (idle row at Speed 0; each clip at its speed from `lockon_set.json`).
5. `/Game/Characters/ArthurPipeline/ABP_Arthur`: in the Event Graph add `IsLockedOn` (from the
   owning BP_Arthur) and `Direction` (Calculate Direction from velocity and actor rotation); in the
   walk/run state, Blend Poses by Bool on `IsLockedOn` → `BS_Arthur_LockOn` (Direction, Speed).
6. Play test; tune the four numbers above.

## Later
- Target marker above the locked enemy (Zelda arrow).
- Switch target with the mouse wheel / right stick.
- Sidestep and backflip dodges while locked (Dodge currently always rolls toward the target).
