# Space Piece: Opening Prototype (Godot 4.5)

The first five minutes of the game, following the family's "Option Omega" beat sheet:
farm chores with Hen-a-wen, the wolf fight, the wolf pup choice, dinner, the crash,
the Stranger and the Black Access Key, the Father's Sword, and the Goblibots arriving.

## Open it
1. Install Godot 4.5.x (standard build, not .NET).
2. In the Project Manager, Import and pick this folder's `project.godot`.
3. Press F5 to play.

## Controls
- Move: WASD / arrow keys / left stick
- Attack (3-hit combo): J / left-click / gamepad X (Square on PlayStation)
- Dodge roll: Space / gamepad A (Cross on PlayStation)
- Interact / talk: E / Enter / gamepad B (Circle on PlayStation)

The input actions are added in `scripts/game_state.gd` at startup. If you add the same
actions in Project Settings > Input Map, yours take priority.

## What's real art and what's placeholder
- **Real:** Arthur and Gwen walk and idle sprites (from the Drive sheets, re-sliced into a
  uniform 98x148 grid with feet aligned; see `tools/slice_character_sheet.py`). Arthur's side
  walk is rigged from his side pose (see below). Gwen's side walk still uses the sheet as-is.
- **Placeholder, drawn in code:** everything else (farm, house, wolves, parents, the Stranger,
  Hen-a-wen, the crash) and the weapon swing and roll effects. There's no attack or roll art yet.
- **No side/back idle art:** side and back idles hold one walk frame.

## Arthur's side walk (skinned rig)
The original sheet's four side-walk frames all show the same pose, so Arthur's side walk is
generated from his one good side pose by `tools/walk_skin.py`:
- **No gaps:** each layer (far arm, far leg, body, near leg, near arm) is warped as one
  continuous mesh over a skeleton, the way Spine and Live2D bend art, so limbs never come
  apart at the knees or elbows.
- **Planned feet:** the feet follow paths. A planted foot slides back at exactly the walking
  speed; a swinging foot lifts in a smooth arc. 2-bone IK works out the hip and knee angles.
  Heel strike and toe-off tilt the sole, and the lowest point of the foot always touches the
  ground.
- **Smooth bob:** the hips bob on an even curve twice per step (lowest at contact). Arms swing
  opposite the legs.
- **No jitter:** every frame is placed in its cell the same way (`tools/build_walk_strip.py`),
  so the frames are never shifted against each other.
- **Settings:** stride, lift, bob, arm swing, frame count and the rest are in `MOTION` at the
  top of `walk_skin.py`. Joint positions are in `tools/arthur_rig.json`.
  `tools/arthur_walk_spec.md` lists every joint angle per frame.
- **Walk speed:** the game's walk speed (`SPEED` in `scripts/player.gd`, 116 px/s) matches the
  stride at 20 fps, so the planted foot doesn't skate. If you change the stride or fps,
  update it: speed = (cycle travel in cell px x 0.75) / (frames / fps).

Rebuild (run inside `tools/`):
```
python3 walk_skin.py arthur_rig.json && python3 build_walk_strip.py arthur && cp arthur_side_walk.png ../art/
```
The standing side pose (`art/arthur_side_idle.png`) comes from the same rig with
stride, bob and swing set to 0 (`arthur_stand_rig.json`).
Needs Python 3 with Pillow, numpy, scipy and opencv-python.

Motion reference: "male hero" walk by Ozzbit Games (free version, used only to study timing,
not included in the game).

## Files
- `scripts/main.gd`: story director (the whole opening, scene by scene)
- `scripts/player.gd`: movement, 3-hit combo, dodge roll with invulnerability, health
- `scripts/wolf.gd`: wolf AI (circle, red-flash telegraph, lunge; at most 2 attack at once)
- `scripts/ui.gd`: HUD, dialogue and choices, title screen, end card
- `scripts/world.gd`, `scripts/prop.gd`: placeholder farm, house and characters
- `scripts/game_state.gd`: hero, name, Valor and choice flags (autoload)
- `tests/playthrough_test.gd`: automated test (combat checks plus a full playthrough)

Run the tests:
`godot --headless --script res://tests/playthrough_test.gd -- arthur 0`
(the second argument picks the first or second option at each choice)

## Web build
Export with the "Web" preset (thread support off). To publish on the claude.ai artifact host,
run `python3 tools/postprocess_web.py build/web`. It packs the files to fit the host's
size and file-type limits.
