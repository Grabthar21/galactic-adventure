"""Build a character's in-game walk + idle strips from Sprixen output, then QA them.

    python3 build_char.py <name>          e.g. python3 build_char.py arthur

Expects tools/sprixen/chars/<name>/ with:
    config.json                      settings (see chars/arthur/config.json)
    base_side.png, base_front.png, base_back.png   approved standing drawings (256x256)
    raw/walk_side.png, raw/walk_down.png, raw/walk_up.png   Sprixen walk sheets (premium)

Writes art/<name>_<side|down|up>_<walk|idle>.png (98x148 cells), a matching *_mask.png
(R = skin, G = hair; used by shaders/recolor.gdshader for player customization) and art/<name>_anims.json
(frame counts + fps, read by scripts/player.gd). Exit code 1 if any QA check fails.

Per walk:  find_loop -> match_scale -> lock_head (+ matte clean) -> match_legs -> fix_gloves -> skin_match
           -> build_walk_strip (downscale, defringe, pinholes, specks, outline, feet on ground)
Per idle:  clean base -> skin_match -> breathe -> build_idle_strip
Then:     stamp_head (idle frame 0's head on every walk/idle frame, whole-pixel positions)
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


RUN_CELL_W = None   # set from config "run_cell_w": run strips use wider cells (a run's stride is wide)


def run(*args, env=None, quiet=True):
    e = dict(os.environ, **(env or {}))
    if RUN_CELL_W and any(("_run" in str(a) or "_roll" in str(a) or "_attack" in str(a)) for a in args):
        e.setdefault("CELL_W", str(RUN_CELL_W))     # every step touching a run strip uses its cell
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
    global RUN_CELL_W
    RUN_CELL_W = cfg.get("run_cell_w")
    st = cfg.get("style", {})
    # every step (subprocesses too) reads the cell size and outline mode from the environment
    os.environ["CELL_SCALE"] = str(st.get("cell_scale", 1))
    os.environ["REINK"] = "1" if st.get("reink", True) else "0"
    os.environ["HEAD_LOCK"] = "1" if st.get("head_lock", True) else "0"
    default_bases = {v: os.path.join(cdir, vc["base"]) for v, vc in cfg["views"].items()}
    ok = build_set(name, name, cfg, cdir, default_bases)
    sys.path.insert(0, HERE)
    from head_rows import head_rows
    # a hairstyle changes the head, not the body: keep the approved drawing's scale
    body_h = {v: head_rows(f)["HEIGHT"] for v, f in default_bases.items()}
    # hairstyles: the approved body with each style's head (compose_style.py), built the same way
    styles = {}
    # hairstyles paste a drawn hairstyle onto the walk's head, so they need the locked-head mode;
    # with Sprixen's own heads each style would need its own Sprixen walks
    hair = cfg.get("hairstyles", {}) if cfg.get("style", {}).get("head_lock", True) else {}
    for style, sc in hair.items():
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
    K = float(os.environ.get("CELL_SCALE", "1"))
    head_lock = cfg.get("style", {}).get("head_lock", True)
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
        if cfg.get("style", {}).get("head_lock", True):
            cb = clean_body(b)
        else:
            from clean_sheet import clean_soft   # soft outline to match the Sprixen-style walks
            cb = clean_soft(b, collar=False, aa=False)   # the standing drawings are approved as they are
        Image.fromarray(np.clip(cb, 0, 255).astype(np.uint8)).save(clean)
        views[v] = dict(base=base, clean=clean, prof=prof)
    ref = views[cfg.get("skin_reference", "side")]["clean"]
    for v, d in views.items():
        if d["clean"] != ref:
            run("skin_match.py", ref, d["clean"], d["clean"])

    manifest, results = {}, []
    attack_parts = {}     # direction -> (combo strip, picked raw frames, raw track, segments)
    refs = {}
    walk_scale = {}
    for direction in ("side", "down", "up"):
        v = DIR_VIEW[direction]
        d = views[v]
        prof = json.dumps({k: d["prof"][k] for k in ("HEAD_TOP", "BROW", "CHIN_CUT", "FACE")})
        base_h = str(body_h[v] if body_h else d["prof"]["HEIGHT"])
        head_px = round((d["prof"]["CHIN_CUT"] - d["prof"]["HEAD_TOP"]) / d["prof"]["HEIGHT"] * H * K)

        strips = {}
        # walk and run are loops; a roll is a one-shot move (played once per dodge). Runs and rolls
        # are both kept as Sprixen's locked camera drew them ("free" moves below).
        for kind, moves in (("walk", cfg["walks"]), ("run", cfg.get("runs", {})), ("roll", cfg.get("rolls", {})),
                            ("attack", cfg.get("attacks", {}))):
            if direction not in moves:
                continue
            # ---- walk
            raw = os.path.join(cdir, moves[direction]["raw"])
            loop = os.path.join(w, f"{direction}_{kind}_loop.png")
            if kind == "roll":
                rng = moves[direction].get("frames", [])
                out = run("pick_oneshot.py", raw, loop, cfg.get("roll_frames", 18), *rng).stdout.strip()
            elif kind == "attack":
                # the whole combo (3 slashes + recovery) as one strip, weapon taken out and tracked
                # (weapon_track.py); split into its parts after the strip is built
                seg_json = os.path.join(w, f"{direction}_attack_segs.json")
                json.dump(moves[direction]["segments"], open(seg_json, "w"))
                atk_track = os.path.join(w, f"{direction}_attack_rawtrack.json")
                out = run("weapon_track.py", "prep", raw, seg_json, loop, atk_track).stdout.strip()
            else:
                out = run("find_loop.py", raw, loop, *((16, 44) if kind == "walk" else (10, 40))).stdout.strip()
            frames = Image.open(loop).width // 256
            sc = os.path.join(w, f"{direction}_{kind}_scaled.png")
            # the raw walk shows the approved head, so scale/locate against the approved drawing
            loc_base = locate_bases[v] if locate_bases else d["base"]
            loc_prof = json.dumps({k: head_rows(loc_base)[k] for k in ("HEAD_TOP", "BROW", "CHIN_CUT", "FACE")})
            ms_env = {"FALLBACK_SCALE": str(walk_scale[direction])} if kind != "walk" and direction in walk_scale else {}
            if kind == "attack":   # the take ends standing (the recovery's last frame): measure there
                ms_env = {"SCALE_FRAMES": "-1,-2"}
            ms = run("match_scale.py", loop, loc_base, sc, loc_prof, env=ms_env or None).stdout
            print(ms.strip())
            if kind == "walk":
                walk_scale[direction] = float(ms.split("rescaled by ")[1].split()[0])
            lk = os.path.join(w, f"{direction}_{kind}_locked.png")
            if head_lock:
                run("lock_head.py", sc, d["base"], lk, 2, 0, prof,
                    env={"LOCATE_BASE": loc_base} if locate_bases else None)
            else:   # Sprixen's own head (turns with the body, hair moves); only the matte is cleaned
                # geometry (head size, bob, leg length, placement) is measured on the sheet WITHOUT the
                # collar repair, so colour/outline fixes never move anything
                geo = os.path.join(w, f"{direction}_{kind}_geom.png")
                tumble = {"TUMBLE": "1"} if kind == "roll" else None
                run("clean_sheet.py", sc, geo, "--gentle", env=tumble)
                run("clean_sheet.py", sc, lk, "--gentle", env=tumble)
                geo2 = geo.replace(".png", "_h.png")
                geo3 = geo.replace(".png", "_l.png")
                if kind != "walk":
                    # a run is kept exactly as Sprixen's locked camera drew it (one uniform scale):
                    # per-frame head/leg fitting moves the airborne frames and makes the head pop
                    shutil.copy(geo, geo2)
                    shutil.copy(geo, geo3)
                else:
                    print(run("match_head.py", geo, d["base"], geo2, prof).stdout.strip())   # approved head size
                    run("match_head.py", lk, d["base"], lk, prof, env={"GEOM_SHEET": geo})
                    run("match_legs.py", geo2, d["base"], geo3, prof)
                    run("match_legs.py", lk, d["base"], lk, prof, env={"GEOM_SHEET": geo2})
            if head_lock:
                print(run("match_legs.py", lk, d["base"], lk, prof).stdout.strip())   # never taller walking than standing
            if cfg.get("fix_gloves"):
                run("fix_gloves.py", lk, lk)
            if d["clean"] != ref:
                run("skin_match.py", ref, lk, lk)
            if not head_lock:   # Sprixen-style: give every frame the approved drawing's outline
                print(run("ink_outline.py", lk, d["base"], lk,
                          env={"OUTLINE_WEIGHT": str(cfg.get("style", {}).get("outline_weight", 1)),
                               **({"STRICT_ROWS": "1"} if kind != "walk" else {})}).stdout.strip())
            fps = round(frames / {"walk": cycle, "run": cfg.get("run_cycle_seconds", 0.55),
                                  "roll": cfg.get("roll_seconds", 0.36),
                                  "attack": sum(cfg.get("attack_seconds", {"x": 1.3}).values())}[kind], 2)
            strip = os.path.join(ART, f"{prefix}_{direction}_{kind}.png")
            fixed = ({"PLACE_FIXED": "1"} if kind != "walk" else {}) | ({"ONESHOT": "1"} if kind == "roll" else {})
            run("build_walk_strip.py", lk, strip, H, fps,
                env={"BASE_H": base_h, **fixed, **({} if head_lock else {"PLACE_FROM": geo3})})
            if not head_lock:
                # reference: Sprixen's own frames with the same geometry and no clean-up (qa_fidelity.py)
                rf = os.path.join(w, f"{direction}_{kind}_ref.png")
                if kind != "walk":
                    shutil.copy(sc, rf)
                else:
                    run("match_head.py", sc, d["base"], rf, prof, env={"GEOM_SHEET": geo})
                    run("match_legs.py", rf, d["base"], rf, prof, env={"GEOM_SHEET": geo2})
                refs[(direction, kind)] = os.path.join(w, f"{direction}_{kind}_ref_strip.png")
                run("build_walk_strip.py", rf, refs[(direction, kind)], H, fps,
                    env={"BASE_H": base_h, "PLACE_FROM": geo3, "REINK": "0", **fixed})
            if kind == "roll":
                # every frame the same body size: the head is measured in each frame against the
                # run's head (roll_scale.py) and each frame resized to match; measured once and kept
                # in chars/<name>/roll_scales.json (delete an entry, or RESCALE=1, to measure again)
                sp = os.path.join(cdir, "roll_scales.json")
                known = json.load(open(sp)) if os.path.exists(sp) else {}
                picks = open(loop + ".picks").read().strip()
                if known.get(direction, {}).get("picks") != picks or os.environ.get("RESCALE"):
                    rs, re_ = moves[direction]["frames"]
                    rep = run("roll_scale.py", strip, direction, raw, rs, re_, "--picks", picks, "--report").stdout.strip()
                    print(f"roll size, {direction} (as Sprixen drew it):\n{rep}")
                    known[direction] = {"picks": picks, "scales": rep.splitlines()[-1],
                                        "measured": rep.splitlines()[:-1]}
                    json.dump(known, open(sp, "w"), indent=1)
                fsc = {"FRAME_SCALES": known[direction]["scales"]}
                run("build_walk_strip.py", lk, strip, H, fps,
                    env={"BASE_H": base_h, **fixed, **fsc, **({} if head_lock else {"PLACE_FROM": geo3})})
                if not head_lock:
                    run("build_walk_strip.py", rf, refs[(direction, kind)], H, fps,
                        env={"BASE_H": base_h, "PLACE_FROM": geo3, "REINK": "0", **fixed, **fsc})
            if not head_lock and direction == "side":
                pass   # the near-glove size is matched after the idle strip exists (below)
            run("masks.py", strip, strip.replace(".png", "_mask.png"), head_px,   # skin/hair for recolouring
                env={"TUMBLE": "1"} if kind == "roll" else None)
            if kind == "attack":
                attack_parts[direction] = (strip, loop, atk_track, seg_json)
            else:
                manifest[f"{kind}_{direction}"] = {"frames": frames, "fps": fps,
                                                   **({"cell_w": RUN_CELL_W} if kind != "walk" and RUN_CELL_W else {})}
            strips[kind] = strip
            print(f"{kind}_{direction}: {out}")

        # ---- idle (the approved drawing, breathing)
        br = os.path.join(w, f"{direction}_breath.png")
        n_idle = idle.get("frames", 32)
        run("breathe.py", d["clean"], br, n_idle, idle.get("lift_px", 2.4))
        istrip = os.path.join(ART, f"{prefix}_{direction}_idle.png")
        run("build_idle_strip.py", br, istrip, H, env={"BASE_H": base_h})
        run("masks.py", istrip, istrip.replace(".png", "_mask.png"), head_px)
        manifest[f"idle_{direction}"] = {"frames": n_idle, "fps": idle.get("fps", 12)}
        for kind, strip in strips.items():
          if not head_lock:
            rfp = refs[(direction, kind)]
            if direction == "side" and kind == "walk":   # a run's hand is foreshortened as Sprixen drew it
                # near hand: one size in every walk frame, measured from the approved standing drawing
                print(run("match_glove.py", strip, istrip).stdout.strip())
            # one-frame blinks / dents in the upper body (what qa_shape.py checks), two passes
            mt = {"MOTION_TOL": "2" if kind != "walk" else "1"}
            steps = (["deflicker"] * 3 + ["fix"] + ["deflicker"] * 2 + ["fix", "deflicker"]) if kind == "walk" \
                else ["static", "static", "fix", "static"]   # runs: no blending between frames
            for k, st in enumerate(steps):
                if os.environ.get("DEBUG_STAGES"):
                    shutil.copy(strip, f"/tmp/stage_{direction}_{kind}_{k}.png")
                if st == "static":
                    print(run("deflicker.py", strip, env={"REF_STRIP": rfp, "NO_TEMPORAL": "1", **mt,
                                                          **({"TUMBLE": "1"} if kind == "roll" else {})}).stdout.strip())
                elif st == "fix":
                    print(run("qa_fidelity.py", strip, rfp, "--fix").stdout.strip())
                else:
                    print(run("deflicker.py", strip, env={"REF_STRIP": rfp, **mt}).stdout.strip())
            run("masks.py", strip, strip.replace(".png", "_mask.png"), head_px,
                env={"TUMBLE": "1"} if kind == "roll" else None)
        if direction in attack_parts:
            # split the combo strip into attack1-3 + attack_rec, weapon track in strip-cell pixels
            strip, loop, atk_track, seg_json = attack_parts[direction]
            meta = os.path.join(w, f"{direction}_attack_meta.json")
            json.dump({"spins": cfg["attacks"][direction].get("spins", {}),
                       "hit": cfg.get("attack_hit", {})}, open(meta, "w"))
            from cells import CELL_H as _CH
            print(run("weapon_track.py", "finish", strip, loop, atk_track, seg_json,
                      os.path.join(ART, f"{prefix}_{direction}"), meta, RUN_CELL_W, _CH).stdout.strip())
            segs = cfg["attacks"][direction]["segments"]
            for part in segs:
                nfr = Image.open(os.path.join(ART, f"{prefix}_{direction}_{part}.png")).width // RUN_CELL_W
                manifest[f"{part}_{direction}"] = {"frames": nfr, "cell_w": RUN_CELL_W,
                                                   "fps": round(nfr / cfg["attack_seconds"][part], 2)}
        if direction == "side" and extra_idles:
            for x in cfg.get("extra_idles", []):
                xo = os.path.join(ART, x["out"])
                # extra idles keep the original 98x148 cells (they pair with older hand-made strips)
                run("build_idle_strip.py", br, xo, x["height"], env={"BASE_H": base_h, "CELL_SCALE": "1", "REINK": "1"})
                run("masks.py", xo, xo.replace(".png", "_mask.png"),
                    round(head_px / K * x["height"] / H), env={"CELL_SCALE": "1"})

    # one face for every frame: re-stamp idle frame 0's head (whole-pixel positions) on all walk
    # and idle frames of each direction, then rebuild the recolour masks
    for direction in (("side", "down", "up") if head_lock else ()):
        v = DIR_VIEW[direction]
        dp = views[v]["prof"]
        head_px = round((dp["CHIN_CUT"] - dp["HEAD_TOP"]) / dp["HEIGHT"] * H * K)
        ref_idle = os.path.join(w, f"{direction}_idle_ref.png")
        shutil.copy(os.path.join(ART, f"{prefix}_{direction}_idle.png"), ref_idle)
        for kind in ("walk", "idle"):
            sp = os.path.join(ART, f"{prefix}_{direction}_{kind}.png")
            print(run("stamp_head.py", sp, ref_idle, head_px, 0).stdout.strip())
            run("masks.py", sp, sp.replace(".png", "_mask.png"), head_px)

    # reference colours the recolour shader converts FROM (median of solid skin / hair pixels)
    st = np.array(Image.open(os.path.join(ART, f"{prefix}_side_walk.png")).convert("RGBA")).astype(float)
    mk = np.array(Image.open(os.path.join(ART, f"{prefix}_side_walk_mask.png"))).astype(float)
    sel_s = (mk[..., 0] >= 250) & (st[..., 3] >= 250) & (st[..., :3].mean(2) > 150)
    sel_h = (mk[..., 1] >= 250) & (st[..., 3] >= 250)
    manifest["skin_ref"] = [round(v / 255, 4) for v in np.median(st[sel_s][:, :3], 0)]
    manifest["hair_ref"] = [round(v / 255, 4) for v in np.median(st[sel_h][:, :3], 0)]
    from cells import CELL_W, CELL_H
    manifest["cell"] = [CELL_W, CELL_H]          # player.gd: frame size and draw scale of these strips
    manifest["draw_scale"] = round(0.75 / K, 4)
    manifest["smooth"] = K != 1
    with open(os.path.join(ART, f"{prefix}_anims.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)

    # ---- QA
    ok = True
    for direction in ("side", "down", "up"):
        for kind in ("walk", "idle", "run", "roll", "attack"):
            if kind in ("run", "roll", "attack") and direction not in cfg.get(kind + "s", {}):
                continue
            r = run("qa_strip.py", os.path.join(ART, f"{prefix}_{direction}_{kind}.png"),
                    f"{prefix}_{direction}_{kind}", round(H * K), kind)
            for line in r.stdout.splitlines():
                if line.startswith("==") or "FAIL" in line or "RESULT" in line:
                    print(line)
            ok &= r.returncode == 0
            if kind == "roll":     # body size: the head the same size as in the run, frame by frame
                r = run("roll_scale.py", "--check", os.path.join(ART, f"{prefix}_{direction}_{kind}.png"), direction)
                for line in r.stdout.splitlines():
                    if line.startswith("==") or "FAIL" in line or "RESULT" in line:
                        print(line)
                ok &= r.returncode == 0
    if not cfg.get("style", {}).get("head_lock", True):
        for direction, kind in refs:
            r = run("qa_fidelity.py", os.path.join(ART, f"{prefix}_{direction}_{kind}.png"),
                    refs[(direction, kind)], f"{prefix}_{direction}_{kind}")
            for line in r.stdout.splitlines():
                if line.startswith("==") or "FAIL" in line or "RESULT" in line:
                    print(line)
            ok &= r.returncode == 0
            r = run("qa_shape.py", os.path.join(ART, f"{prefix}_{direction}_{kind}.png"),
                    os.path.join(ART, f"{prefix}_{direction}_idle.png"), f"{prefix}_{direction}_{kind}",
                    env={"MOTION_TOL": "2" if kind != "walk" else "1", "REF_STRIP": refs[(direction, kind)],
                         **({"TUMBLE": "1"} if kind == "roll" else {})})
            for line in r.stdout.splitlines():
                if line.startswith("==") or "FAIL" in line or "RESULT" in line:
                    print(line)
            ok &= r.returncode == 0
    r = run("qa_cross.py", prefix)
    print(r.stdout.strip())
    ok &= r.returncode == 0
    # the whole-combo attack strips were only a build step (the game loads the split parts)
    for direction in cfg.get("attacks", {}):
        for suffix in (".png", "_mask.png"):
            pth = os.path.join(ART, f"{prefix}_{direction}_attack{suffix}")
            if os.path.exists(pth):
                shutil.copy(pth, f"/tmp/{prefix}_{direction}_attack_combo{suffix}")
                os.remove(pth)
    for (direction, kind), rp in refs.items():          # kept for inspection
        shutil.copy(rp, f"/tmp/ref_{prefix}_{direction}" + ("" if kind == "walk" else "_" + kind) + ".png")
    shutil.rmtree(w, ignore_errors=True)
    return ok


if __name__ == "__main__":
    main()
