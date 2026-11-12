#!/usr/bin/env bash
# Rebuild all of Arthur's Sprixen animation strips from the raw Sprixen sheets, then QA them.
#   raw sheet -> [loop cut / swell removal] -> match_scale -> lock_head -> build strip -> qa
# Every direction is scaled from its approved standing drawing (BASE_H = its height in px)
# so Arthur is the same size walking, standing and turning.
set -euo pipefail
cd "$(dirname "$0")"
ART=../../art
W=$(mktemp -d)

# side (3/4 right): premium walk loop + idle
python3 find_loop.py arthur_walk_premium_sheet.png "$W/side_walk.png" 20 44
# front (down)
python3 find_loop.py arthur_down_walk_premium.png "$W/down_walk.png" 16 40
# back (up)
python3 find_loop.py arthur_up_walk_premium.png "$W/up_walk.png" 16 40

# Idles: Sprixen's idle frames jump between poses and ghost the chin, so each idle is the
# approved standing drawing itself (cleaned), breathing gently (breathe.py): 32 frames,
# chest/shoulders/head lift 2.4 source px (~1.5 game px), legs and feet perfectly still.
python3 - "$W" <<'PY'
import sys, numpy as np
from PIL import Image
from lock_head import clean_body
for n in ['v1', 'front', 'back']:
    b = np.array(Image.open(f'arthur_{n}_base.png').convert('RGBA')).astype(np.float32)
    Image.fromarray(np.clip(clean_body(b), 0, 255).astype(np.uint8)).save(f'{sys.argv[1]}/{n}_clean.png')
PY
python3 breathe.py "$W/v1_clean.png"    "$W/side_idle_l.png" 32 2.4
python3 breathe.py "$W/front_clean.png" "$W/down_idle_l.png" 32 2.4
python3 breathe.py "$W/back_clean.png"  "$W/up_idle_l.png"   32 2.4

run() {  # name base profile cycles kind base_h fps
  if [ "$5" = walk ]; then
    python3 match_scale.py "$W/$1.png" "arthur_$2_base.png" "$W/$1_s.png" "$3"
    python3 lock_head.py "$W/$1_s.png" "arthur_$2_base.png" "$W/$1_h.png" "$4" 0 "$3" > /dev/null
    python3 fix_gloves.py "$W/$1_h.png" "$W/$1_l.png"      # no bare fingers out of the gloves
  fi
  if [ "$5" = walk ]; then
    BASE_H=$6 python3 build_walk_strip.py "$W/$1_l.png" "$ART/arthur_$1.png" 133 "$7" > /dev/null
  else
    BASE_H=$6 python3 build_idle_strip.py "$W/$1_l.png" "$ART/arthur_$1.png" 133 > /dev/null
  fi
  cp "$W/$1_l.png" "arthur_$1_locked.png"
}
run side_walk v1    side  2 walk 209 36
run side_idle v1    side  1 idle 209
run down_walk front front 2 walk 215 37.5
run down_idle front front 1 idle 215
run up_walk   back  back  2 walk 202 30
run up_idle   back  back  1 idle 202
# cut-out test hero (smaller rig) reuses the side idle
BASE_H=209 python3 build_idle_strip.py arthur_side_idle_locked.png "$ART/arthur_v2_side_idle.png" 123 > /dev/null

status=0
for x in "side_walk walk" "side_idle idle" "down_walk walk" "down_idle idle" "up_walk walk" "up_idle idle"; do
  set -- $x
  python3 qa_strip.py "$ART/arthur_$1.png" "$1" 133 "$2" | grep -E "==|FAIL|RESULT" || true
  python3 qa_strip.py "$ART/arthur_$1.png" "$1" 133 "$2" > /dev/null || status=1
done
python3 qa_cross.py
exit $status
