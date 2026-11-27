# Space Piece — Art Style Guide (v1.0, 27 Nov 2026)

**What this is for:** decide the look once, so new characters, creatures and places come out on-model the first time instead of being fixed detail by detail. Every rule here comes from a decision already made, mostly while fixing Arthur. When a new fix is needed, it becomes a new rule here (section 12), so it never comes up twice.

**Where it lives:** this project (`claude/Art_Style_Guide.md`) and the repo (`pipeline/style/`). The measurable rules are in `pipeline/style/style_rules.json`, which the style check (`pipeline/scripts/blender_style_check.py`) reads. Change a number in one place and both follow.

**Reference character:** Arthur, as approved on 26–27 Nov. When in doubt, put the new character next to Arthur under the review lighting (section 10).

---

## 1. The look in one line
A warm, storybook fantasy adventure: **Zelda-like stylised people and creatures, Treasure Planet-like ships and space**. The shapes are chunky and readable, the textures soft and painted, the materials matte, and the faces friendly and simple.

Four pillars:
1. **Silhouette first.** Every character is recognisable as a black shape from the gameplay camera.
2. **Colour carries the detail, not geometry.** Painted shading, not wrinkles and pores.
3. **Soft, matte, warm.** Nothing glossy, wet, neon or photo-real.
4. **Family-friendly.** Friendly faces, no gore, nothing scary up close except deliberate villains and creatures.

## 2. Proportions

| Group | Head size (share of height) | Arm length | Leg length | Feel |
|---|---|---|---|---|
| Child | 0.14–0.18 | 0.22–0.30 | 0.38–0.47 | big head, short limbs |
| Teen (Arthur) | 0.13–0.17 | 0.22–0.30 | 0.40–0.48 | ~6–7 heads tall |
| Adult | 0.11–0.15 | 0.26–0.34 | 0.42–0.50 | ~7 heads tall, still chunky |

- How it's measured: head = top of the model down to the head bone; arm = upper arm + forearm bones; leg = thigh + shin bones; each divided by total height.
- **Arthur:** head 0.151, arm 0.245, leg 0.436; 160 cm; 6.2 heads tall counting hair. His arms are short on purpose (about 75% of realistic).
- Hands and feet are slightly oversized and simple. Boots are chunky.
- Villains and creatures may break these numbers, but must say so in their character entry.

## 3. Shape language
- **Heroes and friends:** rounded shapes, soft corners, slightly oversized heads and hands.
- **Villains and danger:** sharper, angular shapes. Shape alone should hint at who is safe.
- **Clothing:** a few big folds, not many small ones. Belts, straps and buckles are fine, but chunky: no fine laces, tiny rivets or thin chains.
- **Props and weapons:** about 1.2× realistic thickness, so they read at game distance.

## 4. Colour

Arthur's approved colours, as they look under the review lighting:

| Part | Colour |
|---|---|
| Vest (dark leather) | `#473027` |
| Trousers (grey-brown) | `#583d32` |
| Boots and hair | `#84523c` |
| Light leather | `#a76e4f` |
| Skin | `#b98a70` |
| Shirt (cream) | `#c2a28e` |
| Deepest shadow | `#32221b` |

Rules:
- **Warm, earthy base, plus one clear accent colour per character.** The accent is what you'd name the character by ("the one in blue").
- **No pure black and no pure white** in painted textures (under 3% near-black, under 2% near-white). Black reads as holes in the game; white blows out in sunlight. Eye whites are the only exception.
- **No neon** on people or animals. Glow is reserved for magic, tech and pickups.
- **Saturation in the middle:** not grey and washed out like a photo scan, not toy-like.
- Crew members and factions each get a signature accent that is clearly different from Arthur's browns.

## 5. Textures and materials
- **Painted, soft textures.** Shading painted in broad shapes. No photo detail, noise or speckle (the style check measures this).
- **Matte materials:** roughness 0.85, specular 0.25, metallic 0. Only real metal parts (buckles, blades, armour) can be metallic, and even they stay fairly rough (≥ 0.35).
- **Textures at most 2K** (2048). The eyes get their own texture on hero characters.
- **One shared character material in Unreal (planned: `M_Character_Master`).** Every character becomes an instance of it, with the same dials for colour, shading softness and rim light. To change the look of all characters, change the master once.

## 6. Faces
**Always:**
- A small, closed or nearly closed mouth. A smile is shown by the mouth's shape, not by an open grin.
- Simple painted eyes, slightly large, with **one small highlight per eye, on the same side in both eyes**.
- Clean eye whites, with no skin or brown colour bleeding into them.
- Both eyes the same size and height (within 5%).
- Brows clear enough to read from the gameplay camera; they carry most of the expression.
- Hero characters get eyes as their own material and texture (Arthur: `M_Arthur_Eyes`, 1024×512).

**Never:**
- Teeth or the inner mouth visible through or between the lips (Arthur's "transparent lips").
- Glossy, wet or mirror-like eyes (the "Digimon eyes" problem).
- Pores, wrinkles or realistic skin detail on friendly characters.
- **A wide open grin carved into the model.** It can't be fixed by painting: regenerate the head instead (pipeline standard, reject rule).

## 7. Pose, hands and feet (for every new model)
- **Generate and rig in an A-pose:** arms about 30° from the body, palms facing in, **feet pointing straight forward** (Arthur's boots came out turned 25–30° outward, which made him walk duck-footed).
- Hands open and relaxed if possible; fused curled fingers work, but need fitting (Arthur's fingers).
- Nothing held in the hands at generation time. Weapons and props are separate models.

## 8. Clothing and outfits
- Outfit slots, Zelda style: **head, body (torso and arms), hands, legs, feet**, cut on the same seams as Arthur so pieces swap.
- No body underneath the clothes: each piece replaces that part, so nothing pokes through.
- Capes and long coats are add-on pieces.

## 9. Creatures and places
- **Creatures** follow the same colour and material rules. They are stylised, slightly chunky and expressive, with readable eyes. Predators (wolves) are sharper in shape but not gory. Bodies use the quadruped standard in the pipeline doc.
- **Places** use the same warm palette and matte materials. Shapes are chunky: thick roof edges, round trees, big readable landmarks (the escape hill, the barn). Paths and points of interest stand out from the ground in colour.

## 10. Making a new character: one pass, one review
1. **Brief, in the character entry:** name, hero or not, group (child, teen, adult or creature), height, accent colour, must-have parts, and 1–3 reference pictures.
2. **Concept sheet first**, front and side view, approved by you. Feedback is cheapest here: a picture, not a 3D model.
3. **Generate the 3D model from the approved concept sheet plus Arthur's front view as a style reference,** using the prompt template below. Always use the same generator, version and settings, and record them in the entry.
4. **Pipeline:** import check → cleanup → rig → **style check**, which auto-fixes material values and flags everything else.
5. **One review round** on the standard turnaround (front, three-quarter, side, back, face close-up) under the same lights every time, next to Arthur. Give all feedback in one go, using the checklist below.
6. Fixes, then a final check. Anything you correct becomes a new rule in section 12.

**Prompt template** (also in `style_rules.json`):
> {subject}, stylised 3D game character for a family action-adventure, storybook proportions (slightly large head, about 6 to 7 heads tall), soft hand-painted textures, warm earthy palette with one clear accent colour, clean readable silhouette, matte materials, small closed mouth, simple painted eyes with one small highlight, full body, A-pose, arms 30 degrees from body, feet pointing straight forward, plain neutral background, front view

**Avoid:** open mouth, visible teeth, glossy or wet eyes, photo-realistic skin, pores, heavy wrinkles, neon colours, glowing parts, armour spikes, busy noisy textures, T-pose, crossed arms, holding props, copying any existing game or film character.

The prompt describes the style instead of naming another game, so the generator doesn't drift toward copying an existing character.

**Review checklist** (one pass):
- [ ] Silhouette: recognisable, and the accent colour is clear
- [ ] Proportions next to Arthur
- [ ] Face: mouth, eye shine, eye whites, eyes even, brows
- [ ] Colours warm, no black holes or white blowouts
- [ ] Matte: no shine on skin or cloth
- [ ] Must-have parts present
- [ ] Hands and feet: clean, feet straight
- [ ] Anything else, written as "always" or "never" so it can become a rule

## 11. What the style check does
`blender_style_check.run(...)` writes a report (`<name>_style_report.md` and `.json`) and the turnaround renders.

| Area | Measured | If it fails |
|---|---|---|
| Proportions | head, arm and leg size compared with height, by group | ASK |
| Base-colour textures | near-black, near-white, colour strength, neon, photo-like noise, size | ASK (size: FIX in cleanup) |
| Materials | roughness, specular, metallic (metal parts excepted) | **auto-fixed**, logged |
| Face | own eye material on heroes, eye texture ≥ 512 | ASK |
| Face details | mouth, eye shine, eye whites, eye symmetry, brows | CHECK on the face render |

- Heroes stay on ask-first for anything that changes their look (pipeline standard).
- The "painted look" noise limit (0.055) is provisional. **Calibrate it on Arthur's texture** the next time Henry is on.

## 12. Rules learned (log)
| Date | Problem | Rule |
|---|---|---|
| 26 Nov | Teeth visible through "transparent" lips | Small closed mouth; no inner mouth showing |
| 26 Nov | Glossy "Digimon" eye shine | One small painted highlight per eye, same side |
| 26 Nov | Brown in the eye whites | Clean whites; eyes as their own material on heroes |
| 26 Nov | Wide grin carved into the model | Don't repaint; regenerate the head |
| 26 Nov | Comparison renders looked worse under harsh light | Always compare under the standard review lighting |
| 27 Nov | Duck-footed walk (boots turned out 25–30°) | Generate with feet straight forward; rig to Manny's foot angle |
| 27 Nov | Hands crossing in the walk | A-pose at about 30°; match Manny's arm angle at rig time |
| 14 Nov | Shiny skin and cloth in Unreal | Matte: roughness 0.85, specular 0.25 |
