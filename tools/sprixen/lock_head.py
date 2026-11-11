"""Replace the head in every frame of a Sprixen sheet with the approved head from the
base sprite, so the face never changes between frames, and give the hair a soft,
lagging bounce.

Per frame:
  1. find where the frame's head is (template match of the approved face),
  2. lock the head's x to the torso and smooth its y into a clean two-step bob
     (first two harmonics of the measured bob over the loop),
  3. erase the frame's own head above the collar and paste the approved head there,
  4. warp the hair rows by a lagged copy of the bob (hair trails the head by ~2
     frames and settles), fading to zero at the brow so the face stays rigid.

usage: python3 lock_head.py <sheet.png> <base_sprite.png> <out_sheet.png> [cycles=2] [hair_gain=0.8]
  cycles = how many up/down bobs one loop contains (2 for a walk, 1 for an idle)
"""
import sys
import numpy as np
from PIL import Image

SRC = 256
# rows of the approved base sprite (arthur_v1_base.png)
HEAD_TOP, BROW, CHIN_CUT = 18, 50, 88     # head = rows HEAD_TOP..CHIN_CUT
FACE = (54, 84)                            # rows used to find the head in a frame
FEATHER = 4                                # soft blend rows at the bottom of the pasted head


def rgba(im):
    return np.array(im).astype(np.float32)


def find_head(frame, face, fx0, search=28):
    """Best (dx, dy) placing the base face into the frame."""
    fa = face[:, :, 3:4] / 255.0
    best, arg = 1e18, (0, 0)
    h, w = face.shape[:2]
    for dy in range(-search, search + 1):
        for dx in range(-search, search + 1):
            y0, x0 = FACE[0] + dy, fx0 + dx
            if y0 < 0 or x0 < 0 or y0 + h > SRC or x0 + w > SRC:
                continue
            win = frame[y0:y0 + h, x0:x0 + w]
            wa = win[:, :, 3:4] / 255.0
            d = ((face[:, :, :3] * fa - win[:, :, :3] * wa) ** 2).sum() + 300.0 * ((fa - wa) ** 2).sum()
            if d < best:
                best, arg = d, (dx, dy)
    return arg


def harmonics(v, cycles):
    """Keep the mean and the first two harmonics of the bob frequency."""
    n = len(v)
    t = np.arange(n) * 2 * np.pi / n
    out = np.full(n, v.mean())
    for k in (cycles, 2 * cycles):
        a = 2 / n * (v * np.cos(k * t)).sum()
        b = 2 / n * (v * np.sin(k * t)).sum()
        out += a * np.cos(k * t) + b * np.sin(k * t)
    return out


def main():
    sheet = Image.open(sys.argv[1]).convert("RGBA")
    base = rgba(Image.open(sys.argv[2]).convert("RGBA"))
    out_path = sys.argv[3]
    cycles = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    hair_gain = float(sys.argv[5]) if len(sys.argv) > 5 else 0.8
    n = sheet.width // SRC
    frames = [rgba(sheet.crop((i * SRC, 0, (i + 1) * SRC, SRC))) for i in range(n)]

    # approved head + face template
    head = base[HEAD_TOP:CHIN_CUT].copy()
    cols = np.where(head[:, :, 3].max(0) > 40)[0]
    hx0, hx1 = cols.min(), cols.max() + 1
    head = head[:, hx0:hx1]
    face = base[FACE[0]:FACE[1], hx0:hx1]
    for r in range(FEATHER):                       # soft bottom edge into the collar
        head[-FEATHER + r, :, 3] *= 1 - (r + 1) / (FEATHER + 1)

    # locate heads and torsos
    pos, torso = [], []
    for f in frames:
        pos.append(find_head(f, face, hx0))
        a = f[:, :, 3] > 40
        ys, xs = np.where(a)
        top = ys.min()
        tys, txs = np.where(a[top + 75:top + 105])
        torso.append(txs.mean())
    pos = np.array(pos, float)
    torso = np.array(torso)
    off_x = np.median(pos[:, 0] - torso)
    head_x = torso + off_x                          # head rides on the torso, no wobble
    head_y = harmonics(pos[:, 1], cycles)           # clean bob
    bob = head_y - head_y.mean()
    lag = np.roll(bob, 2)                           # hair trails the head by ~2 frames
    hair_dy = hair_gain * (lag - bob)               # hair lifts as the head drops, settles after

    out = Image.new("RGBA", (SRC * n, SRC), (0, 0, 0, 0))
    hh, hw = head.shape[:2]
    for i, f in enumerate(frames):
        f = f.copy()
        x0 = int(round(head_x[i])) + hx0
        y0 = int(round(head_y[i])) + HEAD_TOP
        # erase the frame's own head: everything above the collar line
        cut = y0 + hh - FEATHER
        f[:max(cut, 0)] = 0
        # hair warp: shift each hair row vertically by hair_dy * weight (1 at top -> 0 at brow)
        h = head.copy()
        brow_r = BROW - HEAD_TOP
        warped = h.copy()
        for r in range(brow_r):
            wgt = (1 - r / brow_r) ** 1.5
            src_r = r - hair_dy[i] * wgt
            r0 = int(np.floor(src_r)); fr = src_r - r0
            if 0 <= r0 < hh - 1:
                warped[r] = h[r0] * (1 - fr) + h[r0 + 1] * fr
            else:
                warped[r] = 0
        # paste approved head over the erased area
        ya, yb = max(y0, 0), min(y0 + hh, SRC)
        xa, xb = max(x0, 0), min(x0 + hw, SRC)
        src = warped[ya - y0:yb - y0, xa - x0:xb - x0]
        dst = f[ya:yb, xa:xb]
        sa = src[:, :, 3:4] / 255.0
        da = dst[:, :, 3:4] / 255.0
        oa = sa + da * (1 - sa)
        rgb = (src[:, :, :3] * sa + dst[:, :, :3] * da * (1 - sa)) / np.maximum(oa, 1e-6)
        f[ya:yb, xa:xb, :3] = rgb
        f[ya:yb, xa:xb, 3:4] = oa * 255
        out.paste(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)), (i * SRC, 0))
    out.save(out_path)
    print("head y raw", pos[:, 1].astype(int).tolist())
    print("head y bob", np.round(head_y, 1).tolist())
    print("head x - torso raw", np.round(pos[:, 0] - torso, 1).tolist())
    print("hair dy", np.round(hair_dy, 1).tolist())


if __name__ == "__main__":
    main()
