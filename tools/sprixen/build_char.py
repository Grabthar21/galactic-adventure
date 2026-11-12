"""Build a character's in-game walk + idle strips from Sprixen output, then QA them.

    python3 build_char.py <name>          e.g. python3 build_char.py arthur

Expects tools/sprixen/chars/<name>/ with:
    config.json                      settings (see chars/arthur/config.json)
    base_side.png, base_front.png, base_back.png   approved standing drawings (256x256)
    raw/walk_side.png, raw/walk_down.png, raw/walk_up.png   Sprixen walk sheets (premium)

Writes art/<name>_<side|down|up>_<walk|idle>.png (98x148 cells) and art/<name>_anims.json
(frame counts + fps, read by scripts/player.gd). Exit code 1 if any QA check fails.

Per walk:  find_loop -> match_scale -> lock_head (+ matte clean) -> fix_gloves -> skin_match
           -> build_walk_strip (downscale, defringe, pinholes, specks, outline, feet on ground)
Per idle:  clean base -> skin_match -> breathe -> build_idle_strip
QA:        qa_strip.py per strip, qa_cross.py across walk/idle of each direction
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.normpath(os.path.join(HERE, "..", "..", "art"))
DIR_VIEW = {"side": "side", "down": "front", "up": "back"}


def run(*args, env=None, quiet=True):
    e = dict(os.environ, **(env or {}))
    r = subprocess.run([sys.executable, *map(str, args)], cwd=HERE, env=e,
                       capture_output=True, text=True)
    if r.returncode not in (0, 1) or (r.returncode == 1 and "qa_" not in str(args[0])):
        sys.stderr.write(r.stdout + r.stderr)
        raise SystemExit(f"step failed: {args[0]}")
    if not quiet:
        sys.stdout.write(r.stdout)
    return r


def main():
    name = sys.argv[1]
    cdir = os.path.join(HERE, "chars", name)
    cfg = json.load(open(os.path.join(cdir, "config.json")))
    H = cfg.get("game_height", 133)
    cycle = cfg.get("walk_cycle_seconds", 0.8)
    idle = cfg.get("idle", {})
    w = tempfile.mkdtemp(prefix=f"{name}_")
    sys.path.insert(0, HERE)
    from head_rows import head_rows
    from lock_head import clean_body

    # approved drawings: head rows, height, cleaned copy, skin matched to the reference view
    views = {}
    for v, vc in cfg["views"].items():
        base = os.path.join(cdir, vc["base"])
        prof = head_rows(base)
        clean = os.path.join(w, f"{v}_clean.png")
        b = np.array(Image.open(base).convert("RGBA")).astype(np.float32)
        Image.fromarray(np.clip(clean_body(b), 0, 255).astype(np.uint8)).save(clean)
        views[v] = dict(base=base, clean=clean, prof=prof)
    ref = views[cfg.get("skin_reference", "side")]["clean"]
    for v, d in views.items():
        if d["clean"] != ref:
            run("skin_match.py", ref, d["clean"], d["clean"])

    manifest, results = {}, []
    for direction in ("side", "down", "up"):
        v = DIR_VIEW[direction]
        d = views[v]
        prof = json.dumps({k: d["prof"][k] for k in ("HEAD_TOP", "BROW", "CHIN_CUT", "FACE")})
        base_h = str(d["prof"]["HEIGHT"])

        # ---- walk
        raw = os.path.join(cdir, cfg["walks"][direction]["raw"])
        loop = os.path.join(w, f"{direction}_loop.png")
        out = run("find_loop.py", raw, loop, 16, 44).stdout.strip()
        frames = Image.open(loop).width // 256
        sc = os.path.join(w, f"{direction}_scaled.png")
        run("match_scale.py", loop, d["base"], sc, prof)
        lk = os.path.join(w, f"{direction}_locked.png")
        run("lock_head.py", sc, d["base"], lk, 2, 0, prof)
        if cfg.get("fix_gloves"):
            run("fix_gloves.py", lk, lk)
        if d["clean"] != ref:
            run("skin_match.py", ref, lk, lk)
        fps = round(frames / cycle, 2)
        strip = os.path.join(ART, f"{name}_{direction}_walk.png")
        run("build_walk_strip.py", lk, strip, H, fps, env={"BASE_H": base_h})
        manifest[f"walk_{direction}"] = {"frames": frames, "fps": fps}
        print(f"walk_{direction}: {out}")

        # ---- idle (the approved drawing, breathing)
        br = os.path.join(w, f"{direction}_breath.png")
        n_idle = idle.get("frames", 32)
        run("breathe.py", d["clean"], br, n_idle, idle.get("lift_px", 2.4))
        istrip = os.path.join(ART, f"{name}_{direction}_idle.png")
        run("build_idle_strip.py", br, istrip, H, env={"BASE_H": base_h})
        manifest[f"idle_{direction}"] = {"frames": n_idle, "fps": idle.get("fps", 12)}
        if direction == "side":
            for x in cfg.get("extra_idles", []):
                run("build_idle_strip.py", br, os.path.join(ART, x["out"]), x["height"],
                    env={"BASE_H": base_h})

    with open(os.path.join(ART, f"{name}_anims.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)

    # ---- QA
    ok = True
    for direction in ("side", "down", "up"):
        for kind in ("walk", "idle"):
            r = run("qa_strip.py", os.path.join(ART, f"{name}_{direction}_{kind}.png"),
                    f"{name}_{direction}_{kind}", H, kind)
            for line in r.stdout.splitlines():
                if line.startswith("==") or "FAIL" in line or "RESULT" in line:
                    print(line)
            ok &= r.returncode == 0
    r = run("qa_cross.py", name)
    print(r.stdout.strip())
    ok &= r.returncode == 0
    shutil.rmtree(w, ignore_errors=True)
    print("ALL CHECKS PASS" if ok else "SOME CHECKS FAILED - see above; contact sheets in /tmp/qa_*.png")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
