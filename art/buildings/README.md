# Farm buildings (Blender, 2026-11-11) — approved size templates

Made in Blender on Henry: `Documents/SpacePiece_Blender/space_piece_buildings.blend`.
The build scripts are text blocks inside that file (`sp_lib.py`, `build_house.py`, `build_farmhouse.py`, `build_barn.py`).
Re-run a script in Blender's Text Editor to rebuild a building after changing it.

- Look (softer, painterly pass): eased shadow/highlight transitions, subtle blotchy and brush-streak colour variation, soft corner darkening (AO), hand-drawn tapered and wobbly warm-brown outline (Freestyle), sun from the upper left. Roof shingle breaks are colour only, with no ink line.
- Rendered at 2x and downscaled with Lanczos for soft edges.
- Camera: orthographic, 30° above the horizon, front-on, at 71 px per metre (80% of Arthur's literal scale, because the user found 89 px/m too big next to him). The sprites use the same in-game scale as Arthur.
- farm_cottage.png: 580x610. Eave ≈ 1.9× hero height; door ≈ 1.1× hero height.
- farmhouse.png: 728x880. Eave ≈ 2.9× hero height; door ≈ 1.1× hero height.
- Scale check next to Arthur: docs/art/buildings_scale_check.png
- barn.png: 614x782, ground-centre origin (307, 599.8). Gambrel barn, 7.5 x 8 m, walls 4 m; double doors 3.1 m tall (a barn door, so larger than a house door).
- In-game placement and collision: scripts/world.gd `BUILDINGS`.
