# Quadruped test — 27 Nov 2026

## Skeletons (African Animals pack)
All six animals use the same 3ds Max CAT-style naming (`<ANIMAL>_-Pelvis`, `-Spine`, `-L-Thigh`...),
differing only in prefix and counts:

| Animal | Bones | Spine | Neck | Tail | Legs | Extras |
|---|---|---|---|---|---|---|
| Lion | 39 | 3 | 2 | 9 | 4-bone (HorseLink), hind legs off Spine | toes |
| Zebra | 35 | 2 | 4 | 6 | 4-bone | — |
| Rhino | 33 | 2 | 2 | 6 | 4-bone | — |
| Hippo | 28 | 2 | 2 | 3 | 4-bone | — |
| Elephant | 48 | 2 | 2 | 7 | **3-bone** (no HorseLink) | trunk (14), ears |
| Crocodile | 38 | 2 | 2 | 7 | **3-bone**, sprawled | 2 toes / 2 fingers |

## Transfer test (IK rigs + retargeters in `/Game/Creatures/QuadTest`)
One chain template on every animal: Spine, Neck, Head, Jaw, Tail, FrontLeft, FrontRight,
BackLeft, BackRight; retarget root = Pelvis. Chains map automatically by name; differing bone
counts (2 vs 4 neck bones, 3 vs 9 tail bones) are handled by the retargeter.

Measured over 16 samples of each walk (foot = ankle bone height, cm):

| | front foot lowest | back foot lowest | step height | leg bend (min length) | pelvis |
|---|---|---|---|---|---|
| Rhino, own walk | 38 | 16 | 13–16 | 0.88–0.95 | 150–152 |
| Rhino, zebra walk | 32 | 17 | 12–15 | 0.97–0.99 | 150–151 |
| Hippo, own walk | 14 | 12 | 11–16 | 0.78–0.83 | 119–123 |
| Hippo, lion walk | 7–12 | 6–12 | **23–33** | 0.75–0.89 | 122–125 |

## Findings
- Transfer works between all four-bone-leg animals with no per-bone work. Body height stays
  put and legs never over-stretch.
- The **style** of the motion travels with it. The zebra walk on the rhino is close to the
  rhino's own (slightly stiffer front legs). The lion walk on the hippo is too springy: steps
  twice as high and feet dipping ~5 cm lower. Heavy bodies need their own walk or foot IK.
- Elephant and crocodile have three-bone legs and the crocodile is sprawled: different leg
  mechanics, not tested for transfer.
- A Blender preview of the animations was unreliable for these rigs (axis conversion), so the
  test is numeric. Test actors `QuadTest_*` are in ThirdPersonMap at Y 12000–13350 for a visual
  check with Simulate.

## Proposed standard
- **Quadruped = shared chain template, not one shared skeleton.** Bone counts vary too much
  between animals; the 9-chain IK rig template does the sharing.
- Two motion families: **light / predator** (lion as the source; use for wolves) and
  **heavy / hoofed** (zebra or rhino as the source). Animations move freely within a family;
  across families only with foot IK and tuning.
- Elephant-type (three-bone legs) and crocodile-type (sprawled, long body) are separate
  archetypes, set up when a creature of that type is needed.
