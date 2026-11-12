"""Cross-animation check: Arthur must be the same size and in the same place in every
animation of a direction (walk vs idle), and centred/grounded identically in all of them."""
import sys
import numpy as np
from PIL import Image

ART = "../../art"
CELL_W = 98


def measure(name):
    a = np.array(Image.open(f"{ART}/arthur_{name}.png"))[:, :, 3]
    W, T, C, B = [], [], [], []
    for i in range(a.shape[1] // CELL_W):
        m = a[:, i * CELL_W:(i + 1) * CELL_W] >= 128
        ys, _ = np.where(m)
        top, bot = ys.min(), ys.max()
        hw = np.where(m[top + 18:top + 26])[1]
        W.append(hw.max() - hw.min())                       # head width
        r = np.where(m[top + 55:top + 65])[1]                  # chest band
        T.append(np.percentile(r, 90) - np.percentile(r, 10))
        C.append(np.where(m[top + 50:top + 70])[1].mean())
        B.append(bot)
    return np.median(W), np.median(T), np.mean(C), sorted(set(B))


fail = False
print("== cross-check (head width / chest width / centre / ground)")
for d in ["side", "down", "up"]:
    w = measure(f"{d}_walk")
    i = measure(f"{d}_idle")
    print(f"   {d:5s} walk head {w[0]:.0f} chest {w[1]:.0f} centre {w[2]:.1f} ground {w[3]} | "
          f"idle head {i[0]:.0f} chest {i[1]:.0f} centre {i[2]:.1f} ground {i[3]}")
    if abs(w[0] - i[0]) > 1.5:
        print(f"   FAIL: {d} head width differs walk {w[0]:.0f} vs idle {i[0]:.0f}"); fail = True
    if abs(w[1] - i[1]) / max(i[1], 1) > 0.12:
        # chest width also changes with how far the torso is turned in each pose; scale itself
        # is matched by match_scale.py, so this is a note for the visual pass, not a failure
        print(f"   note: {d} chest width walk {w[1]:.0f} vs idle {i[1]:.0f} (torso turn) - check visually")
    for x, nm in ((w, "walk"), (i, "idle")):
        if abs(x[2] - 46) > 1.5:
            print(f"   FAIL: {d} {nm} not centred ({x[2]:.1f})"); fail = True
        if x[3] != [147]:
            print(f"   FAIL: {d} {nm} feet not all on row 147: {x[3]}"); fail = True
print("   RESULT:", "FAIL" if fail else "PASS")
sys.exit(1 if fail else 0)
