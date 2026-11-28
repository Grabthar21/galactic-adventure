"""Lock-on part of Arthur_Combat_Nodes.txt: Zelda-style lock-on for BP_Arthur.

Tab (keyboard) or Left Trigger (gamepad) toggles. Locking picks the nearest actor tagged
"Lockable" within LOCK_RANGE. While locked, every frame the camera (control rotation)
turns smoothly toward the target and Arthur faces where the camera faces, so W/S move
toward/away from the target and A/D circle it. Lock drops past BREAK_RANGE or when the
target is gone (killed, despawned).

Needs two BP_Arthur variables, added by ue_arthur_combat_setup.py: LockTarget (Actor), IsLockedOn (bool).
Built into Arthur_Combat_Nodes.txt by gen_arthur_combat_nodes.py (shares Event Tick).
"""
from t3d import G, ENGINE, STRUCT

LOCK_RANGE = 1500.0   # 15 m: how far away a target can be picked
BREAK_RANGE = 2200.0  # 22 m: lock drops when the target gets this far away
CAM_PITCH = -12.0     # camera looks slightly down at the target
TURN_SPEED = 8.0      # how fast the camera swings onto the target

VEC, ROT = STRUCT.format("Vector"), STRUCT.format("Rotator")
ACTOR = ENGINE.format("Actor")
CMC = "CharacterMovementComponent"

g = G("Lock")
L = g.link

g.comment("Box", -80, -140, 3500, 1500,
          "Lock-on (Tab / gamepad Left Trigger): locks onto the nearest actor tagged Lockable within 15 m. "
          "Camera and Arthur face the target; A/D circle it. Lets go past 22 m, when the target is gone, "
          "or on a second press. Variables: LockTarget, IsLockedOn.")

# ---------------- toggle ----------------
tab = g.input_key("Tab", "Tab", 0, 0)
lt = g.input_key("LT", "Gamepad_LeftTrigger", 0, 140)
is_locked = g.get("IsLocked1", "IsLockedOn", 220, 230, "bool")
br_toggle = g.branch("Toggle", 420, 60)
L(tab["Pressed"], br_toggle["execute"])
L(lt["Pressed"], br_toggle["execute"])
L(is_locked["IsLockedOn"], br_toggle["Condition"])

tagged = (g.call("Tagged", "GameplayStatics", "GetAllActorsWithTag", 700, 140)
          .pin("Tag", cat="name", default="Lockable")
          .pin("OutActors", out=True, cat="object", obj=ACTOR, array=True))
L(br_toggle["else"], tagged["execute"])

self_loc = g.call("SelfLoc", "Actor", "K2_GetActorLocation", 700, 360, pure=True).pin(
    "ReturnValue", out=True, cat="struct", obj=VEC)
nearest = (g.call("Nearest", "GameplayStatics", "FindNearestActor", 1040, 140)
           .pin("Origin", cat="struct", obj=VEC)
           .pin("ActorsToCheck", cat="object", obj=ACTOR, array=True)
           .pin("Distance", out=True, cat="real", sub="float")
           .pin("ReturnValue", out=True, cat="object", obj=ACTOR))
L(tagged["then"], nearest["execute"])
L(tagged["OutActors"], nearest["ActorsToCheck"])
L(self_loc["ReturnValue"], nearest["Origin"])

found_valid = (g.call("FoundValid", "KismetSystemLibrary", "IsValid", 1380, 330, pure=True)
               .pin("Object", cat="object")
               .pin("ReturnValue", out=True, cat="bool"))
in_range = (g.call("InRange", "KismetMathLibrary", "LessEqual_DoubleDouble", 1380, 430, pure=True)
            .pin("A", cat="real", sub="double").pin("B", cat="real", sub="double", default=f"{LOCK_RANGE:.6f}")
            .pin("ReturnValue", out=True, cat="bool"))
found_and = (g.call("FoundAnd", "KismetMathLibrary", "BooleanAND", 1600, 380, pure=True)
             .pin("A", cat="bool").pin("B", cat="bool").pin("ReturnValue", out=True, cat="bool"))
L(nearest["ReturnValue"], found_valid["Object"])
L(nearest["Distance"], in_range["A"])
L(found_valid["ReturnValue"], found_and["A"])
L(in_range["ReturnValue"], found_and["B"])

br_found = g.branch("Found", 1800, 140)
L(nearest["then"], br_found["execute"])
L(found_and["ReturnValue"], br_found["Condition"])

set_target = g.set("Target", "LockTarget", 2040, 140, "object", obj=ACTOR)
set_locked_t = g.set("LockedT", "IsLockedOn", 2300, 140, "bool", value="true")
cmc1 = g.get("CMC1", "CharacterMovement", 2300, 360, "object", obj=ENGINE.format(CMC), owner="Character")
orient_off = g.set("OrientOff", "bOrientRotationToMovement", 2560, 140, "bool", owner=CMC, value="false")
desired_on = g.set("DesiredOn", "bUseControllerDesiredRotation", 2860, 140, "bool", owner=CMC, value="true")
L(br_found["then"], set_target["execute"])
L(nearest["ReturnValue"], set_target["LockTarget"])
L(set_target["then"], set_locked_t["execute"])
L(set_locked_t["then"], orient_off["execute"])
L(orient_off["then"], desired_on["execute"])
L(cmc1["CharacterMovement"], orient_off["self"])
L(cmc1["CharacterMovement"], desired_on["self"])

# ---------------- release (shared by toggle and tick) ----------------
rel_target = g.set("RelTarget", "LockTarget", 700, -100, "object", obj=ACTOR)
rel_locked = g.set("RelLocked", "IsLockedOn", 960, -100, "bool", value="false")
cmc2 = g.get("CMC2", "CharacterMovement", 1220, -10, "object", obj=ENGINE.format(CMC), owner="Character")
orient_on = g.set("OrientOn", "bOrientRotationToMovement", 1500, -100, "bool", owner=CMC, value="true")
desired_off = g.set("DesiredOff", "bUseControllerDesiredRotation", 1800, -100, "bool", owner=CMC, value="false")
L(br_toggle["then"], rel_target["execute"])
L(rel_target["then"], rel_locked["execute"])
L(rel_locked["then"], orient_on["execute"])
L(orient_on["then"], desired_off["execute"])
L(cmc2["CharacterMovement"], orient_on["self"])
L(cmc2["CharacterMovement"], desired_off["self"])

# ---------------- every frame while locked ----------------
Y = 700
tick = g.event("Tick", "Actor", "ReceiveTick", 0, Y, outs=[("DeltaSeconds", "real", "float")])
is_locked2 = g.get("IsLocked2", "IsLockedOn", 0, Y + 160, "bool")
tick_seq = g.seq("Tick", 120, Y + 300)  # then_0 lock-on, then_1 free for other per-frame work
L(tick["then"], tick_seq["execute"])
br_tick = g.branch("Tick", 260, Y)
L(tick_seq["then_0"], br_tick["execute"])
L(is_locked2["IsLockedOn"], br_tick["Condition"])

tgt = g.get("Target1", "LockTarget", 260, Y + 260, "object", obj=ACTOR)
t_valid = (g.call("TValid", "KismetSystemLibrary", "IsValid", 520, Y + 200, pure=True)
           .pin("Object", cat="object").pin("ReturnValue", out=True, cat="bool"))
dist = (g.call("Dist", "Actor", "GetDistanceTo", 520, Y + 300, pure=True)
        .pin("OtherActor", cat="object", obj=ACTOR).pin("ReturnValue", out=True, cat="real", sub="float"))
near_enough = (g.call("Near", "KismetMathLibrary", "LessEqual_DoubleDouble", 760, Y + 300, pure=True)
               .pin("A", cat="real", sub="double").pin("B", cat="real", sub="double", default=f"{BREAK_RANGE:.6f}")
               .pin("ReturnValue", out=True, cat="bool"))
keep_and = (g.call("KeepAnd", "KismetMathLibrary", "BooleanAND", 980, Y + 240, pure=True)
            .pin("A", cat="bool").pin("B", cat="bool").pin("ReturnValue", out=True, cat="bool"))
br_keep = g.branch("Keep", 1200, Y)
L(br_tick["then"], br_keep["execute"])
L(tgt["LockTarget"], t_valid["Object"])
L(tgt["LockTarget"], dist["OtherActor"])
L(dist["ReturnValue"], near_enough["A"])
L(t_valid["ReturnValue"], keep_and["A"])
L(near_enough["ReturnValue"], keep_and["B"])
L(keep_and["ReturnValue"], br_keep["Condition"])
L(br_keep["else"], rel_target["execute"])   # target gone or too far: let go

self_loc2 = g.call("SelfLoc2", "Actor", "K2_GetActorLocation", 1200, Y + 420, pure=True).pin(
    "ReturnValue", out=True, cat="struct", obj=VEC)
tgt_loc = g.call("TgtLoc", "Actor", "K2_GetActorLocation", 1200, Y + 540, pure=True).pin(
    "ReturnValue", out=True, cat="struct", obj=VEC)
L(tgt["LockTarget"], tgt_loc["self"])
look = (g.call("Look", "KismetMathLibrary", "FindLookAtRotation", 1460, Y + 460, pure=True)
        .pin("Start", cat="struct", obj=VEC).pin("Target", cat="struct", obj=VEC)
        .pin("ReturnValue", out=True, cat="struct", obj=ROT))
L(self_loc2["ReturnValue"], look["Start"])
L(tgt_loc["ReturnValue"], look["Target"])
brk = (g.call("Break", "KismetMathLibrary", "BreakRotator", 1740, Y + 460, pure=True)
       .pin("InRot", cat="struct", obj=ROT).pin("Yaw", out=True, cat="real", sub="float"))
L(look["ReturnValue"], brk["InRot"])
make = (g.call("Make", "KismetMathLibrary", "MakeRotator", 1980, Y + 440, pure=True)
        .pin("Roll", cat="real", sub="float", default="0.000000")
        .pin("Pitch", cat="real", sub="float", default=f"{CAM_PITCH:.6f}")
        .pin("Yaw", cat="real", sub="float")
        .pin("ReturnValue", out=True, cat="struct", obj=ROT))
L(brk["Yaw"], make["Yaw"])
ctrl_rot = g.call("CtrlRot", "Pawn", "GetControlRotation", 1980, Y + 300, pure=True).pin(
    "ReturnValue", out=True, cat="struct", obj=ROT)
interp = (g.call("Interp", "KismetMathLibrary", "RInterpTo", 2240, Y + 300, pure=True)
          .pin("Current", cat="struct", obj=ROT).pin("Target", cat="struct", obj=ROT)
          .pin("DeltaTime", cat="real", sub="float")
          .pin("InterpSpeed", cat="real", sub="float", default=f"{TURN_SPEED:.6f}")
          .pin("ReturnValue", out=True, cat="struct", obj=ROT))
L(ctrl_rot["ReturnValue"], interp["Current"])
L(make["ReturnValue"], interp["Target"])
L(tick["DeltaSeconds"], interp["DeltaTime"])
get_ctrl = g.call("GetCtrl", "Pawn", "GetController", 2240, Y + 160, pure=True).pin(
    "ReturnValue", out=True, cat="object", obj=ENGINE.format("Controller"))
set_ctrl = (g.call("SetCtrl", "Controller", "SetControlRotation", 2540, Y)
            .pin("NewRotation", cat="struct", obj=ROT))
L(br_keep["then"], set_ctrl["execute"])
L(get_ctrl["ReturnValue"], set_ctrl["self"])
L(interp["ReturnValue"], set_ctrl["NewRotation"])

