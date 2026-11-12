"""Build a character's in-game walk + idle strips from Sprixen output, then QA them.

    python3 build_char.py <name>          e.g. python3 build_char.py arthur

Expects tools/sprixen/chars/<name>/ with:
    config.json                      settings (see chars/arthur/config.json)
    base_side.png, base_front.png, base_back.png   approved standing drawings (256x256)
    raw/walk_side.png, raw/walk_down.png, raw/walk_up.png   Sprixen walk sheets (premium)

Writes art/<name>_<side|down|up>_<walk|idle>.png (98x148 cells), a matching *_mask.png
(R = skin, G = hair; used by shaders/recolor.gdshader for player customization) and art/<name>_anims.json
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
    default_bases = {v: os.path.join(cdir, vc["base"]) for v, vc in cfg["views"].items()}
    ok = build_set(name, name, cfg, cdir, default_bases)
    sys.path.insert(0, HERE)
    from head_rows import head_rows
    # a hairstyle changes the head, not the body: keep the approved drawing's scale
    body_h = {v: head_rows(f)["HEIGHT"] for v, f in default_bases.items()}
    # hairstyles: the approved body with each style's head (compose_style.py), built the same way
    styles = {}
    for style, sc in cfg.get("hairstyles", {}).items():
        sdir = tempfile.mkdtemp(prefix=f"{name}_{style}_")
        bases = {}
        for v, vc in cfg["views"].items():
            out = os.path.join(sdir, f"base_{v}.png")
            run("compose_style.py", os.path.join(cdir, vc["base"]), os.path.join(cdir, sc[v]), out,
                *(["--no-face"] if v == "back" else []))
            bases[v] = out
        print(f"--- hairstyle {style}")
        ok &= build_set(name, f"{name}__{style}", cfg, cdir, bases, extra_idles=False, body_h=body_h,
                        locate_bases=default_bases)
        styles[style] = sc.get("label", style.replace("_", " ").title())
        shutil.rmtree(sdir, ignore_errors=True)
    with open(os.path.join(ART, f"{name}_styles.json"), "w") as fh:
        json.dump({"default": cfg.get("default_style_label", "Default"), **styles}, fh, indent=1)
    print("ALL CHECKS PASS" if ok else "SOME CHECKS FAILED - see above; contact sheets in /tmp/qa_*.png")
    sys.exit(0 if ok else 1)


def build_set(name, prefix, cfg, cdir, base_files, extra_idles=True, body_h=None, locate_bases=None):
    """Build walk + idle for side/down/up from the given base drawings; output art/<prefix>_*."""
    H = cfg.get("game_height", 133)
    cycle = cfg.get("walk_cycle_seconds", 0.8)
    idle = cfg.get("idle", {})
    w = tempfile.mkdtemp(prefix=f"{prefix}_")
    sys.path.insert(0, HERE)
    from head_rows import head_rows
    from lock_head import clean_body

    # approved drawings: head rows, height, cleaned copy, skin matched to the reference view
    views = {}
    for v in cfg["views"]:
        base = base_files[v]
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
        base_h = str(body_h[v] if body_h else d["prof"]["HEIGHT"])
        head_px = round((d["prof"]["CHIN_CUT"] - d["prof"]["HEAD_TOP"]) / d["prof"]["HEIGHT"] * H)

        # ---- walk
        raw = os.path.join(cdir, cfg["walks"][direction]["raw"])
        loop = os.path.join(w, f"{direction}_loop.png")
        out = run("find_loop.py", raw, loop, 16, 44).stdout.strip()
        frames = Image.open(loop).width // 256
        sc = os.path.join(w, f"{direction}_scaled.png")
        # the raw walk shows the approved head, so scale/locate against the approved drawing
        loc_base = locate_bases[v] if locate_bases else d["base"]
        loc_prof = json.dumps({k: head_rows(loc_base)[k] for k in ("HEAD_TOP", "BROW", "CHIN_CUT", "FACE")})
        run("match_scale.py", loop, loc_base, sc, loc_prof)
        lk = os.path.join(w, f"{direction}_locked.png")
        run("lock_head.py", sc, d["base"], lk, 2, 0, prof,
            env={"LOCATE_BASE": loc_base} if locate_bases else None)
        if cfg.get("fix_gloves"):
            run("fix_gloves.py", lk, lk)
        if d["clean"] != ref:
            run("skin_match.py", ref, lk, lk)
        fps = round(frames / cycle, 2)
        strip = os.path.join(ART, f"{prefix}_{direction}_walk.png")
        run("build_walk_strip.py", lk, strip, H, fps, env={"BASE_H": base_h})
        run("masks.py", strip, strip.replace(".png", "_mask.png"), head_px)   # skin/hair for recolouring
        manifest[f"walk_{direction}"] = {"frames": frames, "fps": fps}
        print(f"walk_{direction}: {out}")

        # ---- idle (the approved drawing, breathing)
        br = os.path.join(w, f"{direction}_breath.png")
        n_idle = idle.get("frames", 32)
        run("breathe.py", d["clean"], br, n_idle, idle.get("lift_px", 2.4))
        istrip = os.path.join(ART, f"{prefix}_{direction}_idle.png")
        run("build_idle_strip.py", br, istrip, H, env={"BASE_H": base_h})
        run("masks.py", istrip, istrip.replace(".png", "_mask.png"), head_px)
        manifest[f"idle_{direction}"] = {"frames": n_idle, "fps": idle.get("fps", 12)}
        if direction == "side" and extra_idles:
            for x in cfg.get("extra_idles", []):
                xo = os.path.join(ART, x["out"])
                run("build_idle_strip.py", br, xo, x["height"], env={"BASE_H": base_h})
                run("masks.py", xo, xo.replace(".png", "_mask.png"),
                    round(head_px * x["height"] / H))

    # reference colours the recolour shader converts FROM (median of solid skin / hair pixels)
    st = np.array(Image.open(os.path.join(ART, f"{prefix}_side_walk.png")).convert("RGBA")).astype(float)
    mk = np.array(Image.open(os.path.join(ART, f"{prefix}_side_walk_mask.png"))).astype(float)
    sel_s = (mk[..., 0] >= 250) & (st[..., 3] >= 250) & (st[..., :3].mean(2) > 150)
    sel_h = (mk[..., 1] >= 250) & (st[..., 3] >= 250)
    manifest["skin_ref"] = [round(v / 255, 4) for v in np.median(st[sel_s][:, :3], 0)]
    manifest["hair_ref"] = [round(v / 255, 4) for v in np.median(st[sel_h][:, :3], 0)]
    with open(os.path.join(ART, f"{prefix}_anims.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)

    # ---- QA
    ok = True
    for direction in ("side", "down", "up"):
        for kind in ("walk", "idle"):
            r = run("qa_strip.py", os.path.join(ART, f"{prefix}_{direction}_{kind}.png"),
                    f"{prefix}_{direction}_{kind}", H, kind)
            for line in r.stdout.splitlines():
                if line.startswith("==") or "FAIL" in line or "RESULT" in line:
                    print(line)
            ok &= r.returncode == 0
    r = run("qa_cross.py", prefix)
    print(r.stdout.strip())
    ok &= r.returncode == 0
    shutil.rmtree(w, ignore_errors=True)
    return ok


if __name__ == "__main__":
    main()
