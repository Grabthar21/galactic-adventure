extends Node2D
## Story director for the opening. Follows the "Option Omega" beat sheet:
## farm life -> combat intro (wolves) -> first choice (pup) -> dinner -> the crash ->
## the Stranger and the key (willing / begrudging) -> Father's Sword -> Goblibots arrive.

const Player = preload("res://scripts/player.gd")
const Wolf = preload("res://scripts/wolf.gd")
const Prop = preload("res://scripts/prop.gd")
const World = preload("res://scripts/world.gd")
const UI = preload("res://scripts/ui.gd")

const FATHER := "Father"
const MOTHER := "Mother"
const STRANGER := "The Stranger"

var world: Node2D
var actors: Node2D
var player: CharacterBody2D
var cam: Camera2D
var ui: CanvasLayer
var tint: CanvasModulate

var interactables: Array = []   # {id, pos, text, cb, radius}
var cutscene := true
var shake_t := 0.0
var wolves_left := 0
var wolf_phase := false
var respawning := false

var swinebot: Node2D
var father: Node2D
var mother: Node2D
var stranger: Node2D
var pup: Node2D
var craft: Node2D
var rod: Node2D
var tub: Node2D
var carrying := false
var in_room := false


func _ready() -> void:
	randomize()
	world = World.new()
	add_child(world)
	actors = Node2D.new()
	actors.y_sort_enabled = true
	add_child(actors)
	tint = CanvasModulate.new()
	tint.color = Color(1.0, 0.95, 0.88)   # late afternoon
	add_child(tint)

	player = Player.new()
	player.position = Vector2(820, 760)
	actors.add_child(player)
	cam = Camera2D.new()
	cam.position_smoothing_enabled = true
	cam.position_smoothing_speed = 7.0
	cam.offset = Vector2(0, -50)
	player.add_child(cam)
	_set_area("farm")

	swinebot = _prop("swinebot", Vector2(700, 790), "Hen-a-wen")
	tub = _prop("tub", Vector2(1440, 620), "")
	rod = _prop("rod", Vector2(1560, 545), "")
	rod.visible = false

	ui = UI.new()
	add_child(ui)
	player.hp_changed.connect(ui.set_hp)
	player.died.connect(_on_player_died)
	ui.set_hp(player.hp, player.max_hp)
	ui.show_hearts(false)
	ui.title_started.connect(_begin)
	ui.show_title()
	ui.fade.color.a = 0.0


func _prop(kind: String, pos: Vector2, label: String) -> Node2D:
	var p := Prop.new()
	p.kind = kind
	p.position = pos
	p.label = label
	actors.add_child(p)
	return p


func _set_area(area: String) -> void:
	in_room = area == "room"
	var r: Rect2 = World.ROOM if in_room else World.FARM
	cam.limit_left = int(r.position.x) - (240 if in_room else 0)
	cam.limit_right = int(r.end.x) + (240 if in_room else 0)
	cam.limit_top = int(r.position.y) - (60 if in_room else 0)
	cam.limit_bottom = int(r.end.y) + (60 if in_room else 0)


func _teleport(pos: Vector2, area: String) -> void:
	player.global_position = pos
	_set_area(area)
	cam.reset_smoothing()


# ---------------- interaction plumbing ----------------

func add_interact(id: String, pos: Vector2, text: String, cb: Callable, radius := 90.0) -> void:
	remove_interact(id)
	interactables.append({"id": id, "pos": pos, "text": text, "cb": cb, "radius": radius})


func remove_interact(id: String) -> void:
	interactables = interactables.filter(func(i): return i.id != id)


func _process(delta: float) -> void:
	var recently_closed: bool = Engine.get_process_frames() - ui.closed_frame < 3
	player.controllable = not cutscene and not ui.busy and not recently_closed and player.state != "dead"
	# shake
	if shake_t > 0.0:
		shake_t -= delta
		cam.offset = Vector2(0, -50) + Vector2(randf_range(-9, 9), randf_range(-7, 7))
	else:
		cam.offset = Vector2(0, -50)
	# prompts
	var best = null
	var best_d := 1e9
	if player.controllable:
		for it in interactables:
			var d: float = player.global_position.distance_to(it.pos)
			if d < it.radius and d < best_d:
				best = it
				best_d = d
	ui.set_prompt(("[E] " + GameState.fmt(best.text)) if best != null else "")
	if best != null and Input.is_action_just_pressed("interact"):
		ui.set_prompt("")
		best.cb.call()


func shake(t := 0.5) -> void:
	shake_t = t


func wait(t: float) -> void:
	await get_tree().create_timer(t).timeout


func S(text: String) -> String:
	return GameState.fmt(text)


# ---------------- story ----------------

func _begin() -> void:
	player.setup(GameState.hero)
	await ui.fade_out(0.01)
	await ui.show_card(S("A remote, peaceful moon at the edge of the Trinitan Kingdom.\nLate afternoon, on the farm."), 2.2)
	await ui.fade_in(0.8)
	ui.show_hearts(true)
	cutscene = false
	ui.set_objective("Open Hen-a-wen's oil tank")
	add_interact("swine", swinebot.position, "Open Hen-a-wen's tank", _swine_open, 110.0)


func _swine_open() -> void:
	remove_interact("swine")
	cutscene = true
	swinebot.tank_off = true
	carrying = true
	ui.toast("Picked up: Oil tank")
	await ui.say("Hen-a-wen", "*cheerful oink-beep*")
	cutscene = false
	ui.set_objective("Empty the oil into the tub by the barn")
	add_interact("tub", tub.position, "Empty the oil tank", _tub_empty, 100.0)


func _tub_empty() -> void:
	remove_interact("tub")
	carrying = false
	ui.toast("The oil glugs into the tub")
	ui.set_objective("Put the tank back on Hen-a-wen")
	add_interact("swine2", swinebot.position, "Secure the tank", _swine_close, 110.0)


func _swine_close() -> void:
	remove_interact("swine2")
	cutscene = true
	swinebot.tank_off = false
	await ui.say("{name}", "Great job, Hen-a-wen. That will prove sufficient for today, I think.")
	await ui.say("Hen-a-wen", "*proud oink-beep*")
	await wait(0.3)
	shake(0.3)
	await ui.say("", "A long howl rolls out of the trees. Then another. The animals in the pen start to panic.")
	await ui.say("{name}", "Wolves! Coming for the pen!")
	rod.visible = true
	cutscene = false
	ui.set_objective("Grab the metal rod leaning on the barn")
	add_interact("rod", rod.position, "Take the metal rod", _take_rod, 100.0)


func _take_rod() -> void:
	remove_interact("rod")
	rod.visible = false
	player.weapon = "rod"
	ui.toast("Got: Metal Rod")
	ui.toast("Attack: J / Left-click / (X). Press repeatedly for a 3-hit combo.", Color(0.8, 0.95, 1))
	ui.set_objective("Drive the wolves away from the pen")
	_spawn_wolves()


func _spawn_wolves() -> void:
	wolf_phase = true
	Wolf.attackers = 0
	for e in get_tree().get_nodes_in_group("enemies"):
		e.queue_free()
	var spots := [Vector2(1980, 1300), Vector2(2150, 950), Vector2(1700, 1420)]
	wolves_left = spots.size()
	for i in spots.size():
		var w := Wolf.new()
		w.position = spots[i]
		w.target = player
		w.defeated.connect(_on_wolf_defeated)
		actors.add_child(w)
	await wait(2.5)
	if wolf_phase and not respawning:
		ui.toast("Watch for the red flash: a wolf is about to lunge. Dodge with Space / (A)!", Color(1, 0.75, 0.7))


func _on_wolf_defeated() -> void:
	wolves_left -= 1
	if wolves_left <= 0 and wolf_phase:
		wolf_phase = false
		_after_wolves()


func _on_player_died() -> void:
	if respawning:
		return
	respawning = true
	cutscene = true
	await wait(0.6)
	await ui.fade_out(0.6)
	await ui.show_card("You were knocked down!\nThe wolves are still at the pen. Try again.", 1.2)
	player.heal_full()
	_teleport(Vector2(1300, 960), "farm")
	if wolf_phase:
		_spawn_wolves()
	await ui.fade_in(0.5)
	cutscene = false
	respawning = false


func _after_wolves() -> void:
	cutscene = true
	await wait(0.8)
	await ui.say("{name}", "...And stay out!")
	pup = _prop("pup", Vector2(1930, 1160), "")
	await ui.say("", "A thin whimper comes from the far corner of the pen fence.")
	cutscene = false
	ui.set_objective("Find out what's whimpering by the fence")
	add_interact("pup", pup.position, "Look closer", _pup_choice, 110.0)


func _pup_choice() -> void:
	remove_interact("pup")
	cutscene = true
	await ui.say("", "A wolf pup, left behind by its pack, its leg snagged in the fence wire. It growls at you, then whimpers.")
	var c: int = await ui.choose("{name}", "What do you do?", [
		"Free the pup and toss it some scraps from your pocket.",
		"Shoo it away. Wolves are trouble, even small ones."])
	if c == 0:
		GameState.pup_choice = "freed"
		GameState.valor += 1
		await ui.say("{name}", "Easy... easy. There. Go find your family, little one.")
		ui.toast("Valor +1", Color(1, 0.85, 0.3))
		await ui.say("", "The pup sniffs the scraps, licks your glove once, and darts into the trees.")
	else:
		GameState.pup_choice = "shooed"
		await ui.say("{name}", "Go on! Get! And tell your pack to stay away from our farm.")
		await ui.say("", "The pup tears free of the wire and bolts into the trees.")
	var tw := create_tween()
	tw.tween_property(pup, "position", pup.position + Vector2(260, 220), 1.0)
	tw.tween_callback(pup.queue_free)
	await wait(0.6)
	await ui.say("Mother (offscreen)", "{name}! Time for dinner!")
	cutscene = false
	ui.set_objective("Head home for dinner")
	add_interact("door", Vector2(1105, 525), "Go inside", _enter_for_dinner, 80.0)


func _enter_for_dinner() -> void:
	remove_interact("door")
	cutscene = true
	await ui.fade_out(0.5)
	tint.color = Color(1.0, 0.92, 0.82)
	world.set_night(true)
	_teleport(Vector2(3400, 400), "room")
	player.facing = Vector2.UP
	father = _prop("father", Vector2(3330, 235), FATHER)
	mother = _prop("mother", Vector2(3470, 235), MOTHER)
	await ui.fade_in(0.5)
	await _dinner()


func _dinner() -> void:
	await ui.say("", "The family sits down together at the small table, and bows their heads.")
	await ui.say(FATHER, "We are truly grateful for all that we have. We are grateful for this bounteous meal, for our comfortable shelter, and most especially for each other and the love we share. Amen.")
	await ui.say("All", "Amen.")
	if GameState.pup_choice == "freed":
		await ui.say(MOTHER, "I saw you with that wolf pup by the fence. That was kind, {name}.")
		await ui.say(FATHER, "Kind, and perhaps a little foolish. But mostly kind.")
	else:
		await ui.say(FATHER, "I saw you send that pup running. Sensible.")
		await ui.say(MOTHER, "Sensible. Though I do hope it finds its way home.")
	await ui.say("{name}", "Father, how difficult is it to become a Marshal?")
	await ui.say(FATHER, "A Marshal? Why would you ask such a question as this?")
	await ui.say("{name}", GameState.g("I wish to be an honorable man. A hero. For this, I need a great title like Marshal.",
		"I wish to be an honorable woman. A hero. For this, I need a great title like Marshal."))
	await ui.say(MOTHER, "Honor does not come from titles.")
	await ui.say(FATHER, "She is correct. While the Marshals who travel the stars to ensure peace are indeed honorable, there are far more honorable titles one can achieve in this life.")
	await ui.say("{name}", "What titles? How must I earn them?")
	if GameState.is_gwen():
		await ui.say(MOTHER, "The greatest titles a woman can hold, which I am honored to have, are wife and mother.")
		await ui.say(FATHER, "One who honors the vows of these titles is the greatest and most blessed of all.")
	else:
		await ui.say(FATHER, "The greatest titles a man can hold, which I am honored to have, are husband and father.")
		await ui.say(MOTHER, "One who honors the vows of these titles is the greatest and most blessed of all.")
	await ui.say("{name}", "...")
	# The crash
	shake(1.0)
	ui.flash(Color(1, 0.8, 0.5))
	await wait(1.0)
	await ui.say(MOTHER, "What was that?")
	await ui.say(FATHER, "I'm not sure why, but I feel that {name} should go and investigate.")
	await ui.say("{name}", "Me? Are you sure?")
	await ui.say(MOTHER, "Well, the player cannot control us, so it must be you.")
	cutscene = false
	ui.set_objective("Go outside and investigate the crash")
	add_interact("parents", Vector2(3400, 330), "Talk to your parents", _parents_nudge, 110.0)
	add_interact("exit", Vector2(3400, 520), "Go outside", _go_to_crash, 80.0)


func _parents_nudge() -> void:
	cutscene = true
	await ui.say(FATHER, "You must investigate outside first.")
	cutscene = false


func _go_to_crash() -> void:
	remove_interact("exit")
	remove_interact("parents")
	cutscene = true
	await ui.fade_out(0.5)
	tint.color = Color(0.45, 0.5, 0.75)   # night
	_teleport(Vector2(1105, 560), "farm")
	player.facing = Vector2.DOWN
	craft = _prop("craft", Vector2(560, 1250), "")
	stranger = _prop("stranger", Vector2(680, 1240), "???")
	await ui.fade_in(0.5)
	cutscene = false
	ui.set_objective("Find what crashed in the field")
	add_interact("stranger", stranger.position, "Approach the figure", _meet_stranger, 130.0)


func _meet_stranger() -> void:
	remove_interact("stranger")
	cutscene = true
	await ui.say("", "A small one-person craft lies smoking in the field. Beside it, a battered figure of ancient bronze stirs, eyes flickering blue.")
	await ui.say(STRANGER, "Ah. A child. Of course it's a child.")
	await ui.say("{name}", "I am no child! ...But you're hurt. What happened?")
	await ui.say(STRANGER, "No time. Take this. Quickly.")
	ui.toast("Received: Black Access Key", Color(0.7, 0.85, 1))
	await ui.say("{name}", "A key? To what?")
	await ui.say(STRANGER, "If I am captured, it must not be found on me. Above all, it must never fall into Sanderian hands.")
	await ui.say("{name}", "Sanderians? Who are they? What does this key open?")
	await ui.say(STRANGER, "I cannot say.")
	await ui.say("{name}", "Cannot, or will not?")
	await ui.say(STRANGER, "Yes.")
	await ui.say(STRANGER, "My ship is finished. I need an escort to Initium. It is a matter of galactic importance.")
	var c: int = await ui.choose("{name}", "Help the Stranger get to Initium?", [
		"I'll help you. Whatever this is, it sounds like it matters.",
		"Fine. But you're going to owe me some answers."])
	if c == 0:
		GameState.stranger_attitude = "willing"
		await ui.say(STRANGER, "...Good. Brave and polite. A rare pairing in this galaxy.")
		ui.toast("The Stranger approves", Color(0.6, 1, 0.7))
	else:
		GameState.stranger_attitude = "begrudging"
		await ui.say(STRANGER, "Honest, at least. I can work with honest. The answers will come... eventually.")
		ui.toast("The Stranger noted your reluctance", Color(1, 0.8, 0.6))
	await ui.say(STRANGER, "Someone will have seen me fall. We should not linger.")
	await ui.say("{name}", "I'm not leaving without telling my parents.")
	stranger.label = STRANGER
	stranger.follow = player
	ui.toast("Ally joined: The Stranger", Color(0.6, 1, 0.7))
	cutscene = false
	ui.set_objective("Go home and tell your parents")
	add_interact("door2", Vector2(1105, 525), "Go inside", _farewell, 80.0)


func _farewell() -> void:
	remove_interact("door2")
	cutscene = true
	stranger.follow = null
	await ui.say(STRANGER, "I will keep watch out here. Be quick.")
	await ui.fade_out(0.5)
	tint.color = Color(1.0, 0.92, 0.82)
	_teleport(Vector2(3400, 400), "room")
	player.facing = Vector2.UP
	await ui.fade_in(0.5)
	await ui.say("", "You tell your parents everything: the crash, the bronze stranger, the key, and the Sanderians.")
	await ui.say(FATHER, "It seems you have a great destiny placed upon you. What you make of it will be your own choice. Choose well, and know that we love you.")
	await ui.say(FATHER, "Do not forget who you are and who you can become. Take this as a reminder of that, and use it only in dire need.")
	player.weapon = "sword"
	ui.toast("Received: Father's Sword (stronger than the rod)", Color(1, 0.9, 0.5))
	await ui.say(MOTHER, "If time is truly that short, you cannot afford to linger. Learn all you can of this plot, and stop it before it comes to pass. Go with my love, and with my blessing.")
	shake(0.8)
	ui.flash(Color(1, 0.6, 0.4))
	await wait(0.9)
	await ui.say(FATHER, "Goblibots! They're seeking the stranger. Or rather, they're seeking what you now hold, {name}.")
	await ui.say(FATHER, "I will hold them off. Out the back door, quickly!")
	await ui.fade_out(1.0)
	var lines := [
		S("Thanks for playing, {name}."),
		"",
		"Your choices:",
		"Wolf pup: " + ("you set it free (Valor +1)" if GameState.pup_choice == "freed" else "you chased it off"),
		"The Stranger: " + ("you agreed to help willingly" if GameState.stranger_attitude == "willing" else "you agreed, but begrudgingly"),
		"Valor: %d" % GameState.valor,
		"",
		"Next: escape the Goblibots, Mother's Bow, the Solarboard, and the road to Initium.",
	]
	ui.show_end(lines)
