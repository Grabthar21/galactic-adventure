"""Approved-asset protection for Space Piece. Plain Python (works on Henry or anywhere).

Every character entry moves through stages:
    brief -> concept -> model -> review -> approved   (archived = retired)
An APPROVED asset is never edited in place:
  - approve() records a fingerprint (SHA-256) of every approved file: Blender files,
    FBX, textures, and the Unreal .uasset files behind its /Game paths;
  - lock() marks those files read-only, so Blender/Unreal warn before overwriting them;
  - verify() reports anything changed or missing since approval (run it any time, e.g.
    before a play test or after an engine/plugin update);
  - new_version() is the only way back to editing: it bumps the version, unlocks, and
    moves the entry back to "model". Changes then go through review again.

CLI:
    python asset_guard.py verify pipeline/entries/arthur.json --content "C:/.../SpacePiece3D/Content"
    python asset_guard.py stage  pipeline/entries/arthur.json review --note "ready for review"
    python asset_guard.py approve pipeline/entries/arthur.json --content ... --by user --note "..."
    python asset_guard.py new-version pipeline/entries/arthur.json --note "new head"
"""
import argparse
import datetime as _dt
import hashlib
import json
import os
import stat
import sys

STAGES = ["brief", "concept", "model", "review", "approved", "archived"]
# allowed moves (forward one step, back to model from review/approved via new_version)
NEXT = {"brief": {"concept"}, "concept": {"model", "brief"}, "model": {"review", "concept"},
        "review": {"approved", "model"}, "approved": {"archived"}, "archived": set()}


class GuardError(Exception):
    pass


def _now():
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def load(entry_path):
    with open(entry_path, encoding="utf-8") as f:
        e = json.load(f)
    e.setdefault("stage", "model")
    e.setdefault("version", 1)
    e.setdefault("pipeline", {}).setdefault("log", [])
    return e


def save(entry_path, e):
    with open(entry_path, "w", encoding="utf-8") as f:
        json.dump(e, f, indent=2, ensure_ascii=False)
        f.write("\n")


def log(e, msg):
    e["pipeline"]["log"].append(f"{_now()[:10]}: {msg}")


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def ue_files(game_path, content_root):
    """/Game/Characters/X/SK_X -> [Content/Characters/X/SK_X.uasset (+ .uexp/.ubulk if present)]"""
    if not game_path.startswith("/Game/"):
        return []
    rel = game_path[len("/Game/"):].split(".")[0]
    base = os.path.join(content_root, *rel.split("/"))
    return [base + ext for ext in (".uasset", ".umap", ".uexp", ".ubulk") if os.path.exists(base + ext)]


def _collect(e, content_root):
    """Files that make up the approved asset: entry['protect'] = {'files': [...], 'unreal': [...]}"""
    p = e.get("protect", {})
    content_root = content_root or p.get("content_root")
    files = list(p.get("files", []))
    missing = []
    for g in p.get("unreal", []):
        fs = ue_files(g, content_root) if content_root else []
        if not fs:
            missing.append(g)
        files += fs
    return files, missing


def set_stage(entry_path, stage, note="", by="pipeline"):
    e = load(entry_path)
    cur = e["stage"]
    if stage not in STAGES:
        raise GuardError(f"unknown stage {stage}; use one of {STAGES}")
    if stage == "approved":
        raise GuardError("use approve() to approve: it records the fingerprint and locks the files")
    if stage not in NEXT.get(cur, set()):
        raise GuardError(f"{e.get('name')}: can't go from '{cur}' to '{stage}'"
                         + (" (approved assets change only through new_version())" if cur == "approved" else ""))
    e["stage"] = stage
    log(e, f"stage {cur} -> {stage} by {by}" + (f": {note}" if note else ""))
    save(entry_path, e)
    return e


def approve(entry_path, content_root=None, by="user", note="", do_lock=True):
    e = load(entry_path)
    if e["stage"] != "review":
        raise GuardError(f"{e.get('name')} is at '{e['stage']}'; only a model in review can be approved")
    if by != "user":
        raise GuardError("approval is the user's decision (by='user')")
    files, missing = _collect(e, content_root)
    if missing:
        raise GuardError(f"can't find the files for: {missing} (check --content)")
    if not files:
        raise GuardError("nothing to protect: list files/unreal paths under entry['protect']")
    fp = {os.path.normpath(f): sha256(f) for f in files}
    e["approved"] = {"date": _now(), "version": e["version"], "by": by, "note": note, "files": fp,
                     "content_root": content_root}
    e["stage"] = "approved"
    log(e, f"APPROVED v{e['version']} by {by}: {len(fp)} files fingerprinted" + (f" ({note})" if note else ""))
    save(entry_path, e)
    if do_lock:
        lock(entry_path)
    return e


def lock(entry_path, readonly=True):
    e = load(entry_path)
    n = 0
    for f in e.get("approved", {}).get("files", {}):
        if os.path.exists(f):
            mode = os.stat(f).st_mode
            os.chmod(f, (mode & ~stat.S_IWRITE & ~stat.S_IWGRP & ~stat.S_IWOTH) if readonly else (mode | stat.S_IWRITE))
            n += 1
    return n


def verify(entry_path, content_root=None):
    """Returns {'status': 'OK'|'CHANGED'|'NOT_APPROVED', 'changed': [...], 'missing': [...], 'new': [...]}"""
    e = load(entry_path)
    ap = e.get("approved")
    if not ap or e["stage"] != "approved":
        return {"name": e.get("name"), "status": "NOT_APPROVED", "stage": e["stage"]}
    changed, missing, writable = [], [], []
    for f, h in ap["files"].items():
        if not os.path.exists(f):
            missing.append(f)
            continue
        if sha256(f) != h:
            changed.append(f)
        if os.stat(f).st_mode & stat.S_IWRITE:  # read-only flag cleared (Explorer, Unreal 'make writable')
            writable.append(f)
    # files that appeared for the protected /Game paths (e.g. a new .ubulk)
    files, _ = _collect(e, content_root or ap.get("content_root"))
    new = [os.path.normpath(f) for f in files if os.path.normpath(f) not in ap["files"]]
    status = "OK" if not (changed or missing or new) else "CHANGED"
    return {"name": e.get("name"), "status": status, "version": ap["version"], "approved": ap["date"],
            "changed": changed, "missing": missing, "new": new, "unlocked": writable}


def new_version(entry_path, note="", by="user"):
    e = load(entry_path)
    if e["stage"] != "approved":
        raise GuardError(f"{e.get('name')} is not approved (stage '{e['stage']}')")
    lock(entry_path, readonly=False)
    e = load(entry_path)
    old = e["version"]
    e.setdefault("history", []).append(e.pop("approved"))
    e["version"] = old + 1
    e["stage"] = "model"
    log(e, f"new version v{e['version']} started by {by} (v{old} unlocked; its fingerprint kept in history)"
        + (f": {note}" if note else ""))
    save(entry_path, e)
    return e


def guard_edit(entry):
    """Call before any script changes a character: refuses on approved/archived entries."""
    if entry.get("stage") in ("approved", "archived"):
        raise GuardError(f"{entry.get('name')} v{entry.get('version', 1)} is {entry['stage']}; "
                         "start a new version (asset_guard.new_version) before changing it")


def _main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("verify", "approve", "stage", "new-version", "lock", "unlock"):
        p = sub.add_parser(c)
        p.add_argument("entries", nargs="+" if c == "verify" else 1)
        p.add_argument("--content", default=None, help="Unreal project Content folder")
        p.add_argument("--note", default="")
        p.add_argument("--by", default="user")
        if c == "stage":
            p.add_argument("stage")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "verify":
            bad = 0
            for ep in a.entries:
                r = verify(ep, a.content)
                print(json.dumps(r, indent=2))
                bad += r["status"] == "CHANGED"
            return 1 if bad else 0
        ep = a.entries[0]
        if a.cmd == "approve":
            approve(ep, a.content, a.by, a.note)
        elif a.cmd == "stage":
            set_stage(ep, a.stage, a.note, a.by)
        elif a.cmd == "new-version":
            new_version(ep, a.note, a.by)
        elif a.cmd in ("lock", "unlock"):
            print(lock(ep, a.cmd == "lock"), "files")
        print("ok")
        return 0
    except GuardError as err:
        print("REFUSED:", err)
        return 2


if __name__ == "__main__":
    sys.exit(_main())
