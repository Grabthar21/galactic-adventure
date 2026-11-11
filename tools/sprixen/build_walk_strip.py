"""Turn the Sprixen walk sheet (16 x 256px frames) into art/<hero>_side_walk.png.

Sprixen's in-place walk wobbles: a couple of frames sit ~19px off-centre and the
height jumps by up to 10px between neighbours. Each frame is therefore
  1. shifted so the torso centre is fixed (no side-to-side jitter),
  2. uniformly rescaled about the feet so its height follows a smoothed
     (circular 3-tap average) curve, keeping the bob but losing the pops,
then scaled to in-game height into 98x148 cells, feet on the bottom row.
It also prints the ground speed (px/s at the game's sprite scale) that keeps the
planted foot from sliding.

usage: python3 build_walk_strip.py <sheet.png> <out.png> [target_height=133] [fps=20] [frame list e.g. 0,1,2]
"""
import sys
import numpy as np
from PIL import Image

SRC = 256
CELL_W, CELL_H = 98, 148
FOOT_Y = 147
CENTER_X = 46
GAME_SCALE = 0.75   # player.gd SCALE


def alpha(f):
    return np.array(f)[:, :, 3] > 40


def main():
    sheet = Image.open(sys.argv[1]).convert("RGBA")
    out = sys.argv[2]
    target_h = float(sys.argv[3]) if len(sys.argv) > 3 else 133.0
    fps = float(sys.argv[4]) if len(sys.argv) > 4 else 20.0
    n_all = sheet.width // SRC
    order = [int(x) for x in sys.argv[5].split(",")] if len(sys.argv) > 5 else list(range(n_all))
    frames = [sheet.crop((i * SRC, 0, (i + 1) * SRC, SRC)) for i in order]
    info = []
    for f in frames:
        a = alpha(f)
        ys, xs = np.where(a)
        top, bot = ys.min(), ys.max()
        tys, txs = np.where(a[top + 75:top + 105])
        info.append(dict(top=top, bot=bot, h=bot - top, torso=txs.mean()))
    hs = np.array([d["h"] for d in info], float)
    n = len(frames)
    smooth = np.array([(hs[i - 1] + hs[i] + hs[(i + 1) % n]) / 3 for i in range(n)])
    base = target_h / float(np.median(hs))
    strip = Image.new("RGBA", (CELL_W * n, CELL_H), (0, 0, 0, 0))
    foot_x = []   # x of the lowest (planted) foot, in game cell px, per frame
    for i, (f, d) in enumerate(zip(frames, info)):
        s = base * smooth[i] / d["h"]
        w2, h2 = round(SRC * s), round(SRC * s)
        big = f.resize((w2 * 2, h2 * 2), Image.LANCZOS).resize((w2, h2), Image.LANCZOS)
        # place: torso centre -> CENTER_X, feet bottom -> FOOT_Y
        px = round(i * CELL_W + CENTER_X - d["torso"] * s)
        py = round(FOOT_Y - d["bot"] * s)
        cell = Image.new("RGBA", (CELL_W * n, CELL_H), (0, 0, 0, 0))
        cell.alpha_composite(big, (max(px, 0), max(py, 0)),
                             (max(-px, 0), max(-py, 0)))
        # clip to own cell
        mask = Image.new("L", cell.size, 0)
        mask.paste(255, (i * CELL_W, 0, (i + 1) * CELL_W, CELL_H))
        clipped = Image.new("RGBA", cell.size, (0, 0, 0, 0))
        clipped.paste(cell, (0, 0), mask)
        strip.alpha_composite(clipped)
        a = alpha(f)
        ys, xs = np.where(a)
        low = xs[ys > d["bot"] - 4]
        foot_x.append((low.min() - d["torso"]) * s)   # toe-side unused; heel edge
    strip.save(out)
    # planted-foot slide per frame (backwards = positive speed)
    dx = [foot_x[i] - foot_x[(i + 1) % n] for i in range(n)]
    good = [v for v in dx if 0 < v < 15]
    v = float(np.median(good)) * fps * GAME_SCALE if good else 0
    print(f"{n} frames {order} -> {out}; median height {np.median(hs):.0f}px; "
          f"foot slide/frame {np.round(dx,1).tolist()}; suggested speed {v:.0f} px/s at {fps:.0f} fps")


if __name__ == "__main__":
    main()
