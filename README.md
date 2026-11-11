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

## Arthur's side walk (traced from a reference, skinned rig)
The original sheet's four side-walk frames are all the same pose, so Arthur's side walk is
generated from his one good side pose by `tools/walk_skin.py`.

- **Motion is traced from a reference walk.** `tools/ref_walk_tracking.json` holds, for all 10
  frames of the reference: where the planted/swinging foot is, how high it lifts, where each
  fist is relative to the shoulder, and the head height. Those curves drive Arthur:
  - **Feet:** each ankle follows the traced foot path (steady push back while planted, high
    lift at passing, reach forward), and 2-bone IK works out the hip and knee.
  - **Arms:** the fist follows the traced fist path, swinging further forward than back. Arm IK
    keeps the elbow pointing back: nearly straight when the arm trails, bent about 80 deg
    with the fist at the chest when it leads.
  - **Bob:** follows the traced head bob (low at contact, high through passing), never so high
    that a planted leg would have to over-stretch.
- **The art bends, it doesn't come apart.** Each layer (far arm, far leg, body, near leg, near
  arm) is warped as one continuous mesh with fixed triangles. Points near a joint blend the two
  bones' angles and rotate about the shared joint, so knees and elbows bend without gaps. Both
  arms are complete layers attached at the shoulder.
- **No jitter.** `tools/build_walk_strip.py` places every frame identically in its cell.
- **Tuning:** settings are in `MOTION` at the top of `walk_skin.py`: stride, lift, bob, reach
  when leading/trailing, frames. Joint positions are in `tools/arthur_rig.json`.
  `tools/arthur_walk_spec.md` lists every angle per frame.
- **Walk speed:** the game's walk speed (`SPEED` in `scripts/player.gd`, 119 px/s) matches the
  stride at 20 fps so the planted foot doesn't slide. Speed = cycle travel (cell px) x 0.75 / 0.6 s.

Rebuild (inside `tools/`):
```
python3 walk_skin.py arthur_rig.json && python3 build_walk_strip.py arthur && cp arthur_side_walk.png ../art/
python3 walk_skin.py arthur_stand_rig.json   # standing side pose (see README history for the cell step)
```
Needs Python 3 with Pillow, numpy, scipy and opencv-python.

Motion reference: "male hero" walk by Ozzbit Games (free version, non-commercial license),
used only to measure timing and body-part paths; none of its art is in the game.

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
