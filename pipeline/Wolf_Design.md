# Wolf — first enemy (3D, v1 design, 28 Nov 2026)

The farm wolves from the opening (Option Omega: the wolf fight before the wolf-pup choice).
This brings the 2D prototype's wolf (`scripts/wolf.gd`, playtested in the web build) into
Unreal with the same behaviour, so the fight feels the same and is ready before the real
model exists.

## Look (to be decided: see "Model" below)
- Art Style Guide §9: stylised, slightly chunky, expressive, readable eyes; predators sharper
  in shape but **not gory**. Same colour and material rules as people (matte, painted).
- Size against Arthur (160 cm): shoulder about 75 cm (just under his waist-to-chest), nose to
  tail about 1.4 m. Grey with a lighter belly (the 2D wolf's colours).
- **Stand-in now:** grey blocks (body, chest, head, snout, ears, tail, four legs) under one
  `Visual` component. It crouches and turns red to warn, flashes white when hit, goes dark
  when defeated. The real model replaces only the `Visual` parts.

## Behaviour (same as 2D)
| State | What it does | 3D numbers |
|---|---|---|
| idle | waits | notices Arthur within **18 m** |
| approach | runs at Arthur, a little faster than his run | 540 cm/s (Arthur 500) |
| circle | circles him, keeping its distance; switches sides after each attack | radius 2.8 m, ~46% of run speed; back to approach past 4.9 m |
| telegraph | stops, faces him, crouches, turns red: **the "roll now" moment** | 0.65 s, after at least 0.9 s of circling |
| lunge | short leap at him; one bite if it reaches him | 11.8 m/s forward + small hop (~3.3 m); bite reach 1 m; 1 damage |
| recover | stands, open to hits | 0.8 s |
| stagger | knocked back when hit | 0.35 s, 6.5 m/s push |
| dying | goes dark, removed | 0.7 s |

- **Attack tokens:** at most **2 wolves** warn/lunge at the same time; the rest keep circling.
  The count lives on Arthur (`BP_Arthur.AttackersNow`), like the 2D version.
- **Health:** 4. Sword damage is 1 / 1 / 2 for the three combo hits, so one full combo
  defeats a wolf, or two quick first hits plus a finisher.
- **Lock-on:** wolves are tagged `Lockable` and `Enemy`.

## Arthur's side (in `Arthur_Combat_Nodes.txt`)
- Each combo swing hits once, in its hit window, the nearest `Enemy` within 2.3 m and in
  front of him. Windows (montage seconds) are first guesses to tune after a test:
  hit 1 0.20–0.42, hit 2 0.12–0.32, finisher 0.85–1.25.
- Bites: 6 bites restart the level (placeholder until there's a health display and a
  hit-reaction animation). A small knockback and an on-screen "Arthur was bitten!" for now.
- **Dodge = no damage** in the first ~0.46 s of the roll (matches the 2D roll's 0.30 s
  window scaled to the longer 3D roll).

## Files
| File | What |
|---|---|
| `pipeline/scripts/ue_wolf_setup.py` | makes `/Game/Creatures/Wolf/BP_Wolf` (stand-in parts, movement, AI possession, tags, variables), adds `AttackersNow` to BP_Arthur, places 3 wolves at the farm's wolf spawns |
| `pipeline/scripts/ue_paste/Wolf_AI_Nodes.txt` | the wolf's brain for BP_Wolf's Event Graph (128 nodes), from `gen_wolf_nodes.py` |
| `pipeline/scripts/ue_arthur_combat_setup.py` | BP_Arthur variables + graph check + lock-on practice posts |
| `pipeline/scripts/ue_paste/Arthur_Combat_Nodes.txt` | lock-on + sword hits + taking hits for BP_Arthur (124 nodes), from `gen_arthur_combat_nodes.py` (replaces the lock-on-only file) |
| `pipeline/scripts/ue_paste/lint_graph.py` | checks a generated graph: every action reachable, every input wired or set |

All numbers sit at the top of the two generators; change and re-run to rebuild the paste files.

## Henry steps (by remote)
1. Run `ue_arthur_combat_setup.py`, then `ue_wolf_setup.py`.
2. Paste `Arthur_Combat_Nodes.txt` into BP_Arthur's Event Graph; compile, save.
3. Open BP_Wolf, paste `Wolf_AI_Nodes.txt`; compile, save.
4. Play `L_Farm_Blockout`, walk to the wolf corner (north-east), fight. Tune.

## Model (decision for the family)
- **A. Build it in Blender myself (free).** Stylised low-detail wolf to the style guide,
  rigged to the quadruped chain template, animated with the lion clips we already have
  (walk, run; checking what attack/hit/death clips the lion has). Most control over the look;
  slower; first look shown for approval before rigging.
- **B. Generate with Sprixen 3D or Tripo (uses credits).** Fast first shape, then the same
  cleanup Arthur needed (size, triangle budget, rig). Credits only with your OK.
- **C. A free wolf from Fab.** Usually realistic, so it may fight the Zelda look; licence check.

## Canon notes
- In the 2D opening Arthur fights the wolves with a **metal rod** (Father's Sword comes
  later). The 3D test uses his sword; a rod is a mesh swap when the opening is built in 3D.
- Wolf-pup choice and "the pup returns" (proposed beat) come after this fight; the pup can be
  a scaled-down copy of the wolf model.
