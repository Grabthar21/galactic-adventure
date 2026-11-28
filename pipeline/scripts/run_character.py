"""One command: run every Blender-side check for a character and write its report card.

    import run_character
    card = run_character.run(r"C:/.../pipeline/entries/arthur.json", out_dir=r"C:/.../review/arthur")

Reads the character entry (`pipeline/entries/<name>.json`):
    "blender": {"meshes": ["SK_Arthur"], "armature": "Armature", "reference": ["SK_Arthur"]}
    "style":   {"group": "human_teen", "accent": "#..."}
    "hero", "height_cm", "stage", "version"
and runs, in order:
    1. style check  (proportions, textures, matte materials, eyes) + review turnaround
    2. pose test    (rest pose, 8-pose suite, pose strip)
    3. game camera  (as players see it) and lineup (next to Arthur, door, fence, sword)
Then writes ONE page: <out_dir>/<name>_report_card.html (+ .json), and logs the run in the entry.

Approved characters are checked read-only (no auto-fixes), per asset_guard.
"""
import datetime as _dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "."
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy  # noqa: E402

import asset_guard  # noqa: E402
import blender_pose_test as pose_test  # noqa: E402
import blender_review_renders as review  # noqa: E402
import blender_style_check as style  # noqa: E402
import report_card  # noqa: E402


def _thumb(path, max_side=1100, quality=82):
    """JPEG copy for the report page (keeps it small enough to share)."""
    if not path or not os.path.exists(path):
        return path
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    s = min(1.0, max_side / max(w, h))
    if s < 1.0:
        img.scale(int(w * s), int(h * s))
    out = os.path.splitext(path)[0] + "_web.jpg"
    # save the pixels as they are (save_render would colour-manage them a second time)
    img.filepath_raw = out
    img.file_format = "JPEG"
    img.save(quality=quality)
    bpy.data.images.remove(img)
    return out


def _strip(paths, out, height=420):
    """Join several renders side by side into one picture (Blender images, no PIL needed)."""
    import numpy as np
    imgs = []
    for p in paths:
        if os.path.exists(p):
            im = bpy.data.images.load(p, check_existing=False)
            w, h = im.size
            im.scale(max(1, int(w * height / h)), height)
            a = np.empty(im.size[0] * im.size[1] * 4, dtype=np.float32)
            im.pixels.foreach_get(a)
            imgs.append(a.reshape(height, im.size[0], 4))
            bpy.data.images.remove(im)
    if not imgs:
        return None
    strip = np.concatenate(imgs, axis=1)
    H, W = strip.shape[:2]
    res = bpy.data.images.new("strip", W, H, alpha=True)
    res.pixels.foreach_set(strip.ravel())
    res.filepath_raw = out
    res.file_format = "PNG"
    res.save()
    bpy.data.images.remove(res)
    return out


def _section(title, checks, images=(), notes=(), wide=False):
    return {"title": title, "verdict": report_card.verdict([c["status"] for c in checks]) if checks else "PASS",
            "checks": checks, "images": [i for i in images if i], "notes": list(notes), "wide_images": wide}


def run(entry_path, out_dir=None, poses=None, render=True):
    entry = asset_guard.load(entry_path)
    name = entry.get("name", "character")
    out_dir = out_dir or os.path.join(os.path.dirname(os.path.abspath(entry_path)), "..", "review", name.lower())
    os.makedirs(out_dir, exist_ok=True)
    b = entry.get("blender", {})
    meshes = [bpy.data.objects[m] for m in b.get("meshes", []) if m in bpy.data.objects]
    if not meshes:
        raise RuntimeError(f"{name}: none of entry.blender.meshes {b.get('meshes')} are in this Blender file")
    arm = bpy.data.objects.get(b.get("armature", "Armature"))
    approved = entry.get("stage") in ("approved", "archived")
    group = entry.get("style", {}).get("group", "human_teen")
    hero = bool(entry.get("hero"))
    sections, measured = [], {}

    # 1. style
    st = style.run(meshes, arm, group=group, hero=hero, height_cm=entry.get("height_cm"),
                   fix=not approved, out_dir=out_dir, name=name, render=render)
    measured["style"] = st["measured"]
    turn = st.get("renders", [])
    face = [p for p in turn if p.endswith("_face.png")]
    body = [p for p in turn if not p.endswith("_face.png")]
    strip = _strip(body, os.path.join(out_dir, f"{name}_turnaround.png")) if body else None
    notes = ["Read-only run: this character is approved, so nothing was changed."] if approved else []
    sections.append(_section("Look and style", st["checks"], [_thumb(strip)] + [_thumb(p) for p in face], notes))

    # 2. poses
    if arm:
        pt = pose_test.run(meshes, arm, out_dir=out_dir, name=name, poses=poses, render=render)
        measured["poses"] = pt["measured"]
        pstrip = _strip(pt.get("renders", []), os.path.join(out_dir, f"{name}_poses.png"), height=360)
        sections.append(_section("Rig and poses", pt["checks"], [_thumb(pstrip, 1600)], wide=True))
    else:
        sections.append(_section("Rig and poses", [{"check": "armature", "status": "ASK",
                                                    "detail": "no armature found; rig before the pose test"}]))

    # 3. as players see it
    gc = review.game_camera(meshes, out_dir, name) if render else {"renders": [], "screen_height_px": None}
    ref = [m for m in b.get("reference", ["SK_Arthur"]) if m in bpy.data.objects and m not in b.get("meshes", [])]
    lu = review.lineup(meshes, out_dir, name, reference=ref) if render else {"renders": [], "height_cm": None}
    measured["game_camera"] = {"screen_height_px": gc["screen_height_px"]}
    measured["lineup"] = {k: v for k, v in lu.items() if k != "renders"}
    gchecks = []
    if gc["screen_height_px"]:
        gchecks.append({"check": "size on screen", "status": "INFO",
                        "detail": f"about {gc['screen_height_px']} px tall at 1080p from the play camera. "
                                  "Details you can't see here aren't worth a fix round."})
    want = entry.get("height_cm")
    if want and lu.get("height_cm"):
        off = abs(lu["height_cm"] - want) / want
        gchecks.append({"check": "height", "status": "PASS" if off <= 0.03 else "ASK",
                        "detail": f"{lu['height_cm']} cm (entry says {want} cm)"})
    sections.append(_section("As players see it", gchecks,
                             [_thumb(p) for p in gc["renders"]] + [_thumb(p, 1600) for p in lu["renders"]]))

    allc = [c for s in sections for c in s["checks"]]
    card = {"name": name, "date": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "stage": entry.get("stage"), "version": entry.get("version", 1), "hero": hero, "group": group,
            "height_cm": lu.get("height_cm") or entry.get("height_cm"),
            "verdict": report_card.verdict([c["status"] for c in allc]),
            "sections": sections, "measured": measured}
    path = report_card.write(card, os.path.join(out_dir, f"{name}_report_card.html"))

    if not approved:  # log the run in the entry (approved entries stay untouched)
        e = asset_guard.load(entry_path)
        n = {k: sum(c["status"] == k for c in allc) for k in ("ASK", "FIX", "FIXED", "CHECK")}
        asset_guard.log(e, f"report card: {card['verdict']} ({n['ASK']} to decide, {n['FIX']} to fix, "
                           f"{n['FIXED']} auto-fixed, {n['CHECK']} to look at) -> {os.path.basename(path)}")
        e["pipeline"]["report_card"] = {"date": card["date"], "verdict": card["verdict"], "path": path}
        asset_guard.save(entry_path, e)
    card["path"] = path
    return card
