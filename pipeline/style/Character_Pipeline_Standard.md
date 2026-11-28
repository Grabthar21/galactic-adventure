# Space Piece — Character & Creature Pipeline Standard (v0.9, 27 Nov 2026)

Status: **biped pilot passed (Arthur, playable); quadruped standard approved 27 Nov (first real creature: a wolf)**. Numbers come from `SpacePiece3D` (UE 5.4.4). Full pilot logs: `pipeline/reports/` in the `galactic-adventure` repo (branch `pipeline-standard`).

Decisions (26 Nov): stylised look closer to Zelda; the user names which characters are heroes; creatures get their own folder; character entries live in this project and in the `galactic-adventure` GitHub repository. Decision (27 Nov): quadruped approach below approved. Decision (27 Nov): **the look is set by `Art_Style_Guide.md`** (with its measurable rules in `pipeline/style/style_rules.json`), and every model passes the style check before review. Decision (27 Nov): **one report card per review** (`run_character.py`), and **approved assets are fingerprinted and locked** (`asset_guard.py`); they change only through a new version.

## 1. Purpose
Every character or creature enters Unreal through the same steps and checks, so results are repeatable and problems are caught at import, not discovered during animation. All placement, scale and offsets come from data (the character entry), never from eyeballing.

## 2. Archetypes

| Archetype | Standard | Used for | Status |
|---|---|---|---|
| **Biped** | UE5 Mannequin (`SK_Mannequin`, Manny) — shared skeleton asset | Arthur, crew, humanoid enemies | **Arthur on it and playable** (`BP_Arthur`) |
| **Quadruped** (four-bone legs) | **Shared 9-chain IK rig template**, not one shared skeleton: Spine, Neck, Head, Jaw, Tail, FrontLeft/Right (clavicle→hand), BackLeft/Right (thigh→foot); retarget root = Pelvis. Source animation families: **light/predator = lion** (use for wolves), **heavy/hoofed = zebra or rhino** | Wolves, mounts, beasts, most monsters | **Approved 27 Nov**; transfer tested (zebra→rhino, lion→hippo) |
| **Long-body / reptile** | Separate archetype (crocodile: sprawled, three-bone legs) | Crocodile, lizards, low creatures | Set up when first needed |
| **Heavy three-bone-leg** | Separate archetype (elephant: no HorseLink, trunk) | Elephants, giant beasts | Set up when first needed |
| **Winged** | Not yet defined | Birds, flying monsters | Later |
| **Serpent / other** | Not yet defined | Snakes, blobs, multi-limbed | Later |

Rules:
- Same archetype = same bone names and hierarchy (bipeds) or the same chain template (quadrupeds). Proportions, bone lengths and scale may differ freely.
- **Shared skeleton = same bone orientations.** Only joint positions move to fit the new body; bone axes stay exactly as in the archetype skeleton. Turning bones to follow the new limbs makes every shared animation lean or twist (Arthur hunched forward).
- **Match the archetype's rest pose.** Shared animations keep each body's rest offsets, so before binding compare and re-pose to the archetype's rest pose: **arm angle** (Arthur's hands crossed in front of him) and **foot direction** measured from the sole (Arthur's boots turned out 25–30° vs Manny's 6.5°, making him walk duck-footed). Fix by rotating the limb in the rest pose and applying it as the new rest.
- **Fingers**: fit finger bones to the actual fingers (generator hands rarely match Manny's), weight from the hand and smooth across the mesh; test a half curl and a full fist.
- **Quadrupeds:** bone counts vary too much (2–4 neck, 3–9 tail bones) for one shared skeleton, so sharing happens through the chain template and a retargeter per pair. Animations move freely within a motion family; across families (light → heavy) the style comes along (lion walk on hippo: steps twice as high, feet ~5 cm low), so use the body's own set or add foot IK and tuning.
- Extras (tail, wings, ears, cape, tusks) are **add-on bones or attached parts**. They never rename or remove core bones.
- Big size changes get their own locomotion tuning (play rate, weight, or a dedicated set), not just scaling.

## 3. Look and budgets
Art direction: **stylised, closer to Zelda** — clean readable shapes, painted/hand-coloured textures, detail carried by colour and silhouette rather than dense geometry. Full rules (proportions, palette, faces, materials, prompt template, review checklist): **`Art_Style_Guide.md`**.

| Class | Triangles (LOD0) | LODs | Materials | Bones |
|---|---|---|---|---|
| Hero character | 20–40k | 3+ | ≤ 4 | archetype standard (+ add-ons) |
| Background / NPC | 8–20k | 3+ | ≤ 3 | archetype standard |
| Creature | 5–15k (large/hero creature up to 25k); up to 10% over = warning | 2+ | ≤ 3 | archetype standard (+ add-ons) |
| Attachment (tusks, weapons, hats) | ≤ 2k | 1–3 | 1 | none / socket |

- **Small face features get their own material when they need fixing** (Arthur: eyes `M_Arthur_Eyes`, mouth `M_Arthur_Mouth` with a normal map). Planar-projected UVs for those faces go in the first UV map, because Unreal builds normal-map tangents from UV channel 0.
- **Eyes get their own material and texture** on hero characters (generators give each eye only a tiny patch of the main texture). Arthur: `M_Arthur_Eyes`, 1024×512.
- **Hero status is set by the user**; heroes get the higher budget and stay on ask-first for any fix that changes their look.

## 4. Naming and folders
- Characters: `/Game/Characters/<Name>/`. Creatures: `/Game/Creatures/<Name>/`. Purchased packs stay in their own folder.
- Prefixes: `SK_`, `SKEL_`, `SM_`, `M_`/`MI_`, `T_` (`_D`, `_N`, `_ORM`/`_RM`), `A_`, `AM_`, `BS_`, `ABP_`, `IK_`, `RTG_`, `BP_`.
- One approved version per character; old versions archived. Similar names in different folders cause mistakes: manual editor steps always give the full asset path.
- Scale: 1 unit = 1 cm in Unreal. Root at the feet.

## 5. Character entry (one per character)
Filled by the user: name, archetype, hero yes/no, references, rough height, must-have parts, **style group (child / teen / adult / creature) and accent colour**.
Filled by the pipeline: import/cleanup/rig results, skeleton, LODs, materials, log of fixes and approvals, **stage and version**, the Blender objects to check (`blender`), the files to protect (`protect`), and the approval fingerprint (`approved`, `approved_ue`).

**Stages:** brief → concept → model → review → **approved** (→ archived). Only the user approves. An approved character is never edited in place: `asset_guard new-version` unlocks it as v2, back at *model*, and it goes through review again.
Stored as JSON in this project (`claude/entries/<name>.json`) and in the repo (`pipeline/entries/<name>.json`); the repo copy is what scripts read.

## 6. Pipeline steps
1. **Source**: high-detail model (Tripo, Sprixen, pack, hand-made), generated from an **approved concept sheet** with the style guide's prompt template and Arthur's front view as style reference. Inputs locked: cropped front view, A-pose (arms ~30°, feet straight forward), same generator, version and settings, recorded in the entry.
2. **Import check** (Blender, `blender_import_check.py`): triangles, debris, pieces, flipped normals, non-manifold, scale, textures, materials, armature.
3. **Cleanup** (Blender, `blender_cleanup.py`): keep the source untouched; scale; delete debris; reduce in passes (head region gentler than body); downscale textures; keep UVs so the original paint still lines up. **Do not recalculate normals** on multi-piece models. **Clear imported custom normals and merge seam duplicates before any shape edit.** Compare face directions against the source after every geometry step.
4. **Rig**: archetype skeleton (bipeds) or a rig that fits the quadruped chain template; joints moved to the body, archetype bone orientations kept, arms and feet re-posed to the archetype rest pose; fingers fitted; weights; test with a real archetype animation (walk) from the side, front and above. Quadrupeds: also measure foot height, step height and leg stretch against the body's own walk.
4b. **Style check** (Blender, `blender_style_check.py`): proportions by style group, base-colour textures (near-black/white, colour strength, neon, photo-like noise), matte materials (auto-fixed), hero eye material; renders the **standard review turnaround** (front, three-quarter, side, back, face; fixed lights and camera).
4c. **Pose stress test** (Blender, `blender_pose_test.py`): rest pose foot direction (max 12°; Manny ~6.5°), arm angle (15–50° A-pose), hand clearance from the hips, feet on the floor; then walk, run, crouch, arms up, sword ready, slash and fist: parts passing through each other (compared with the rest pose), stretching/squashing; one pose strip.
4d. **Report card** (`run_character.py` → `report_card.py`): runs 4b–4c plus the **game-camera view** (third-person camera, 4 m, 90° FOV, 1080p; about how big players see the character) and the **lineup** (next to Arthur, a 2.2 m door, 1.1 m fence, 88 cm sword), and writes **one page**: decisions for the user first, pictures to confirm, what was auto-fixed, then every check and a one-round feedback table. The user reviews this page once; each correction becomes a one-off fix or a style-guide rule.
5. **Export** (Blender → FBX), fixed recipe: model and rig in **meters**, scene unit scale **1.0**, a real `root` bone, armature object named `Armature`, Apply Scalings **FBX_SCALE_NONE**, no leaf bones, primary/secondary bone axis Y/X. (The old "unit scale 0.01" recipe gave a root bone scale of 0.01, which shared animations would undo, blowing the mesh up 100×.)
6. **Unreal import**: import as a fresh asset, consolidate the old one into it and rename back (a "replace" re-import adds duplicate material slots); assign materials; generate LODs.
7. **Final check** (Unreal, `ue_import_check.py`): budgets, naming, skeleton, root scale 1, height; animations play; walks forward; character blueprint swords/sockets in place.
8. **Approval** (user): `asset_guard approve` records a SHA-256 fingerprint of every protected file (Blender, FBX, textures, and the `.uasset` files behind the entry's `/Game` paths) and marks them read-only; `ue_fingerprint.record` stores what the Unreal setup is (mesh, anim blueprint, components and attach bones, assets the blueprint uses such as montages).
9. **Guard** (any time; before play tests and after engine or plugin updates): `asset_guard verify` lists approved files that changed, went missing or were unlocked; `ue_fingerprint.compare` says what changed in plain terms (e.g. "montage swapped", "sword moved to hand_l"). Approved characters are checked read-only by the report card.

**Commands (on Henry):**
- Report card, in Blender with the character's file open: `import run_character; run_character.run(r"...\pipeline\entries\<name>.json")`
- Stages and approval: `python pipeline/scripts/asset_guard.py stage <entry> review` · `approve <entry>` · `verify pipeline/entries/*.json` · `new-version <entry> --note "..."`
- Self-tests without real art: `make_test_figure.py` builds an on-style and an off-style rigged stand-in.

Previews are judged under even lighting with backface culling on (Eevee), never the flat Workbench view, and before/after always under the same lighting (the style check's turnaround is that standard setup).

## 7. Fix rules: auto-fix / ask / reject
- **Never on approved assets**: no script edits an approved character; the report card runs read-only and `asset_guard.guard_edit()` refuses changes.
- **Auto-fix** (logged): debris, holes, flipped normals, scale/orientation, over budget, missing LODs, naming, **material values (roughness, specular, metallic) to the style guide's matte settings**.
- **Ask first**: anything that changes the look: clothing parts, hands, face, eyes, proportions, painted colours. Show before/after; follow the entry, references and style guide.
- **Reject and regenerate**: when a fix means rebuilding a feature carved into the model (e.g. Arthur's wide open grin — painting and reshaping at 40k triangles left creases). Regenerate that part from an edited reference instead.
- Heroes stay on ask-first; repeat-proven fixes may become auto-fix for background characters only, by the user's decision.

## 8. Pilot results
- **Arthur (biped, hero) — passed, playable.** Source Tripo GLB 191k → 39.3k triangles; eyes rebuilt as own material; mouth kept as approved; rigged on `SK_Mannequin` with fingers (55 deforming bones); arms and feet matched to Manny's rest pose; 160 cm, root scale 1, 2 material slots, LODs 28.7k/7.7k/4.3k verts. `BP_Arthur` uses Manny's own locomotion and `ABP_Arthur`; sword clips retargeted into `ArthurPipeline/Sword`; hip, back and hand swords fitted. Game mode default pawn = `BP_Arthur`; old character kept as `BP_ArthurAdvCharacter_Legacy`.
  - Open: full fist shows small gaps between the fused fingers; Zelda-style mouth via a regenerated head when a Tripo generation is available; **the user approves v1** (`asset_guard approve`, then `ue_fingerprint.record`), which fingerprints and locks his files.
  - **Mouth rebuilt to Link's proportions, 27 Nov (user-approved):** width 0.33 of face width (was 0.64), 6 mm lower, real lips (upper 4.3 mm, lower 6.8 mm, normal map for volume) on its own material `M_Arthur_Mouth`; old carved smile flattened with depth-only moves (sideways moves tore holes in the loose face pieces). Re-exported and re-imported (fresh import, consolidate, rename): 3 slots, LODs 32.5k/9.4k/5.4k verts. Backups `Arthur_rigged_before_linkmouth.blend`, `SK_Arthur_before_linkmouth.fbx`.
  - **Report card run on Arthur, 27 Nov (Henry, 60 s):** style all pass (head 0.150, arm 0.244, leg 0.434; saturation 0.71; painted-look noise 0.013); face checklist for the user; rest pose matches Manny (arm 35.2°, feet 15/16.5° vs Manny 3° on the sole outline). Flags: deep crouch, thighs press 7 cm into each other (baggy trousers); arms straight up, upper arms dip ~6 cm into the hair; fist, fused-finger overlap (known). 364 px tall from the play camera. Card: `pipeline/reports/arthur_2026-11-27/`.
  - **Calibrated on Arthur and Manny:** foot limit 20° (sole outline: Manny 3, Arthur 15–16.5, Arthur before the fix ~35–40); arm angle and limb lengths measured joint to joint (UE bones in Blender don't point along the limb); colour strength 0.18–0.80; painted-look noise max 0.035; eye textures exempt from dark/bright/colour checks; poses compared with Manny's own results (`style/pose_reference_manny.json`): what Manny also does is a note, not a question.
  - **Unreal fingerprint tested on Arthur:** mesh (3 LODs, 2 slots), BP_Arthur (ABP_Arthur, AM_Slash_Outward_Fast, capsule 80/35, swords on pelvis / spine_05 / hand_r), repeatable, and catches a swapped montage or moved sword.
- **Quadrupeds**: all seven African Animals pass the import check (lion 131 triangles over → warning). Transfer test (`pipeline/reports/2026-11-27_quadruped_test.md`): zebra walk on rhino close to the rhino's own; lion walk on hippo too springy. Test assets in `/Game/Creatures/QuadTest`; test actors `QuadTest_*` in ThirdPersonMap (Y 12000–13350).
- **Crocodile / elephant**: separate archetypes, to set up when a creature of that type is needed.
