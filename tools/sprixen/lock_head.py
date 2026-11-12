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

usage: python3 lock_head.py <sheet.png> <base_sprite.png> <out_sheet.png> [cycles=2] [hair_gain=0.8] [profile]
  profile = side|front|back (Arthur) or a JSON dict of head rows from head_rows.py
  cycles = how many up/down bobs one loop contains (2 for a walk, 1 for an idle)
"""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage

ALPHA_CUT = 60    # Sprixen leaves the far arm partly see-through: anything above this counts as solid

SRC = 256
# rows of each approved base sprite: head = HEAD_TOP..CHIN_CUT, FACE = rows used to find the head
PROFILES = {
    "side":  dict(HEAD_TOP=18, BROW=50, CHIN_CUT=88, FACE=(54, 84)),   # arthur_v1_base.png
    "front": dict(HEAD_TOP=14, BROW=46, CHIN_CUT=84, FACE=(48, 78)),   # arthur_front_base.png
    "back":  dict(HEAD_TOP=20, BROW=46, CHIN_CUT=84, FACE=(44, 78)),   # arthur_back_base.png (hair)
}


def profile(arg):
    """A named Arthur profile, or a JSON dict from head_rows.py (any character)."""
    import json
    if arg.strip().startswith("{"):
        d = json.loads(arg)
        d["FACE"] = tuple(d["FACE"])
        return d
    return PROFILES[arg]


HEAD_TOP, BROW, CHIN_CUT = 18, 50, 88
FACE = (54, 84)
FEATHER = 4                                # soft blend rows at the bottom of the pasted head


def rgba(im):
    return np.array(im).astype(np.float32)


def clean_body(f):
    """Undo Sprixen's background-removal leftovers on the body.
    - haze: cool (bluish/greenish) light pixels -> cleared
    - white fringe: pixels within 2px of the outside that are not fully opaque and are much
      lighter than the nearest fully opaque pixel were blended with the old white backdrop
      -> cleared; the rest of the soft edge takes the colour of the nearest opaque pixel
    - everything left above ALPHA_CUT becomes fully opaque (the far arm is partly see-through)
    """
    A = f[:, :, 3]
    rgb = f[:, :, :3]
    solid = A >= ALPHA_CUT
    solid &= ~((rgb.min(2) > 140) & (rgb[:, :, 0] < np.maximum(rgb[:, :, 1], rgb[:, :, 2]) - 2))
    interior = solid & (A >= 245)
    _, (iy, ix) = ndimage.distance_transform_edt(~interior, return_indices=True)
    near = rgb[iy, ix]
    lum = rgb.mean(2)
    lighter = lum - near.mean(2)
    outside_d = ndimage.distance_transform_edt(solid)
    soft = solid & ~interior & (outside_d <= 2.5)   # only the edge band; deeper see-through pixels keep their colour
    fringe = soft & (outside_d <= 2.5) & (lighter > 30)
    solid &= ~fringe
    soft &= ~fringe
    f = f.copy()
    f[soft, :3] = near[soft]
    f[:, :, 3] = np.where(solid, 255, 0)
    return f


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
    base = clean_body(rgba(Image.open(sys.argv[2]).convert("RGBA")))   # the approved head has Sprixen's white rim too
    out_path = sys.argv[3]
    cycles = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    hair_gain = float(sys.argv[5]) if len(sys.argv) > 5 else 0.8
    global HEAD_TOP, BROW, CHIN_CUT, FACE
    prof = profile(sys.argv[6] if len(sys.argv) > 6 else "side")
    HEAD_TOP, BROW, CHIN_CUT, FACE = prof["HEAD_TOP"], prof["BROW"], prof["CHIN_CUT"], prof["FACE"]
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
        f = clean_body(f)
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
        solid = f[:, :, 3] >= ALPHA_CUT
        f[:, :, 3] = np.where(solid, 255, 0)
        # holes just under the chin (see-through collar) -> fill from the approved sprite's collar
        holes, nh = ndimage.label(ndimage.binary_fill_holes(solid) & ~solid)
        bx, by = x0 - hx0, y0 - HEAD_TOP          # frame = base shifted by (bx, by)
        chin = y0 + hh
        for lab in range(1, nh + 1):
            ys, xs = np.where(holes == lab)
            if not (chin - 20 <= ys.mean() <= chin + 30) or len(ys) > 600:
                continue                           # only the collar; real gaps elsewhere stay open
            sy, sx = ys - by, xs - bx
            ok = (sy >= 0) & (sy < SRC) & (sx >= 0) & (sx < SRC)
            src_px = np.zeros((len(ys), 4), np.float32)
            src_px[ok] = base[sy[ok], sx[ok]]
            use = src_px[:, 3] > 128
            f[ys[use], xs[use], :3] = src_px[use, :3]
            f[ys[use], xs[use], 3] = 255
            # anything the base doesn't cover: nearest solid neighbour colour
            rest = ~use
            if rest.any():
                _, (iy, ix) = ndimage.distance_transform_edt(f[:, :, 3] < 255, return_indices=True)
                f[ys[rest], xs[rest], :3] = f[iy[ys[rest], xs[rest]], ix[ys[rest], xs[rest]], :3]
                f[ys[rest], xs[rest], 3] = 255
        out.paste(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)), (i * SRC, 0))
    out.save(out_path)
    print("head y raw", pos[:, 1].astype(int).tolist())
    print("head y bob", np.round(head_y, 1).tolist())
    print("head x - torso raw", np.round(pos[:, 0] - torso, 1).tolist())
    print("hair dy", np.round(hair_dy, 1).tolist())


if __name__ == "__main__":
    main()
