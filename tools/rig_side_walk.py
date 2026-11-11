"""Build an 8-frame side walk cycle from ONE good side pose by cutting it into
parts (body, near/far leg, near/far arm) and rotating them around hip/shoulder pivots.
Coordinates are in the cropped source frame (side0.png, 1:1 with the original sheet)."""
import numpy as np, math, json, sys
from scipy import ndimage
from PIL import Image, ImageDraw, ImageEnhance

cfg = dict(
    src='side0.png',
    hip_far=(88, 182), hip_near=(110, 182),
    shoulder_far=(68, 148), shoulder_near=(128, 148),   # elbow pivots (forearm + glove swing)
    leg_top=172, crotch=(97, 199),
    far_leg_angle=-36.0, near_leg_angle=21.0,   # natural angle of each leg graphic (deg, + = forward)
    arm_swing=9.0, lift=0.10, frames=8,
)
if len(sys.argv) > 1:
    cfg.update(json.load(open(sys.argv[1])))

src = Image.open(cfg['src']).convert('RGBA')
A = np.array(src)
A[A[:, :, 3] < 24] = 0   # drop the near-invisible fringe pixels in the source sheet
H, W = A.shape[:2]
yy, xx = np.mgrid[0:H, 0:W]
opaque = A[:, :, 3] > 0

def poly_mask(pts):
    m = Image.new('L', (W, H), 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    return np.array(m) > 0

cx, cy = cfg['crotch']
lt = cfg['leg_top']
from scipy import ndimage
pants_col = (A[:, :, 2].astype(int) > A[:, :, 0].astype(int) + 15) & (A[:, :, 2] > 50)
far_arm = opaque & poly_mask([(30, 146), (78, 146), (74, 160), (73, 200), (30, 200)]) & (yy < cy) & ~pants_col
near_arm = opaque & poly_mask([(124, 146), (180, 146), (180, 200), (130, 200), (129, 160)]) & (yy < cy) & ~pants_col
# drop stray specks so only the forearm + glove move
for m in (far_arm, near_arm):
    lab_a, na = ndimage.label(m & (A[:, :, 3] > 160) & ~(A[:, :, :3].max(axis=2) < 45))
    if na > 1:
        sz = ndimage.sum(np.ones_like(lab_a), lab_a, range(1, na + 1))
        main = lab_a == (np.argmax(sz) + 1)
        m &= ndimage.binary_dilation(main, iterations=2)
# legs: separate components below the crotch, split by x in the hip band above it
strong = (A[:, :, 3] > 160) & (yy >= cy)
lab, n = ndimage.label(strong)
sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
big = np.argsort(sizes)[::-1][:2] + 1
cents = [np.nonzero(lab == k)[1].mean() for k in big]
far_id, near_id = (big[0], big[1]) if cents[0] < cents[1] else (big[1], big[0])
hip_band = opaque & (yy >= lt) & (yy < cy) & (xx > 74) & (xx < 129) & ~far_arm & ~near_arm
# give every soft edge pixel below the crotch to the nearest strong leg pixel
keep = np.isin(lab, [far_id, near_id])
_, (iy, ix) = ndimage.distance_transform_edt(~keep, return_indices=True)
near_lab = lab[iy, ix]
below = opaque & (yy >= cy)
far_leg = (below & (near_lab == far_id)) | (hip_band & (xx < cx + 2))
near_leg = (below & (near_lab == near_id)) | (hip_band & (xx >= cx + 2))
far_leg &= ~far_arm & ~near_arm
near_leg &= ~far_arm & ~near_arm
body = (opaque & ~far_arm & ~near_arm & ~far_leg & ~near_leg | (hip_band & (yy < lt + 6))) & ~((yy >= lt + 6) & (xx >= 60) & (xx <= 135))

def layer(mask, dark=1.0):
    a = A.copy()
    a[~mask] = 0
    if dark != 1.0:
        a[:, :, :3] = (a[:, :, :3] * dark).astype(np.uint8)
    return Image.fromarray(a)

def body_with_pelvis():
    img = layer(body)
    # pants-colored pelvis underlay so rotating legs never open gaps at the hips
    pants = A[(A[:, :, 3] > 200) & (yy > cy) & (yy < cy + 15) & near_leg]
    col = tuple(int(c) for c in np.median(pants[:, :3], axis=0)) + (255,)
    under = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    hx = (cfg['hip_far'][0] + cfg['hip_near'][0]) // 2
    ImageDraw.Draw(under).ellipse([hx - 24, lt - 6, hx + 24, cy + 6], fill=col)
    under.alpha_composite(img)
    return under

L = dict(body=body_with_pelvis(), far_leg=layer(far_leg), near_leg=layer(near_leg),
         far_arm=layer(far_arm, 0.88), near_arm=layer(near_arm))

PAD = 60
def hip_clip(big):
    # after rotating a leg, trim anything above the hips that pokes outside the pelvis
    a = np.array(big)
    hx = (cfg['hip_far'][0] + cfg['hip_near'][0]) / 2.0 + PAD
    hy = cfg['hip_far'][1] + PAD
    Y, X = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    inside = ((X - hx) / 27.0) ** 2 + ((Y - hy) / 16.0) ** 2 <= 1.0
    a[(Y < hy + 4) & ~inside] = 0
    return Image.fromarray(a)

def place(canvas, img, pivot, angle, sy=1.0, dark=1.0, clip=False):
    big = Image.new('RGBA', (W + 2 * PAD, H + 2 * PAD), (0, 0, 0, 0))
    big.alpha_composite(img, (PAD, PAD))
    px, py = pivot[0] + PAD, pivot[1] + PAD
    if sy != 1.0:   # knee-bend stand-in: shorten the swinging leg toward the hip
        nh = int(round(big.height * sy))
        sq = big.resize((big.width, nh), Image.BICUBIC)
        big2 = Image.new('RGBA', big.size, (0, 0, 0, 0))
        big2.alpha_composite(sq, (0, int(round(py - py * sy))))
        big = big2
    big = big.rotate(angle, resample=Image.BICUBIC, center=(px, py))
    if clip:
        big = hip_clip(big)
    if dark != 1.0:
        big = ImageEnhance.Brightness(big).enhance(dark)
    canvas.alpha_composite(big)

mid = (cfg['far_leg_angle'] + cfg['near_leg_angle']) / 2.0
amp = (cfg['near_leg_angle'] - cfg['far_leg_angle']) / 2.0

def leg(canvas, phase, hip, dark):
    th = mid + amp * math.cos(2 * math.pi * phase)
    moving_forward = math.sin(2 * math.pi * phase) < 0   # angle increasing
    # pick the drawn pose that matches: heel-strike graphic in front, push-off graphic behind
    if th >= mid:
        g, nat, gp = L['near_leg'], cfg['near_leg_angle'], cfg['hip_near']
    else:
        g, nat, gp = L['far_leg'], cfg['far_leg_angle'], cfg['hip_far']
    # move the graphic so its own hip sits on this leg's hip
    shifted = Image.new('RGBA', g.size, (0, 0, 0, 0))
    shifted.alpha_composite(g, (0, 0))
    off = (hip[0] - gp[0], hip[1] - gp[1])
    shifted = shifted.transform(g.size, Image.AFFINE, (1, 0, -off[0], 0, 1, -off[1]))
    sy = 1.0 - (cfg['lift'] * abs(math.sin(2 * math.pi * phase)) if moving_forward else 0.0)
    place(canvas, shifted, hip, th - nat, sy, dark, clip=True)

frames = []
for i in range(cfg['frames']):
    p = i / cfg['frames']
    c = Image.new('RGBA', (W + 2 * PAD, H + 2 * PAD), (0, 0, 0, 0))
    arm = cfg['arm_swing'] * math.cos(2 * math.pi * p)
    place(c, L['far_arm'], cfg['shoulder_far'], arm)                 # far arm swings with near leg
    leg(c, p + 0.5, cfg['hip_far'], 0.86)                             # far leg (behind)
    place(c, L['body'], (0, 0), 0)
    leg(c, p, cfg['hip_near'], 1.0)                                   # near leg
    place(c, L['near_arm'], cfg['shoulder_near'], -arm)              # near arm opposite near leg
    frames.append(c.crop((PAD - 40, PAD - 20, PAD + W + 40, PAD + H + 30)))

# plant feet: lowest opaque pixel of each frame on a common baseline; keep body x fixed
def despeck(img, min_px=40):
    a = np.array(img)
    lab_s, ns = ndimage.label(a[:, :, 3] > 0, structure=np.ones((3, 3)))
    if ns > 1:
        sz = ndimage.sum(np.ones_like(lab_s), lab_s, range(1, ns + 1))
        for k, v in enumerate(sz):
            if v < min_px:
                a[lab_s == k + 1] = 0
    return Image.fromarray(a)

frames = [despeck(f) for f in frames]
out = []
for f in frames:
    a = np.array(f)[:, :, 3]
    bottom = np.nonzero(a.any(1))[0].max()
    shift = (f.height - 10) - bottom
    g = Image.new('RGBA', f.size, (0, 0, 0, 0))
    g.alpha_composite(f, (0, int(shift)))
    out.append(g)
strip = Image.new('RGBA', (out[0].width * len(out), out[0].height), (0, 0, 0, 0))
for i, f in enumerate(out):
    strip.alpha_composite(f, (i * f.width, 0))
strip.save('side_walk_src.png')
json.dump({'frame_w': out[0].width, 'frame_h': out[0].height, 'count': len(out)}, open('side_walk_src.json', 'w'))
# debug: show the cut parts in colors
dbg = np.zeros((H, W, 4), np.uint8)
for m, col in [(body, (200, 200, 200)), (far_leg, (60, 60, 220)), (near_leg, (60, 200, 60)), (far_arm, (220, 60, 60)), (near_arm, (230, 180, 40))]:
    dbg[m] = col + (255,)
Image.fromarray(dbg).save('side_parts_debug.png')
print('ok', len(out), out[0].size)
