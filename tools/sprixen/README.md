# Sprixen character animation pipeline

Turns Sprixen output into clean, consistent in-game walk + idle strips for any character,
and checks every frame. Arthur (`chars/arthur/`) is the worked example.

## One command
    python3 tools/sprixen/build_char.py <name>      # ~35 s, prints QA, exit 1 on any failure

## What a character folder needs (`tools/sprixen/chars/<name>/`)
| file | what it is |
|---|---|
| `config.json` | settings (copy `chars/arthur/config.json`, change `name`) |
| `base_side.png` | approved 3/4 right-facing standing drawing, 256x256 (this is "the look") |
| `base_front.png`, `base_back.png` | approved front / back standing drawings, generated from the side one |
| `raw/walk_side.png`, `raw/walk_down.png`, `raw/walk_up.png` | Sprixen **premium** walk sheets |

## Output
`art/<name>_<side|down|up>_<walk|idle>.png` (98x148 cells, feet on row 147) and
`art/<name>_anims.json` (frames + fps). `scripts/player.gd` loads them by name automatically
(the JSON is exported via `include_filter="art/*.json"`). Walking left = the side walk mirrored.

## What the build does
- **Walks:** cut the cleanest seamless loop (`find_loop.py`) -> rescale to the approved drawing
  (`match_scale.py`) -> paste the approved head on every frame + clean Sprixen's background
  removal (`lock_head.py`, head rows found by `head_rows.py`) -> repaint bare fingers
  (`fix_gloves.py`) -> match skin to the side view (`skin_match.py`) -> build strip.
- **Idles:** the approved drawing breathing gently (`breathe.py`); Sprixen idles are not used.
- **Strip build:** premultiplied area downscale, defringe, pinhole fill, speck removal,
  outline re-ink, feet snapped to the ground (`resample.py`); one scale per direction from
  the base drawing's height so walking/standing/turning never changes size.
- **QA:** `qa_strip.py` (fringe, haze, holes, specks, ground, size, drift, head lock, pops,
  loop seam; contact sheets in /tmp/qa_*.png) and `qa_cross.py` (walk vs idle size/position).

## Quality standards (from the user's feedback on Arthur)
Locked face (same drawing every frame) - no hair motion - gloved hands, no bare fingers -
crisp outline, no colour off the face edge - no white/green fringe or haze - skin and size
identical across all directions - calm, subtle breathing idle with feet still - no jitter.

`legacy/` holds the earlier Arthur-only scripts.
