"""Builds Arthur_Combat_Nodes.txt for BP_Arthur's Event Graph: lock-on + sword hits + taking hits.

- Lock-on: see gen_lockon_nodes.py (Tab / gamepad Left Trigger).
- Sword hits: while a combo montage plays, once per swing inside its hit window, the nearest
  actor tagged "Enemy" within REACH and in front of Arthur takes the swing's damage
  (hit 1: 1, hit 2: 1, hit 3: 2). Windows are in montage time (seconds), tune after a test.
- Taking hits: wolf bites (Apply Damage) count up DamageTaken; a short knockback; at
  MAX_HEALTH the level restarts. Ignored during the first part of the dodge roll (i-frames).
Needs BP_Arthur variables (added by ue_arthur_combat_setup.py): LockTarget, IsLockedOn,
AttackersNow, SwingDone1..3, PendingDamage, DamageTaken.
Run: python gen_arthur_combat_nodes.py -> Arthur_Combat_Nodes.txt
"""
import os

from gen_lockon_nodes import g, tick_seq
from t3d import Node

L = g.link
COMBAT = "/Game/Characters/ArthurPipeline/Combat"
ROLL = "/Game/Characters/ArthurPipeline/Moves/AM_SprintRoll.AM_SprintRoll"
SWINGS = [  # montage, hit window start, end (montage seconds), damage
    ("AM_Combo1", 0.20, 0.42, 1.0),
    ("AM_Combo2", 0.12, 0.32, 1.0),
    ("AM_Combo3", 0.85, 1.25, 2.0),
]
REACH = 230.0         # cm between Arthur and the enemy's centre
FRONT = 0.3           # how far in front (dot product; 0.3 ~ within 70 degrees either side)
IFRAMES = 0.55        # montage seconds of the roll that can't be hit (~0.46 s at rate 1.2)
MAX_HEALTH = 6.0      # bites before restart (3 hearts in halves, placeholder)
KNOCK = 400.0

X0, Y0 = 0, 1700
g.comment("Combat", X0 - 80, Y0 - 140, 4200, 1500,
          "Sword hits (once per swing, in the swing's hit window, to the nearest Enemy in front within 2.3 m) "
          "and taking hits (roll = no damage in its first half; 6 bites restarts the level).")

mesh = g.get("CbMesh", "Mesh", X0, Y0 + 300, "object", owner="Character")
anim = g.fn("CbAnim", "SkeletalMeshComponent", "GetAnimInstance", X0 + 200, Y0 + 300, outs={"ReturnValue": "o:AnimInstance"})
L(mesh["Mesh"], anim["self"])
seq = g.seq("Swings", X0 + 260, Y0, n=3)
L(tick_seq["then_1"], seq["execute"])

# shared sweep: nearest enemy, in reach and in front -> Apply Damage(PendingDamage)
SX = X0 + 2300
tagged = g.fn("CbTagged", "GameplayStatics", "GetAllActorsWithTag", SX, Y0,
              {"Tag": ("n", "Enemy")}, {"OutActors": "a:Actor"}, pure=False)
self_loc = g.fn("CbSelfLoc", "Actor", "K2_GetActorLocation", SX, Y0 + 200, outs={"ReturnValue": "v"})
nearest = g.fn("CbNearest", "GameplayStatics", "FindNearestActor", SX + 300, Y0,
               {"Origin": "v", "ActorsToCheck": "a:Actor"}, {"Distance": "f", "ReturnValue": "o:Actor"}, pure=False)
L(tagged["then"], nearest["execute"]); L(tagged["OutActors"], nearest["ActorsToCheck"])
L(self_loc["ReturnValue"], nearest["Origin"])
valid = g.fn("CbValid", "KismetSystemLibrary", "IsValid", SX + 600, Y0 + 200, {"Object": "o"}, {"ReturnValue": "b"})
L(nearest["ReturnValue"], valid["Object"])
in_reach = g.math("CbReach", "LessEqual_DoubleDouble", SX + 600, Y0 + 300, {"A": "d", "B": ("d", REACH)}, "b")
L(nearest["Distance"], in_reach["A"])
e_loc = g.fn("CbELoc", "Actor", "K2_GetActorLocation", SX + 300, Y0 + 400, outs={"ReturnValue": "v"})
L(nearest["ReturnValue"], e_loc["self"])
to_e = g.math("CbToE", "Subtract_VectorVector", SX + 520, Y0 + 420, {"A": "v", "B": "v"}, "v")
L(e_loc["ReturnValue"], to_e["A"]); L(self_loc["ReturnValue"], to_e["B"])
to_ef = g.math("CbToEF", "Multiply_VectorVector", SX + 720, Y0 + 420, {"A": "v", "B": ("v", (1, 1, 0))}, "v")
L(to_e["ReturnValue"], to_ef["A"])
to_en = g.math("CbToEN", "Normal", SX + 920, Y0 + 420, {"A": "v", "Tolerance": ("f", 0.0001)}, "v")
L(to_ef["ReturnValue"], to_en["A"])
fwd = g.fn("CbFwd", "Actor", "GetActorForwardVector", SX + 920, Y0 + 540, outs={"ReturnValue": "v"})
dot = g.math("CbDot", "Dot_VectorVector", SX + 1120, Y0 + 460, {"A": "v", "B": "v"}, "d")
L(fwd["ReturnValue"], dot["A"]); L(to_en["ReturnValue"], dot["B"])
in_front = g.math("CbFront", "GreaterEqual_DoubleDouble", SX + 1320, Y0 + 460, {"A": "d", "B": ("d", FRONT)}, "b")
L(dot["ReturnValue"], in_front["A"])
and1 = g.math("CbAnd1", "BooleanAND", SX + 900, Y0 + 240, {"A": "b", "B": "b"}, "b")
L(valid["ReturnValue"], and1["A"]); L(in_reach["ReturnValue"], and1["B"])
and2 = g.math("CbAnd2", "BooleanAND", SX + 1500, Y0 + 300, {"A": "b", "B": "b"}, "b")
L(and1["ReturnValue"], and2["A"]); L(in_front["ReturnValue"], and2["B"])
br_hit = g.branch("CbHit", SX + 1500, Y0)
L(nearest["then"], br_hit["execute"]); L(and2["ReturnValue"], br_hit["Condition"])
me = Node(g, "/Script/BlueprintGraph.K2Node_Self", "K2Node_Self_CbMe", SX + 1500, Y0 + 640)
me.pin("self", out=True, cat="object")
pend = g.var("CbPend", "PendingDamage", "f", SX + 1500, Y0 + 520)
dmg = g.fn("CbDamage", "GameplayStatics", "ApplyDamage", SX + 1760, Y0,
           {"DamagedActor": "o:Actor", "BaseDamage": "f", "DamageCauser": "o:Actor"}, {"ReturnValue": "f"}, pure=False)
L(br_hit["then"], dmg["execute"]); L(nearest["ReturnValue"], dmg["DamagedActor"])
L(pend["PendingDamage"], dmg["BaseDamage"]); L(me["self"], dmg["DamageCauser"])

# one checker per swing
for i, (am, a, b, d) in enumerate(SWINGS, start=1):
    y = Y0 + (i - 1) * 380
    x = X0 + 520
    path = f"{COMBAT}/{am}.{am}"
    playing = g.fn(f"CbPlay{i}", "AnimInstance", "Montage_IsPlaying", x, y + 160, {"Montage": "o:AnimMontage"}, {"ReturnValue": "b"})
    playing["Montage"].default_object = path
    pos = g.fn(f"CbPos{i}", "AnimInstance", "Montage_GetPosition", x, y + 260, {"Montage": "o:AnimMontage"}, {"ReturnValue": "f"})
    pos["Montage"].default_object = path
    L(anim["ReturnValue"], playing["self"]); L(anim["ReturnValue"], pos["self"])
    br_play = g.branch(f"CbPlay{i}", x + 260, y)
    L(seq[f"then_{i - 1}"], br_play["execute"]); L(playing["ReturnValue"], br_play["Condition"])
    early = g.math(f"CbEarly{i}", "Less_DoubleDouble", x + 520, y + 160, {"A": "d", "B": ("d", a)}, "b")
    L(pos["ReturnValue"], early["A"])
    br_early = g.branch(f"CbEarly{i}", x + 520, y)
    L(br_play["then"], br_early["execute"]); L(early["ReturnValue"], br_early["Condition"])
    reset = g.setv(f"CbReset{i}", f"SwingDone{i}", "b", x + 780, y - 80, value=False)
    L(br_early["then"], reset["execute"])
    late = g.math(f"CbLate{i}", "LessEqual_DoubleDouble", x + 780, y + 260, {"A": "d", "B": ("d", b)}, "b")
    L(pos["ReturnValue"], late["A"])
    done = g.var(f"CbDone{i}", f"SwingDone{i}", "b", x + 780, y + 360)
    not_done = g.math(f"CbNotDone{i}", "Not_PreBool", x + 980, y + 360, {"A": "b"}, "b")
    L(done[f"SwingDone{i}"], not_done["A"])
    now = g.math(f"CbNow{i}", "BooleanAND", x + 1180, y + 300, {"A": "b", "B": "b"}, "b")
    L(late["ReturnValue"], now["A"]); L(not_done["ReturnValue"], now["B"])
    br_now = g.branch(f"CbNow{i}", x + 1040, y + 80)
    L(br_early["else"], br_now["execute"]); L(now["ReturnValue"], br_now["Condition"])
    mark = g.setv(f"CbMark{i}", f"SwingDone{i}", "b", x + 1300, y + 80, value=True)
    put = g.setv(f"CbPut{i}", "PendingDamage", "f", x + 1560, y + 80, value=d)
    L(br_now["then"], mark["execute"]); L(mark["then"], put["execute"]); L(put["then"], tagged["execute"])

# ---------- taking a hit ----------
HY = Y0 + 1250
ev = g.event("CbDmg", "Actor", "ReceiveAnyDamage", X0, HY,
             outs=[("Damage", "real", "float"), ("DamageType", "object", ""), ("InstigatedBy", "object", ""),
                   ("DamageCauser", "object", "")])
roll_play = g.fn("CbRollPlay", "AnimInstance", "Montage_IsPlaying", X0 + 220, HY + 160, {"Montage": "o:AnimMontage"}, {"ReturnValue": "b"})
roll_play["Montage"].default_object = ROLL
roll_pos = g.fn("CbRollPos", "AnimInstance", "Montage_GetPosition", X0 + 220, HY + 260, {"Montage": "o:AnimMontage"}, {"ReturnValue": "f"})
roll_pos["Montage"].default_object = ROLL
L(anim["ReturnValue"], roll_play["self"]); L(anim["ReturnValue"], roll_pos["self"])
early_roll = g.math("CbIFr", "Less_DoubleDouble", X0 + 460, HY + 260, {"A": "d", "B": ("d", IFRAMES)}, "b")
L(roll_pos["ReturnValue"], early_roll["A"])
safe = g.math("CbSafe", "BooleanAND", X0 + 660, HY + 200, {"A": "b", "B": "b"}, "b")
L(roll_play["ReturnValue"], safe["A"]); L(early_roll["ReturnValue"], safe["B"])
br_safe = g.branch("CbSafe", X0 + 300, HY)
L(ev["then"], br_safe["execute"]); L(safe["ReturnValue"], br_safe["Condition"])
taken = g.var("CbTaken", "DamageTaken", "f", X0 + 600, HY + 380)
add = g.math("CbAdd", "Add_DoubleDouble", X0 + 820, HY + 380, {"A": "d", "B": "d"}, "d")
L(taken["DamageTaken"], add["A"]); L(ev["Damage"], add["B"])
set_taken = g.setv("CbTaken", "DamageTaken", "f", X0 + 600, HY)
L(br_safe["else"], set_taken["execute"]); L(add["ReturnValue"], set_taken["DamageTaken"])
c_loc = g.fn("CbCLoc", "Actor", "K2_GetActorLocation", X0 + 860, HY + 520, outs={"ReturnValue": "v"})
L(ev["DamageCauser"], c_loc["self"])
away = g.math("CbAway", "Subtract_VectorVector", X0 + 1080, HY + 520, {"A": "v", "B": "v"}, "v")
L(self_loc["ReturnValue"], away["A"]); L(c_loc["ReturnValue"], away["B"])
away_f = g.math("CbAwayF", "Multiply_VectorVector", X0 + 1280, HY + 520, {"A": "v", "B": ("v", (1, 1, 0))}, "v")
L(away["ReturnValue"], away_f["A"])
away_n = g.math("CbAwayN", "Normal", X0 + 1480, HY + 520, {"A": "v", "Tolerance": ("f", 0.0001)}, "v")
L(away_f["ReturnValue"], away_n["A"])
away_k = g.math("CbAwayK", "Multiply_VectorFloat", X0 + 1680, HY + 520, {"A": "v", "B": ("d", KNOCK)}, "v")
L(away_n["ReturnValue"], away_k["A"])
away_up = g.math("CbAwayUp", "Add_VectorVector", X0 + 1880, HY + 520, {"A": "v", "B": ("v", (0, 0, 120))}, "v")
L(away_k["ReturnValue"], away_up["A"])
knock = g.fn("CbKnock", "Character", "LaunchCharacter", X0 + 900, HY,
             {"LaunchVelocity": "v", "bXYOverride": ("b", True), "bZOverride": ("b", True)}, pure=False)
L(away_up["ReturnValue"], knock["LaunchVelocity"]); L(set_taken["then"], knock["execute"])
say = g.fn("CbSay", "KismetSystemLibrary", "PrintString", X0 + 1200, HY,
           {"InString": ("s", "Arthur was bitten!"), "Duration": ("f", 1.5)}, pure=False)
L(knock["then"], say["execute"])
br_down = g.branch("CbDown", X0 + 1500, HY)
L(say["then"], br_down["execute"])
down = g.math("CbDownQ", "GreaterEqual_DoubleDouble", X0 + 1500, HY + 160, {"A": "d", "B": ("d", MAX_HEALTH)}, "b")
L(add["ReturnValue"], down["A"]); L(down["ReturnValue"], br_down["Condition"])
lvl = g.fn("CbLvl", "GameplayStatics", "GetCurrentLevelName", X0 + 1760, HY + 200,
           {"bRemovePrefixString": ("b", True)}, {"ReturnValue": "s"})
lvl_n = g.fn("CbLvlN", "KismetStringLibrary", "Conv_StringToName", X0 + 2000, HY + 200, {"InString": "s"}, {"ReturnValue": "n"})
L(lvl["ReturnValue"], lvl_n["InString"])
restart = g.fn("CbRestart", "GameplayStatics", "OpenLevel", X0 + 2000, HY, {"LevelName": "n"}, pure=False)
L(lvl_n["ReturnValue"], restart["LevelName"]); L(br_down["then"], restart["execute"])

if __name__ == "__main__":
    nodes, links = g.check()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Arthur_Combat_Nodes.txt")
    with open(out, "w", newline="") as f:
        f.write(g.dump())
    print(f"{nodes} nodes, {links} links -> {out} ({os.path.getsize(out)} bytes)")
