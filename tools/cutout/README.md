# Arthur cut-out side walk (test hero "arthur_v2")

Source: `Arthur_right_reference.png` / `Arthur_front_reference.png` (generated parts sheets,
opaque checkerboard background). Pipeline, run in this folder:

1. `python3 key_checker.py Arthur_right_reference.png right_alpha.png` (and the same for front):
   removes the checkerboard and gives soft, defringed edges.
2. `python3 build_torso.py`: armless torso that keeps buttons/neckerchief/buckle (front torso
   minus its baked-in arm, laid over the plain side torso for the hidden back of the vest).
3. `python3 build_legs.py`: the side sheet has no thigh, so the thigh comes from the front
   sheet; the lower leg is the side navy knee piece tucked into the boot cuff (one rigid piece).
4. `python3 cutout_walk.py arthur_parts.json`: rigs and renders 12 frames + standing pose.
   - Parts only rotate about joints (no stretching).
   - Legs/arms use 2-bone IK driven by the reference walk traced in `ref_walk_tracking.json`.
   - The hip bob is identical for both steps and never over-stretches a planted leg.
   - Hair bounces as a damped spring hanging off the head (it lags each footfall, then settles);
     the face and ear never bend.
   - The far arm is hidden behind the back above the waist.
5. `python3 build_cutout_strip.py arthur_cut 124`: 98x148 game cells, fixed placement.
   Prints the matching walk speed (119 px/s) -> `SPEED_V2` in `scripts/player.gd`.
6. Copy `arthur_cut_side_walk.png` / `arthur_cut_side_idle.png` to `../../art/arthur_v2_side_*.png`.
