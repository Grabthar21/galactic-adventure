"""Unreal import check for Space Piece characters and creatures.

Run inside the Unreal Editor (Python). Reads character entries (JSON) and checks the
Unreal asset each one points to against the pipeline standard:
claude project doc `Character_Pipeline_Standard.md`.

Usage in the editor's Python console:
    import ue_import_check as c
    c.run_dir(r"C:/path/to/galactic-adventure/pipeline/entries")
or check ad-hoc entries:
    c.run([{"name": "Zebra", "asset": "/Game/AfricanAnimalsPack/Zebra/Meshes/SK_Zebra",
            "class": "creature", "archetype": "quadruped", "pack": True}])

Statuses: PASS, INFO, AUTO-FIX (scripted fix, logged), NEEDS RIG (rigging step),
ASK (needs the user's OK), REJECT (regenerate).
"""
import json
import os

import unreal

BUDGETS = {
    "hero":           {"tris": (20000, 40000), "lods": 3, "mats": 4},
    "background":     {"tris": (8000, 20000),  "lods": 3, "mats": 3},
    "creature":       {"tris": (5000, 15000),  "lods": 2, "mats": 3},
    "creature_large": {"tris": (5000, 25000),  "lods": 2, "mats": 3},
    "attachment":     {"tris": (0, 2000),      "lods": 1, "mats": 1},
}

ARCHETYPE_SKELETON = {
    "biped": "/Game/Characters/Mannequins/Meshes/SK_Mannequin",
    "quadruped": None,
    "longbody": None,
}

ORDER = {"REJECT": 4, "ASK": 3, "NEEDS RIG": 2, "AUTO-FIX": 1}


def _tag(asset_data, name):
    v = asset_data.get_tag_value(name)
    return None if v is None else str(v)


def check(entry):
    asset_path = entry.get("asset") or entry.get("unreal", {}).get("asset")
    cls = entry["class"]
    res = {"name": entry["name"], "asset": asset_path, "results": []}

    def add(name, status, detail):
        res["results"].append({"check": name, "status": status, "detail": detail})

    reg = unreal.AssetRegistryHelpers.get_asset_registry()
    found = reg.get_assets_by_package_name(asset_path)
    if not found:
        add("exists", "REJECT", "asset not found")
        res["verdict"] = "REJECT"
        return res
    a = found[0]
    b = BUDGETS[cls]

    tris = int(_tag(a, "Triangles") or 0)
    lods = int(_tag(a, "LODs") or 0)
    bones = int(_tag(a, "Bones") or 0)
    res.update(triangles=tris, lods=lods, bones=bones)

    hi = b["tris"][1]
    if tris > hi:
        add("triangles", "AUTO-FIX", f"{tris:,} is {tris / hi:.1f}x the {hi:,} limit")
    else:
        add("triangles", "PASS", f"{tris:,} (limit {hi:,})")

    add("lods", "AUTO-FIX" if lods < b["lods"] else "PASS", f"{lods} (need {b['lods']}+)")

    mesh = unreal.load_asset(asset_path)
    mats = len(mesh.materials)
    res["materials"] = mats
    add("materials", "AUTO-FIX" if mats > b["mats"] else "PASS", f"{mats} (limit {b['mats']})")

    ext = mesh.get_bounds().box_extent
    height = round(ext.z * 2)
    res["height_cm"] = height
    want_h = entry.get("height_cm")
    if want_h:
        ok = 0.5 <= height / want_h <= 2.0
        add("scale", "PASS" if ok else "AUTO-FIX", f"{height} cm tall (entry ~{want_h} cm)")
    else:
        add("size", "INFO", f"{height} cm tall, {round(max(ext.x, ext.y) * 2)} cm long")

    skel = mesh.skeleton.get_path_name().split(".")[0] if mesh.skeleton else None
    res["skeleton"] = skel
    want = entry.get("unreal", {}).get("target_skeleton") or ARCHETYPE_SKELETON.get(entry["archetype"])
    if skel is None:
        add("skeleton", "NEEDS RIG", "no skeleton assigned (broken or missing)")
    elif want is None:
        add("skeleton", "INFO", f"{skel.split('/')[-1]}, {bones} bones (archetype standard not chosen yet)")
    elif skel == want:
        add("skeleton", "PASS", "on archetype skeleton")
    else:
        add("skeleton", "NEEDS RIG", f"own skeleton {skel.split('/')[-1]}, {bones} bones; map to {want.split('/')[-1]}")

    short = asset_path.split("/")[-1]
    add("naming", "PASS" if short.startswith(("SK_", "SKM_")) else "AUTO-FIX", short)

    if not entry.get("pack"):
        root = "/Game/Creatures/" if cls.startswith("creature") else "/Game/Characters/"
        add("folder", "PASS" if asset_path.startswith(root) else "AUTO-FIX", asset_path.rsplit("/", 1)[0])

    for part in entry.get("must_have", []):
        add("part: " + part, "ASK", "confirm visually")

    worst = max([ORDER.get(r["status"], 0) for r in res["results"]] + [0])
    res["verdict"] = {4: "REJECT", 3: "ASK", 2: "NEEDS RIG", 1: "AUTO-FIX", 0: "PASS"}[worst]
    return res


def report(results):
    for r in results:
        print(f"{r['name']} => {r['verdict']}")
        for x in r["results"]:
            print(f"    {x['status']:<9} | {x['check']} | {x['detail']}")


def run(entries):
    results = [check(e) for e in entries]
    report(results)
    return results


def run_dir(entries_dir):
    entries = []
    for fn in sorted(os.listdir(entries_dir)):
        if fn.endswith(".json"):
            with open(os.path.join(entries_dir, fn), encoding="utf-8") as f:
                entries.append(json.load(f))
    return run(entries)
