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
  uniform 98x148 grid with feet aligned; see `tools/slice_character_sheet.py`).
- **Placeholder, drawn in code:** everything else (farm, house, wolves, parents, the Stranger,
  Hen-a-wen, the crash) and the weapon swing and roll effects. There's no attack or roll art yet.
- **No side/back idle art:** side and back idles hold one walk frame.

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
