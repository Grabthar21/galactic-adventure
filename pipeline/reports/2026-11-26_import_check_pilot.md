# Import check — pilot run, 26 Nov 2026

Project: `SpacePiece3D` (UE 5.4.4). Script: `pipeline/scripts/ue_import_check.py`.
Standard: `Character_Pipeline_Standard.md` in the claude.ai project.

## Arthur (hero, biped) — all three versions: ASK

| Version | Triangles | LODs | Materials | Skeleton | Height |
|---|---|---|---|---|---|
| SK_ArthurAdv (current) | 191,104 (4.8x limit) | 1 | 1 | own, 35 bones | 160 cm |
| SK_ArthurV2 | 358,357 (9.0x) | 1 | 8 | own, 62 bones | 164 cm |
| SK_Arthur | 365,001 (9.1x) | 1 | 6 | **none assigned** | 160 cm |

All fail on triangles and LODs (auto-fix from the high-detail source), all need rigging to
the Manny skeleton, and the must-have parts need visual confirmation. `SK_Arthur` has no
skeleton loaded, so it is broken and should be archived.

## African Animals pack (creatures) — pass

| Animal | Triangles | LODs | Mats | Height × length | Result |
|---|---|---|---|---|---|
| Lion | 15,131 | 4 | 2 | 144 × 286 cm | over by 131 triangles |
| Lioness | 10,214 | 3 | 2 | 133 × 278 cm | pass |
| Zebra | 6,349 | 3 | 1 | 189 × 288 cm | pass |
| Rhino (large) | 6,648 | 3 | 1 | 202 × 510 cm | pass |
| Hippo (large) | 7,836 | 3 | 1 | 181 × 399 cm | pass |
| Elephant (large) | 6,810 | 2 | 1 | 409 × 627 cm | pass |
| Crocodile | 8,118 | 3 | 1 | 111 × 636 cm | pass |
| Elephant tusks, big | 596 | 3 | 1 | — | pass |

## Takeaways
- The check separates good assets from bad ones as intended: the pack passes, every Arthur fails.
- Budget edge: the lion misses by under 1%. Proposal: allow 10% over the limit as a warning, not a fix.
- Size readings use mesh bounds, which include the bind pose, so they are rough.
- Not covered yet (needs the Blender step): loose pieces, holes, flipped normals.

## Blender check — Arthur source (`Downloads\adventurer character 3d model.glb`, Tripo, 14 Nov)

| Check | Result | Status |
|---|---|---|
| Triangles | 191,104 (limit 40,000) | auto-fix |
| Debris | 16 tiny pieces under 10 faces | auto-fix (delete) |
| Pieces | 257 separate shells, largest 8,749 faces; 209 under 1,000 faces | info: reduce per piece so seams don't open |
| Open edges | 18,438 (edges of the separate clothing/hair shells) | info |
| Flipped normals / non-manifold / loose verts | 0 / 0 / 0 | pass |
| Height | 98 cm (target 160) | auto-fix (scale x1.63) |
| Materials | 1 | pass |
| Textures | 3 at 4096px (colour, normal, roughness-metal) | auto-fix (2048 for Henry's 3 GB card) |
| Armature | none | needs rig |

Verdict: **fixable, no reject.** The surface is clean; everything wrong is on the auto-fix list
or is the expected rigging step. The 4K colour and normal maps are a good source for baking
onto the reduced mesh.
