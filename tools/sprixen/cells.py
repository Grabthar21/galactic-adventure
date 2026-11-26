"""In-game cell size shared by every strip script. CELL_SCALE (env, default 1) multiplies it:
1 = the original 98x148 cells (pixel look), 1.5 = 147x222 cells for the smooth, Sprixen-style look
(the game then draws the sprite at half the scale with smooth filtering)."""
import os

K = float(os.environ.get("CELL_SCALE", "1"))
CELL_W, CELL_H = round(98 * K), round(148 * K)
FOOT_Y = CELL_H - 1
CENTER_X = round(46 * K)
# a wider cell (env CELL_W) for strips whose poses reach further sideways (a run's stride): the
# body stays the same distance left of the cell's middle, so it lines up when the game swaps strips
if os.environ.get("CELL_W"):
    _w = int(os.environ["CELL_W"])
    CENTER_X = round(CENTER_X + (_w - CELL_W) / 2)
    CELL_W = _w
REINK = os.environ.get("REINK", "1") != "0"   # darken the outline (crisp pixel look); off for smooth
