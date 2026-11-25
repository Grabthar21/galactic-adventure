"""Measure the size Arthur is drawn at in every frame of a roll and work out per-frame size
corrections, so every frame matches his run (FRAME_SCALES for build_walk_strip.py).

usage: python3 roll_scale.py <roll_strip.png> <direction> <raw_sheet.png> <start> <end> [--picks a,b,..] [--report]
  (the strip as built without corrections; the Sprixen sheet and the frame range it was cut from)

The yardstick is the head: a rigid ball, one size however he turns.

* Head width: the widest row of the head's silhouette (spiky hair tips trimmed off by an opening
  with a 7px disc), where the head is the top of the figure -- or the bottom when he is upside
  down. A reading counts only when it really is the head: the widest row has to sit well above
  the shoulders (the silhouette narrows again below it, at the neck, or the widest row is in the
  upper two thirds of the head band) and be within 15% of the run's head. On the run strips this reads the same head to +-3%: that is the accuracy.
* Side roll: he turns over in the picture plane, so the head can be followed through the whole
  somersault (head_track.py: frame to frame, every turn and size change). That track is tied to
  the head-width readings of the standing take-off and landing frames, which removes the small
  drift a long track gathers.
Frames with no trustworthy reading (head tucked away or hidden behind the body) take their
neighbours' size. Corrections closer to 1 than the measuring accuracy (2%) are not applied.
"""
import os
import sys
import subprocess
import numpy as np
import cv2
from PIL import Image
from scipy import ndimage
from cells import CELL_W

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "..", "..", "art")
DISC = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)).astype(bool)


def frames(p, w):
    a = np.array(Image.open(p).convert("RGBA"))
    return [a[:, i * w:(i + 1) * w] for i in range(a.shape[1] // w)]


def head_width(f, flip=False):
    """(width, trusted?) of the head ball at the top of the figure (bottom when flip)"""
    a = f[..., 3] >= 128
    if flip:
        a = a[::-1]
    a = ndimage.binary_opening(a, structure=DISC)
    ys = np.where(a.any(1))[0]
    if not len(ys):
        return np.nan, False
    t, b = ys.min(), ys.max()
    w = []
    for y in range(t, t + int(0.24 * (b - t)) + 1):
        xs = np.where(a[y])[0]
        if not len(xs):
            w.append(0)
            continue
        runs = np.split(xs, np.where(np.diff(xs) > 1)[0] + 1)
        w.append(max(len(r) for r in runs))
    w = np.array(w, float)
    k = int(np.argmax(w))
    # a ball: its widest row is well above the bottom of the band, and it narrows below (the neck)
    below = w[k + 1:]
    ball = k < 0.75 * len(w) and ((len(below) > 2 and below.min() < 0.88 * w[k]) or k < 0.65 * len(w))
    return float(w[k]), bool(ball)


def run_head_width(direction):
    vals = [head_width(f) for f in frames(os.path.join(ART, f"arthur_{direction}_run.png"), CELL_W)]
    return float(np.median([v for v, ok in vals if ok] or [v for v, _ in vals]))


def width_readings(strip, direction):
    ref = run_head_width(direction)
    out = []
    for f in frames(strip, CELL_W):
        best = (np.nan, "-")
        for flip in (False, True):
            v, ok = head_width(f, flip)
            if ok and abs(v / ref - 1) <= 0.15:
                best = (v / ref, "upside down" if flip else "upright")
                break
        out.append(best)
    return out


def side_track(raw, s, e, picks):
    res = subprocess.run([sys.executable, os.path.join(HERE, "head_track.py"), raw, str(s), str(e)],
                         capture_output=True, text=True, check=True)
    tr = np.array([float(v) for v in res.stdout.strip().split(",")])
    return tr[np.array(picks) - s]


def measure(strip, direction, raw, s, e, picks=None):
    n = len(frames(strip, CELL_W))
    picks = np.array(picks) if picks is not None else np.round(np.linspace(s, e, n)).astype(int)
    wr = width_readings(strip, direction)
    rows = [dict(size=v, how=f"head width, {how}" if v == v else "no clear view of the head") for v, how in wr]
    if direction == "side":
        tr = side_track(raw, s, e, picks)
        # tie the track to the standing ends (head-width readings of the first/last 2 frames)
        ends = [(i, wr[i][0] / tr[i]) for i in (0, 1, n - 2, n - 1) if wr[i][0] == wr[i][0]]
        if len(ends) >= 2:
            ii = np.array([i for i, _ in ends], float)
            kk = np.array([k for _, k in ends])
            A = np.vstack([np.ones_like(ii), ii]).T
            c0, c1 = np.linalg.lstsq(A, kk, rcond=None)[0]       # drift: a straight line in frame index
            for i in range(n):
                rows[i] = dict(size=float(tr[i] * (c0 + c1 * i)), how="head followed through the turn")
    return rows


def corrections(rows):
    sz = np.array([r["size"] for r in rows], float)
    idx = np.arange(len(sz))
    ok = ~np.isnan(sz)
    if not ok.any():
        return np.ones(len(sz))
    full = np.interp(idx, idx[ok], sz[ok])
    # a 3-frame median: one odd reading is the ruler's error, not the drawing
    sm = np.array([np.median(full[max(i - 1, 0):i + 2]) for i in idx])
    m = 1.0 / sm
    m[np.abs(m - 1) < 0.02] = 1.0
    return np.clip(m, 0.85, 1.18)


if __name__ == "__main__":
    if sys.argv[1] == "--check":
        # after the corrections: every trusted head reading within 4% of the run's head
        # (2 px on a ~56 px head; the ruler itself reads the run to +-3%)
        strip, direction = sys.argv[2], sys.argv[3]
        wr = width_readings(strip, direction)
        bad = [(i, v) for i, (v, _) in enumerate(wr) if v == v and abs(v - 1) > 0.04]
        print(f"== size {os.path.basename(strip)}: head vs run " +
              " ".join(f"{v:.2f}" if v == v else "-" for v, _ in wr))
        for i, v in bad:
            print(f"   FAIL: frame {i}: head {v:.3f}x the run's (more than 4% off)")
        print("   RESULT: " + ("FAIL" if bad else "PASS"))
        sys.exit(1 if bad else 0)
    strip, direction, raw, s, e = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
    picks = [int(v) for v in sys.argv[sys.argv.index("--picks") + 1].split(",")] if "--picks" in sys.argv else None
    rows = measure(strip, direction, raw, s, e, picks)
    m = corrections(rows)
    if "--report" in sys.argv:
        for i, r in enumerate(rows):
            print(f"  frame {i:2d}: head {r['size']:.3f} of the run's ({r['how']})  -> x{m[i]:.3f}")
    print(",".join(f"{v:.4f}" for v in m))
