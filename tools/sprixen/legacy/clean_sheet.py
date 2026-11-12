"""Apply lock_head.clean_body (white fringe / haze clean-up) to every frame of a sheet,
without replacing the head. usage: python3 clean_sheet.py <sheet.png> <out.png>"""
import sys
import numpy as np
from PIL import Image
from lock_head import clean_body, SRC

im = np.array(Image.open(sys.argv[1]).convert("RGBA")).astype(np.float32)
for i in range(im.shape[1] // SRC):
    im[:, i * SRC:(i + 1) * SRC] = clean_body(im[:, i * SRC:(i + 1) * SRC])
Image.fromarray(np.clip(im, 0, 255).astype(np.uint8)).save(sys.argv[2])
