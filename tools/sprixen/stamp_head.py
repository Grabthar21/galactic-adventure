"""Make the face pixel-identical in every frame of a finished strip.

lock_head.py pastes the approved head on every 256px frame, but each frame's head sits at a
slightly different sub-pixel spot, so after the downscale to 98x148 the eyes, brows and mouth
come out a little different frame to frame (the face "shimmers" at game size). This step
takes the head from ONE finished reference cell (idle frame 0 of the same direction), finds
where each frame's head is to the nearest whole pixel, and re-stamps the reference head there.
Every row above the cut line (top of hair down to just above the shoulders) is replaced, so no
part of the old head is left behind. Walk and idle then show exactly the same face.

usage: python3 stamp_head.py <strip.png> <ref_strip.png> <head_px> [ref_frame=0] [out.png]
  head_px = rows from the top of the hair down to the shoulders (build_char.py's head_px)
"""
import sys
import numpy as np
from PIL import Image

from cells import CELL_W as CW, CELL_H as CH
SEARCH = 7          # +-px searched around the reference position


def cells(path):
    a = np.array(Image.open(path).convert("RGBA")).astype(np.float32)
    return a, [a[:, i * CW:(i + 1) * CW] for i in range(a.shape[1] // CW)]


def stamp(strip_path, ref_path, head_px, ref_frame=0, out=None):
    _, rc = cells(ref_path)
    ref = rc[ref_frame]
    ys = np.where((ref[..., 3] > 128).any(1))[0]
    top = int(ys.min())
    cut = top + head_px - 2                       # stop 2 rows above the shoulders
    head = ref[:cut].copy()                        # rows 0..cut-1 of the reference cell
    hm = head[..., 3] > 128
    full, fr = cells(strip_path)

    def err(f, dx, dy):
        y0, y1 = max(0, dy), cut - 4 + dy
        if y1 > CH or y1 <= y0:
            return 1e9
        reg = np.roll(f, -dx, axis=1)[y0:y1]
        h = head[y0 - dy:y1 - dy]
        m = (h[..., 3] > 128) | (reg[..., 3] > 128)
        return np.abs(reg[..., :3] - h[..., :3])[m].mean() + 0.5 * np.abs(reg[..., 3] - h[..., 3]).mean()

    # 1. best whole-pixel spot per frame, refined to a sub-pixel estimate (parabola through
    #    the error at dy-1, dy, dy+1), 2. smoothed round the loop, 3. rounded with no jump
    #    bigger than 1px between neighbouring frames -> the head steps, never flickers
    est = []
    for f in fr:
        E = {(dx, dy): err(f, dx, dy) for dy in range(-SEARCH, SEARCH + 1) for dx in range(-SEARCH, SEARCH + 1)}
        dx, dy = min(E, key=E.get)
        sub = []
        for a, b, c in ((E.get((dx - 1, dy)), E[(dx, dy)], E.get((dx + 1, dy))),
                        (E.get((dx, dy - 1)), E[(dx, dy)], E.get((dx, dy + 1)))):
            den = (a - 2 * b + c) if a is not None and c is not None else 0
            sub.append(0.5 * (a - c) / den if den > 0 else 0.0)
        est.append((dx + sub[0], dy + sub[1]))
    est = np.array(est)
    n = len(est)
    sm = (np.roll(est, 1, 0) + est + np.roll(est, -1, 0)) / 3 if n >= 3 else est
    offs = []
    for i in range(n):
        o = np.round(sm[i]).astype(int)
        if offs:
            o = np.clip(o, np.array(offs[-1]) - 1, np.array(offs[-1]) + 1)
        offs.append((int(o[0]), int(o[1])))
    for i, f in enumerate(fr):
        dx, dy = offs[i]
        new = f.copy()
        c = cut + dy                               # cut row in this frame
        new[:max(c, 0)] = 0
        sh = np.roll(head, dx, axis=1)
        src0 = max(0, -dy)
        new[max(dy, 0):max(c, 0)] = sh[src0:src0 + max(c, 0) - max(dy, 0)]
        # body pixels just above the cut (shoulder tips) stay where the head is empty
        keep = (f[:max(c, 0), :, 3] > 128) & (new[:max(c, 0), :, 3] <= 8) & (np.arange(max(c, 0))[:, None] >= c - 3)
        new[:max(c, 0)][keep] = f[:max(c, 0)][keep]
        full[:, i * CW:(i + 1) * CW] = new
    from resample import fill_pinholes
    full = np.array(fill_pinholes(Image.fromarray(np.clip(full, 0, 255).astype(np.uint8)))).astype(np.float32)
    Image.fromarray(np.clip(full, 0, 255).astype(np.uint8)).save(out or strip_path)
    return offs


if __name__ == "__main__":
    a = sys.argv
    offs = stamp(a[1], a[2], int(a[3]), int(a[4]) if len(a) > 4 else 0, a[5] if len(a) > 5 else None)
    print(f"{a[1]}: head stamped on {len(offs)} frames; offsets x {min(o[0] for o in offs)}..{max(o[0] for o in offs)}"
          f", y {min(o[1] for o in offs)}..{max(o[1] for o in offs)}")
