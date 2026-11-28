"""Builds Wolf_AI_Nodes.txt: the wolf's brain, pasted into BP_Wolf's Event Graph.

A port of the 2D prototype wolf (scripts/wolf.gd) to 3D. States:
  idle      waits until Arthur comes within AGGRO
  approach  runs at Arthur (a little faster than his run)
  circle    circles him at CIRCLE_R; after CIRCLE_MIN s may take an attack token
  telegraph stops, faces him, crouches and turns red for TELEGRAPH s (the "dodge now!" cue)
  lunge     leaps at him; one bite (1 damage) if it reaches him
  recover   stands still RECOVER s, then circles the other way
  stagger   knocked back when hit, STAGGER s
  dying     dark, removed after 0.7 s
Attack tokens: at most MAX_ATTACKERS wolves telegraph/lunge at once. The count lives on
Arthur (BP_Arthur.AttackersNow), so any number of wolves share it.

Distances from the 2D wolf at ~53 px per metre (Arthur's sprite height), speeds relative
to Arthur's run (500 cm/s in BP_Arthur).
Run: python gen_wolf_nodes.py -> Wolf_AI_Nodes.txt
"""
import os
from t3d import G, Node

ARTHUR = "/Game/Characters/ArthurPipeline/BP_Arthur.BP_Arthur_C"
MAX_HP = 4.0            # sword hits: 1 + 1 + 2 -> one full combo finishes a wolf
AGGRO = 1800.0          # cm: notices Arthur
CIRCLE_ENTER = 320.0    # cm: from approach to circling (2D 170 px)
CIRCLE_R = 280.0        # cm: circling distance (2D 150 px)
CIRCLE_LEAVE = 490.0    # cm: back to approach (2D 260 px)
CIRCLE_SCALE = 0.46     # circling speed / run speed (2D 90 vs 150+)
CIRCLE_MIN = 0.9        # s circling before it may attack
MAX_ATTACKERS = 2
TELEGRAPH = 0.65        # s
LUNGE_SPEED = 1180.0    # cm/s forward (2D 620 px/s for 0.28 s = ~3.3 m)
LUNGE_UP = 160.0        # cm/s upward: a short leap
LUNGE_TIME = 0.45       # s until it counts as landed
BITE_RANGE = 100.0      # cm
RECOVER = 0.8
STAGGER = 0.35
KNOCKBACK = 650.0
GREY, RED, WHITE, DARK = (0.42, 0.42, 0.46), (0.75, 0.3, 0.3), (1, 1, 1), (0.08, 0.08, 0.09)

g = G("Wolf")
L = g.link
STATES = ["idle", "approach", "circle", "telegraph", "lunge", "recover", "stagger", "dying"]

g.comment("Box", -120, -200, 5600, 2700,
          "Wolf brain (port of the 2D wolf): idle > approach > circle > telegraph (crouch, red) > lunge > recover; "
          "stagger when hit; 4 damage defeats it. Attack tokens on BP_Arthur.AttackersNow (max 2 attackers).")

# ---------- shared values (pure) ----------
pc = g.fn("PC", "GameplayStatics", "GetPlayerCharacter", 0, 1500, {"PlayerIndex": ("i", 0)}, {"ReturnValue": "o:Character"})
self_loc = g.fn("SelfLoc", "Actor", "K2_GetActorLocation", 0, 1650, outs={"ReturnValue": "v"})
pc_loc = g.fn("PcLoc", "Actor", "K2_GetActorLocation", 260, 1500, outs={"ReturnValue": "v"})
L(pc["ReturnValue"], pc_loc["self"])
to = g.math("To", "Subtract_VectorVector", 500, 1550, {"A": "v", "B": "v"}, "v")
L(pc_loc["ReturnValue"], to["A"]); L(self_loc["ReturnValue"], to["B"])
flat = g.math("Flat", "Multiply_VectorVector", 720, 1550, {"A": "v", "B": ("v", (1, 1, 0))}, "v")
L(to["ReturnValue"], flat["A"])
dist = g.math("Dist", "VSize", 940, 1500, {"A": "v"}, "d")
L(flat["ReturnValue"], dist["A"])
dirv = g.math("Dir", "Normal", 940, 1620, {"A": "v", "Tolerance": ("f", 0.0001)}, "v")
L(flat["ReturnValue"], dirv["A"])
arthur = g.cast("Arthur", ARTHUR, "BP Arthur", 260, 1760)
L(pc["ReturnValue"], arthur["Object"])
attackers = g.var("Attackers", "AttackersNow", "i", 520, 1760, owner_bp=ARTHUR)
L(arthur["AsBP Arthur"], attackers["self"])
t_get = g.var("T", "T", "f", 0, 1850)
hold_get = g.var("Hold", "HoldingToken", "b", 0, 1950)
cms = g.get("CMC", "CharacterMovement", 0, 2050, "object", owner="Character")
visual = g.var("Visual", "Visual", "o:SceneComponent", 0, 2150)
body = g.var("Body", "Body", "o:StaticMeshComponent", 0, 2250)


def gt(tag, a_pin, b, x, y, op="Greater_DoubleDouble"):
    n = g.math(tag, op, x, y, {"A": "d", "B": ("d", b)}, "b")
    L(a_pin, n["A"])
    return n


def to_state(tag, name, x, y):
    s = g.setv(f"S{tag}", "State", "n", x, y, value=name)
    t = g.setv(f"T{tag}", "T", "f", x + 260, y, value=0.0)
    L(s["then"], t["execute"])
    return s, t


def color(tag, rgb, x, y):
    n = g.fn(tag, "PrimitiveComponent", "SetVectorParameterValueOnMaterials", x, y,
             {"ParameterName": ("n", "Color"), "ParameterValue": ("v", rgb)}, pure=False)
    L(body["Body"], n["self"])
    return n


def crouch(tag, z, x, y):
    n = g.fn(tag, "SceneComponent", "K2_SetRelativeLocation", x, y, {"NewLocation": ("v", (0, 0, z))}, pure=False)
    L(visual["Visual"], n["self"])
    return n


def release_token(tag, x, y):
    """Branch(HoldingToken) -> HoldingToken=false -> AttackersNow=max(n-1,0). Returns (entry, [exits])."""
    br = g.branch(f"Rel{tag}", x, y)
    L(hold_get["HoldingToken"], br["Condition"])
    off = g.setv(f"HoldOff{tag}", "HoldingToken", "b", x + 260, y, value=False)
    minus = g.fn(f"Minus{tag}", "KismetMathLibrary", "Subtract_IntInt", x + 260, y + 160,
                 {"A": "i", "B": ("i", 1)}, {"ReturnValue": "i"})
    clamp = g.fn(f"Clamp{tag}", "KismetMathLibrary", "Max", x + 480, y + 160,
                 {"A": "i", "B": ("i", 0)}, {"ReturnValue": "i"})
    put = g.setv(f"Tok{tag}", "AttackersNow", "i", x + 520, y, owner_bp=ARTHUR)
    L(attackers["AttackersNow"], minus["A"]); L(minus["ReturnValue"], clamp["A"])
    L(clamp["ReturnValue"], put["AttackersNow"]); L(arthur["AsBP Arthur"], put["self"])
    L(br["then"], off["execute"]); L(off["then"], put["execute"])
    return br, [br["else"], put["then"]]


# ---------- tick ----------
tick = g.event("Tick", "Actor", "ReceiveTick", 0, 0, outs=[("DeltaSeconds", "real", "float")])
sq = g.seq("Tick", 220, 0)
L(tick["then"], sq["execute"])
add_t = g.math("AddT", "Add_DoubleDouble", 220, 160, {"A": "d", "B": "d"}, "d")
L(t_get["T"], add_t["A"]); L(tick["DeltaSeconds"], add_t["B"])
set_t = g.setv("TickT", "T", "f", 460, -80)
L(add_t["ReturnValue"], set_t["T"]); L(sq["then_0"], set_t["execute"])
state_get = g.var("State", "State", "n", 220, 260)
sw = g.switch_name("State", 460, 60, STATES)
L(sq["then_1"], sw["execute"]); L(state_get["State"], sw["Selection"])

# Default (first frame): pick a circling side, go idle
rb = g.fn("RandBool", "KismetMathLibrary", "RandomBool", 700, -260, outs={"ReturnValue": "b"})
sel = g.math("Side", "SelectFloat", 900, -260, {"A": ("d", 1.0), "B": ("d", -1.0), "bPickA": "b"}, "d")
L(rb["ReturnValue"], sel["bPickA"])
set_side = g.setv("Side", "CircleSign", "f", 1100, -200)
L(sel["ReturnValue"], set_side["CircleSign"])
s_idle0, t_idle0 = to_state("Idle0", "idle", 1360, -200)
L(sw["Default"], set_side["execute"]); L(set_side["then"], s_idle0["execute"])

X = 800
# idle -> approach when Arthur is near
br_idle = g.branch("Idle", X, 80)
L(sw["idle"], br_idle["execute"])
L(gt("Aggro", dist["ReturnValue"], AGGRO, X, 220, "Less_DoubleDouble")["ReturnValue"], br_idle["Condition"])
s_appr, _ = to_state("Appr", "approach", X + 260, 80)
L(br_idle["then"], s_appr["execute"])

# approach: run at him; close enough -> circle
Y = 380
run = g.fn("Run", "Pawn", "AddMovementInput", X, Y, {"WorldDirection": "v", "ScaleValue": ("f", 1.0)}, pure=False)
L(sw["approach"], run["execute"]); L(dirv["ReturnValue"], run["WorldDirection"])
br_close = g.branch("Close", X + 300, Y)
L(run["then"], br_close["execute"])
L(gt("Close", dist["ReturnValue"], CIRCLE_ENTER, X + 300, Y + 140, "Less_DoubleDouble")["ReturnValue"], br_close["Condition"])
s_circ1, _ = to_state("Circ1", "circle", X + 560, Y)
L(br_close["then"], s_circ1["execute"])

# circle: sideways + spring toward CIRCLE_R; too far -> approach; ready -> telegraph
Y = 700
up = g.math("Cross", "Cross_VectorVector", X, Y + 160, {"A": "v", "B": ("v", (0, 0, 1))}, "v")
L(dirv["ReturnValue"], up["A"])
side_get = g.var("SideGet", "CircleSign", "f", X, Y + 300)
tan = g.math("Tan", "Multiply_VectorFloat", X + 220, Y + 160, {"A": "v", "B": "d"}, "v")
L(up["ReturnValue"], tan["A"]); L(side_get["CircleSign"], tan["B"])
off_r = g.math("OffR", "Subtract_DoubleDouble", X + 220, Y + 300, {"A": "d", "B": ("d", CIRCLE_R)}, "d")
L(dist["ReturnValue"], off_r["A"])
k_r = g.math("KR", "Multiply_DoubleDouble", X + 440, Y + 300, {"A": "d", "B": ("d", 0.01)}, "d")
L(off_r["ReturnValue"], k_r["A"])
rad = g.math("Rad", "Multiply_VectorFloat", X + 660, Y + 300, {"A": "v", "B": "d"}, "v")
L(dirv["ReturnValue"], rad["A"]); L(k_r["ReturnValue"], rad["B"])
mix = g.math("Mix", "Add_VectorVector", X + 880, Y + 200, {"A": "v", "B": "v"}, "v")
L(tan["ReturnValue"], mix["A"]); L(rad["ReturnValue"], mix["B"])
mixn = g.math("MixN", "Normal", X + 1080, Y + 200, {"A": "v", "Tolerance": ("f", 0.0001)}, "v")
L(mix["ReturnValue"], mixn["A"])
circ = g.fn("Circ", "Pawn", "AddMovementInput", X + 1280, Y, {"WorldDirection": "v", "ScaleValue": ("f", CIRCLE_SCALE)}, pure=False)
L(sw["circle"], circ["execute"]); L(mixn["ReturnValue"], circ["WorldDirection"])
br_far = g.branch("Far", X + 1580, Y)
L(circ["then"], br_far["execute"])
L(gt("Far", dist["ReturnValue"], CIRCLE_LEAVE, X + 1580, Y + 140)["ReturnValue"], br_far["Condition"])
s_appr2, _ = to_state("Appr2", "approach", X + 1840, Y - 120)
L(br_far["then"], s_appr2["execute"])
ready_t = gt("ReadyT", t_get["T"], CIRCLE_MIN, X + 1840, Y + 300)
free = g.fn("Free", "KismetMathLibrary", "Less_IntInt", X + 1840, Y + 420, {"A": "i", "B": ("i", MAX_ATTACKERS)}, {"ReturnValue": "b"})
L(attackers["AttackersNow"], free["A"])
ready = g.math("Ready", "BooleanAND", X + 2060, Y + 340, {"A": "b", "B": "b"}, "b")
L(ready_t["ReturnValue"], ready["A"]); L(free["ReturnValue"], ready["B"])
br_ready = g.branch("Ready", X + 1840, Y + 60)
L(br_far["else"], br_ready["execute"]); L(ready["ReturnValue"], br_ready["Condition"])
# enter telegraph: take token, stop, crouch, red
plus = g.fn("Plus", "KismetMathLibrary", "Add_IntInt", X + 2100, Y + 180, {"A": "i", "B": ("i", 1)}, {"ReturnValue": "i"})
L(attackers["AttackersNow"], plus["A"])
take = g.setv("Take", "AttackersNow", "i", X + 2100, Y + 40, owner_bp=ARTHUR)
L(plus["ReturnValue"], take["AttackersNow"]); L(arthur["AsBP Arthur"], take["self"])
hold_on = g.setv("HoldOn", "HoldingToken", "b", X + 2380, Y + 40, value=True)
stop = g.fn("Stop", "MovementComponent", "StopMovementImmediately", X + 2640, Y + 40, pure=False)
L(cms["CharacterMovement"], stop["self"])
down = crouch("Down", -12, X + 2900, Y + 40)
red = color("Red", RED, X + 3200, Y + 40)
s_tel, _ = to_state("Tel", "telegraph", X + 3500, Y + 40)
L(br_ready["then"], take["execute"])
g.chain(take, hold_on, stop, down, red, s_tel)

# telegraph: face him; after TELEGRAPH -> leap
Y = 1100
face_rot = g.math("FaceRot", "Conv_VectorToRotator", X, Y + 160, {"InVec": "v"}, "r")
L(dirv["ReturnValue"], face_rot["InVec"])
face = g.fn("Face", "Actor", "K2_SetActorRotation", X + 220, Y, {"NewRotation": "r", "bTeleportPhysics": ("b", False)},
            {"ReturnValue": "b"}, pure=False)
L(sw["telegraph"], face["execute"]); L(face_rot["ReturnValue"], face["NewRotation"])
br_go = g.branch("Go", X + 520, Y)
L(face["then"], br_go["execute"])
L(gt("GoT", t_get["T"], TELEGRAPH, X + 520, Y + 140, "GreaterEqual_DoubleDouble")["ReturnValue"], br_go["Condition"])
fwd = g.math("LFwd", "Multiply_VectorFloat", X + 760, Y + 180, {"A": "v", "B": ("d", LUNGE_SPEED)}, "v")
L(dirv["ReturnValue"], fwd["A"])
leapv = g.math("LUp", "Add_VectorVector", X + 980, Y + 180, {"A": "v", "B": ("v", (0, 0, LUNGE_UP))}, "v")
L(fwd["ReturnValue"], leapv["A"])
leap = g.fn("Leap", "Character", "LaunchCharacter", X + 780, Y,
            {"LaunchVelocity": "v", "bXYOverride": ("b", True), "bZOverride": ("b", True)}, pure=False)
L(leapv["ReturnValue"], leap["LaunchVelocity"])
hit_off = g.setv("HitOff", "HitPlayer", "b", X + 1080, Y, value=False)
stand = crouch("Stand", 0, X + 1340, Y)
grey = color("Grey1", GREY, X + 1640, Y)
s_lun, _ = to_state("Lun", "lunge", X + 1940, Y)
L(br_go["then"], leap["execute"])
g.chain(leap, hit_off, stand, grey, s_lun)

# lunge: bite once if close; after LUNGE_TIME -> give token back, recover
Y = 1500 + 300
X2 = 1400
hit_get = g.var("HitGet", "HitPlayer", "b", X2, Y + 200)
not_hit = g.math("NotHit", "Not_PreBool", X2 + 200, Y + 200, {"A": "b"}, "b")
L(hit_get["HitPlayer"], not_hit["A"])
near = gt("Bite", dist["ReturnValue"], BITE_RANGE, X2 + 200, Y + 300, "Less_DoubleDouble")
can_bite = g.math("CanBite", "BooleanAND", X2 + 420, Y + 240, {"A": "b", "B": "b"}, "b")
L(not_hit["ReturnValue"], can_bite["A"]); L(near["ReturnValue"], can_bite["B"])
br_bite = g.branch("Bite", X2 + 640, Y)
L(sw["lunge"], br_bite["execute"]); L(can_bite["ReturnValue"], br_bite["Condition"])
hit_on = g.setv("HitOn", "HitPlayer", "b", X2 + 900, Y, value=True)
self_ref = Node(g, "/Script/BlueprintGraph.K2Node_Self", "K2Node_Self_WolfMe", X2 + 900, Y + 200)
self_ref.pin("self", out=True, cat="object")
bite = g.fn("BiteDmg", "GameplayStatics", "ApplyDamage", X2 + 1160, Y,
            {"DamagedActor": "o:Actor", "BaseDamage": ("f", 1.0), "DamageCauser": "o:Actor"}, {"ReturnValue": "f"}, pure=False)
L(pc["ReturnValue"], bite["DamagedActor"]); L(self_ref["self"], bite["DamageCauser"])
L(br_bite["then"], hit_on["execute"]); L(hit_on["then"], bite["execute"])
br_land = g.branch("Land", X2 + 1460, Y)
L(bite["then"], br_land["execute"]); L(br_bite["else"], br_land["execute"])
L(gt("LandT", t_get["T"], LUNGE_TIME, X2 + 1460, Y + 140, "GreaterEqual_DoubleDouble")["ReturnValue"], br_land["Condition"])
rel1, rel1_out = release_token("1", X2 + 1720, Y)
L(br_land["then"], rel1["execute"])
s_rec, _ = to_state("Rec", "recover", X2 + 2560, Y)
for p in rel1_out:
    L(p, s_rec["execute"])

# recover: wait, then circle the other way
Y = 2150
br_rec = g.branch("Rec", X2, Y)
L(sw["recover"], br_rec["execute"])
L(gt("RecT", t_get["T"], RECOVER, X2, Y + 140, "GreaterEqual_DoubleDouble")["ReturnValue"], br_rec["Condition"])
flip = g.math("Flip", "Multiply_DoubleDouble", X2 + 260, Y + 160, {"A": "d", "B": ("d", -1.0)}, "d")
L(side_get["CircleSign"], flip["A"])
set_flip = g.setv("Flip", "CircleSign", "f", X2 + 260, Y)
L(flip["ReturnValue"], set_flip["CircleSign"])
s_circ2, _ = to_state("Circ2", "circle", X2 + 520, Y)
L(br_rec["then"], set_flip["execute"]); L(set_flip["then"], s_circ2["execute"])

# stagger: wait, back to normal colour, circle
br_stg = g.branch("Stg", X2 + 1200, Y)
L(sw["stagger"], br_stg["execute"])
L(gt("StgT", t_get["T"], STAGGER, X2 + 1200, Y + 140, "GreaterEqual_DoubleDouble")["ReturnValue"], br_stg["Condition"])
grey2 = color("Grey2", GREY, X2 + 1460, Y)
s_circ3, _ = to_state("Circ3", "circle", X2 + 1760, Y)
L(br_stg["then"], grey2["execute"]); L(grey2["then"], s_circ3["execute"])

# ---------- taking a hit ----------
Y = -700
ev = g.event("Dmg", "Actor", "ReceiveAnyDamage", 0, Y,
             outs=[("Damage", "real", "float"), ("DamageType", "object", ""), ("InstigatedBy", "object", ""),
                   ("DamageCauser", "object", "")])
is_dying = g.fn("IsDying", "KismetMathLibrary", "EqualEqual_NameName", 220, Y + 160,
                {"A": "n", "B": ("n", "dying")}, {"ReturnValue": "b"})
L(state_get["State"], is_dying["A"])
br_alive = g.branch("Alive", 260, Y)
L(ev["then"], br_alive["execute"]); L(is_dying["ReturnValue"], br_alive["Condition"])
dmg_get = g.var("DmgGet", "DamageTaken", "f", 500, Y + 200)
dmg_add = g.math("DmgAdd", "Add_DoubleDouble", 700, Y + 200, {"A": "d", "B": "d"}, "d")
L(dmg_get["DamageTaken"], dmg_add["A"]); L(ev["Damage"], dmg_add["B"])
dmg_set = g.setv("Dmg", "DamageTaken", "f", 520, Y)
L(dmg_add["ReturnValue"], dmg_set["DamageTaken"]); L(br_alive["else"], dmg_set["execute"])
causer_loc = g.fn("CauserLoc", "Actor", "K2_GetActorLocation", 760, Y + 340, outs={"ReturnValue": "v"})
L(ev["DamageCauser"], causer_loc["self"])
away = g.math("Away", "Subtract_VectorVector", 980, Y + 340, {"A": "v", "B": "v"}, "v")
L(self_loc["ReturnValue"], away["A"]); L(causer_loc["ReturnValue"], away["B"])
away_f = g.math("AwayF", "Multiply_VectorVector", 1180, Y + 340, {"A": "v", "B": ("v", (1, 1, 0))}, "v")
L(away["ReturnValue"], away_f["A"])
away_n = g.math("AwayN", "Normal", 1380, Y + 340, {"A": "v", "Tolerance": ("f", 0.0001)}, "v")
L(away_f["ReturnValue"], away_n["A"])
away_k = g.math("AwayK", "Multiply_VectorFloat", 1580, Y + 340, {"A": "v", "B": ("d", KNOCKBACK)}, "v")
L(away_n["ReturnValue"], away_k["A"])
away_up = g.math("AwayUp", "Add_VectorVector", 1780, Y + 340, {"A": "v", "B": ("v", (0, 0, 150))}, "v")
L(away_k["ReturnValue"], away_up["A"])
knock = g.fn("Knock", "Character", "LaunchCharacter", 800, Y,
             {"LaunchVelocity": "v", "bXYOverride": ("b", True), "bZOverride": ("b", True)}, pure=False)
L(away_up["ReturnValue"], knock["LaunchVelocity"])
flash = color("Flash", WHITE, 1100, Y)
stand2 = crouch("Stand2", 0, 1400, Y)
g.chain(dmg_set, knock, flash, stand2)
rel2, rel2_out = release_token("2", 1700, Y)
L(stand2["then"], rel2["execute"])
dead_q = gt("Dead", dmg_add["ReturnValue"], MAX_HP, 2500, Y + 160, "GreaterEqual_DoubleDouble")
br_dead = g.branch("Dead", 2500, Y)
for p in rel2_out:
    L(p, br_dead["execute"])
L(dead_q["ReturnValue"], br_dead["Condition"])
s_die, t_die = to_state("Die", "dying", 2760, Y - 120)
dark = color("Dark", DARK, 3300, Y - 120)
life = g.fn("Life", "Actor", "SetLifeSpan", 3600, Y - 120, {"InLifespan": ("f", 0.7)}, pure=False)
L(br_dead["then"], s_die["execute"])
g.chain(t_die, dark, life)
s_stg, _ = to_state("Stg", "stagger", 2760, Y + 120)
L(br_dead["else"], s_stg["execute"])

if __name__ == "__main__":
    nodes, links = g.check()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Wolf_AI_Nodes.txt")
    with open(out, "w", newline="") as f:
        f.write(g.dump())
    print(f"{nodes} nodes, {links} links -> {out} ({os.path.getsize(out)} bytes)")
