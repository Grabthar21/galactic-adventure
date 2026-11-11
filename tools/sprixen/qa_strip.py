"""Frame-by-frame quality check for an in-game animation strip (98x148 cells).

Checks every frame for:
  halo     edge pixels much lighter than the colour just inside them (white fringe)
  haze     cool / greenish light pixels (background-removal leftovers)
  holes    see-through pockets fully enclosed by the character
  islands  stray specks not connected to the body
  ground   feet not touching the cell's bottom row (floating / sinking)
  size     character height vs the target and vs the other frames
  drift    side-to-side wobble of the body centre
  head     head region changing shape between frames (face lock check)
  pops     a frame-to-frame change much larger than the rest (jumps), incl. the loop seam
and writes a 3x contact sheet on magenta + green for a visual pass.

usage: python3 qa_strip.py <strip.png> <name> [target_height=133] [walk|idle]
exit code 1 if any check fails.
"""
import sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

CELL_W, CELL_H, FOOT_Y = 98, 148, 147


def frames_of(path):
    im = np.array(Image.open(path).convert("RGBA")).astype(np.int32)
    n = im.shape[1] // CELL_W
    return [im[:, i * CELL_W:(i + 1) * CELL_W] for i in range(n)]


def main():
    path, name = sys.argv[1], sys.argv[2]
    target = float(sys.argv[3]) if len(sys.argv) > 3 else 133.0
    kind = sys.argv[4] if len(sys.argv) > 4 else "walk"
    fr = frames_of(path)
    n = len(fr)
    fails, notes = [], []
    heights, centres, bottoms, heads, masks = [], [], [], [], []
    for i, f in enumerate(fr):
        a = f[:, :, 3]
        m = a > 0
        solid = a >= 128
        ys, xs = np.where(m)
        top, bot = ys.min(), ys.max()
        heights.append(bot - top)
        bottoms.append(bot)
        t0, t1 = top + int(0.40 * (bot - top)), top + int(0.55 * (bot - top))   # torso band
        centres.append(np.where(m[t0:t1])[1].mean())
        masks.append(solid)
        # head silhouette: top 28% of the body, aligned on its own top row
        hh = int(0.28 * (bot - top))
        head = np.zeros((hh, CELL_W), bool)
        head[:] = solid[top:top + hh]
        heads.append(head)

        rgb = f[:, :, :3]
        lum = rgb.mean(2)
        # halo: outer edge pixels that are much lighter than the solid pixel 2px inside
        outside = ~m
        edge = m & ndimage.binary_dilation(outside)
        inner = solid & ~ndimage.binary_dilation(outside, iterations=2)
        if inner.any():
            _, (iy, ix) = ndimage.distance_transform_edt(~inner, return_indices=True)
            halo = edge & (lum - lum[iy, ix] > 45) & (lum > 170)
            h = int(halo.sum())
            if h > 6:
                fails.append(f"frame {i}: {h} white-fringe edge pixels")
            elif h:
                notes.append(f"frame {i}: {h} light edge px (ok)")
        haze = m & ndimage.binary_dilation(outside, iterations=3) & (rgb.min(2) > 140) & (rgb[:, :, 0] < np.maximum(rgb[:, :, 1], rgb[:, :, 2]) - 6)
        if haze.sum() > 3:
            fails.append(f"frame {i}: {int(haze.sum())} cool/greenish haze px")
        holes, nh = ndimage.label(ndimage.binary_fill_holes(solid) & ~solid)
        for k in range(1, nh + 1):
            sz = int((holes == k).sum())
            hy, hx = np.where(holes == k)
            if sz >= 3 and hy.mean() < top + 0.55 * (bot - top):
                fails.append(f"frame {i}: see-through hole {sz}px at ({int(hx.mean())},{int(hy.mean())})")
        lab, nl = ndimage.label(m)
        if nl > 1:
            sizes = ndimage.sum(m, lab, range(1, nl + 1))
            main = sizes.max()
            specks = [int(s) for s in sizes if s < main]
            if specks:
                fails.append(f"frame {i}: {len(specks)} stray speck(s), largest {max(specks)}px")
        if bot != FOOT_Y:
            fails.append(f"frame {i}: feet at row {bot}, not on the ground row {FOOT_Y}")

    H = np.array(heights, float)
    C = np.array(centres)
    med_h = float(np.median(H))
    if abs(med_h - target) > 3:
        fails.append(f"median height {med_h:.0f}px vs target {target:.0f}px")
    if kind == "idle" and H.max() - H.min() > 3:
        fails.append(f"idle height varies {H.min():.0f}-{H.max():.0f}px")
    if kind == "walk" and H.max() - H.min() > 8:
        fails.append(f"walk height varies {H.min():.0f}-{H.max():.0f}px")
    jumps = np.abs(np.diff(np.r_[C, C[0]]))
    if jumps.max() > 2.5:
        fails.append(f"body centre jumps {jumps.max():.1f}px between frames {int(jumps.argmax())}->{(int(jumps.argmax()) + 1) % n}")
    # head shape stability (IoU vs median frame)
    ref = heads[n // 2]
    for i, h in enumerate(heads):
        k = min(len(h), len(ref))
        inter = (h[:k] & ref[:k]).sum(); uni = (h[:k] | ref[:k]).sum()
        iou = inter / max(uni, 1)
        if iou < 0.80:
            fails.append(f"frame {i}: head shape differs (IoU {iou:.2f})")
    # pops: silhouette change between consecutive frames, including the loop seam
    d = np.array([(masks[i] ^ masks[(i + 1) % n]).sum() for i in range(n)], float)
    med = np.median(d)
    for i, v in enumerate(d):
        if v > max(2.6 * med, med + 120):
            fails.append(f"pop: frame {i}->{(i + 1) % n} changes {int(v)}px (typical {int(med)})")

    print(f"== {name}: {n} frames, height {H.min():.0f}-{H.max():.0f} (median {med_h:.0f}, target {target:.0f}), "
          f"centre range {C.min():.1f}-{C.max():.1f}, max centre step {jumps.max():.1f}, "
          f"silhouette change median {med:.0f}px max {d.max():.0f}px")
    for x in notes[:6]:
        print("   note:", x)
    for x in fails:
        print("   FAIL:", x)
    print("   RESULT:", "PASS" if not fails else f"{len(fails)} issue(s)")

    # contact sheet
    cols = min(n, 10)
    rows = (n + cols - 1) // cols
    S = 3
    sheet = Image.new("RGBA", (cols * CELL_W * S, rows * CELL_H * S * 2), (0, 0, 0, 255))
    strip = Image.open(path).convert("RGBA")
    for bi, bg in enumerate([(200, 0, 200, 255), (110, 165, 85, 255)]):
        for i in range(n):
            cell = strip.crop((i * CELL_W, 0, (i + 1) * CELL_W, CELL_H)).resize((CELL_W * S, CELL_H * S), Image.NEAREST)
            tile = Image.new("RGBA", cell.size, bg)
            tile.alpha_composite(cell)
            ImageDraw.Draw(tile).text((4, 4), str(i), fill=(255, 255, 255, 255))
            sheet.paste(tile, ((i % cols) * CELL_W * S, (bi * rows + i // cols) * CELL_H * S))
    out = f"/tmp/qa_{name}.png"
    sheet.save(out)
    print("   contact sheet:", out)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
