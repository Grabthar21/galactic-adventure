"""Find where the head is in an approved base drawing (no hand measuring per character).
The neck is the narrowest row between ~22% and ~45% of the body height; the shoulders
start where the width grows back to 1.5x the neck. The head is pasted from just above
the top of the hair down to the row before the shoulders (chin and neck included).
usage: python3 head_rows.py <base.png>   -> prints the JSON profile"""
import json
import sys
import numpy as np
from PIL import Image


def head_rows(path):
    a = np.array(Image.open(path).convert("RGBA"))[:, :, 3] > 40
    ys = np.where(a.any(1))[0]
    top, bot = int(ys.min()), int(ys.max())
    h = bot - top
    w = np.array([np.ptp(np.where(r)[0]) if r.any() else 0 for r in a])
    lo, hi = top + int(0.22 * h), top + int(0.45 * h)
    neck = lo + int(np.argmin(w[lo:hi]))
    shoulders = neck
    while shoulders < bot and w[shoulders] < 1.5 * w[neck]:
        shoulders += 1
    cut = shoulders - 1
    return {"HEAD_TOP": max(top - 3, 0), "BROW": top + int(0.3 * (cut - top)),
            "CHIN_CUT": cut, "FACE": [cut - 32, cut - 4], "HEIGHT": h}


if __name__ == "__main__":
    print(json.dumps(head_rows(sys.argv[1])))
