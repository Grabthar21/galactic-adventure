# Sprixen character animation pipeline

## Two looks (config.json `style`)
- **Sprixen style (Arthur since 23 Nov 2026, user's choice):** `{"cell_scale": 1.5, "head_lock": false, "reink": false}`.
  Sprixen's own head turn and hair motion are kept (no pasted head, so no seam at the neck), outlines stay
  soft (no pixel look), cells are 147x222 and the game draws them at half scale with smooth filtering
  (`player.gd` reads the cell size from each strip's height). Steps: `clean_sheet.py` (soft-edged matte
  clean-up, closes nape/collar notches, removes backdrop boxed in between arm and body) -> `match_head.py`
  (approved head size + steadied bob) -> `match_legs.py` (never taller than standing + smooth head path:
  legs stretch/shrink a few px so Sprixen's wobbling ground line doesn't make him hop) -> `fix_gloves.py`.
  Hairstyle sets are skipped in this mode (each style would need its own Sprixen walks).
- **Locked-face pixel look (earlier):** `head_lock: true, reink: true, cell_scale: 1` (98x148 cells; `lock_head.py` +
  `stamp_head.py`).

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

## Player customization (skin tone, hair colour, hairstyle)
- Every strip gets a `*_mask.png` (R = skin, G = hair) from `masks.py`; `shaders/recolor.gdshader`
  re-shades those pixels to the player's chosen colours in-game, keeping line art and shading.
  The reference colours are stored in `art/<name>_anims.json` (`skin_ref`, `hair_ref`).
- **Hairstyles:** add drawings of the three approved poses with only the hair changed
  (Sprixen, reference = the approved base sprite, "change ONLY his hairstyle") to
  `chars/<name>/styles/` and list them in `config.json` under `hairstyles`. The build aligns each
  to the approved body by the torso, keeps the approved face (`compose_style.py`), and builds a
  full set `art/<name>__<style>_*` using the same walk motion (no new walk renders). The list of
  styles goes to `art/<name>_styles.json` for the title screen.
- Check with the real renderer: `xvfb-run -a godot --rendering-driver opengl3 --path . -s tests/render_appearance.gd`
  (also `render_title.gd`, `render_ingame.gd`) -> screenshots in /tmp.

## Output
`art/<name>_<side|down|up>_<walk|idle>.png` (98x148 cells, feet on row 147) and
`art/<name>_anims.json` (frames + fps). `scripts/player.gd` loads them by name automatically
(the JSON is exported via `include_filter="art/*.json"`). Walking left = the side walk mirrored.

## What the build does
- **Walks:** cut the cleanest seamless loop (`find_loop.py`) -> rescale to the approved drawing
  (`match_scale.py`) -> paste the approved head on every frame + clean Sprixen's background
  removal (`lock_head.py`, head rows found by `head_rows.py`) -> repaint bare fingers
  (`fix_gloves.py`) -> match skin to the side view (`skin_match.py`) -> build strip.
- **Legs:** `match_legs.py` - a walk may never stand taller than the standing drawing; if Sprixen drew the legs
  longer (Arthur's back walk was ~2.5% taller), the legs are shortened by whole pixels, head/torso untouched.
- **One face:** `stamp_head.py` - after the strips are built, idle frame 0's head is re-stamped on every walk and
  idle frame at whole-pixel positions (no jumps >1px), so the face is pixel-identical in every frame.
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
