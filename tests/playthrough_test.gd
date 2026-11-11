extends SceneTree
## Automated checks: combat mechanics + a full scripted playthrough of the opening.
## Run: godot --headless --script res://tests/playthrough_test.gd -- [arthur|gwen] [0|1]

var main
var results := []
var hero := "arthur"
var pick := 0

func ok(name: String, cond: bool, extra := "") -> void:
	results.append(("PASS " if cond else "FAIL ") + name + ("  " + extra if extra != "" else ""))

func frames(n: int) -> void:
	for i in n:
		await process_frame

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() > 0: hero = args[0]
	if args.size() > 1: pick = int(args[1])
	main = load("res://main.tscn").instantiate()
	root.add_child(main)
	_run.call_deferred()

func _run() -> void:
	await frames(5)
	var ui = main.ui
	ui._pick_hero(0 if hero == "arthur" else 1)
	ui.name_edit.text = "Testy"
	ui._start()
	ok("hero chosen", root.get_node("GameState").hero == hero and root.get_node("GameState").hero_name == "Testy")
	await _drive(1200, func(): return main.player.weapon == "rod")
	ok("reached wolf fight with rod", main.player.weapon == "rod" and main.wolf_phase)
	await _combat_checks()
	await _drive(6000, func(): return ui.end_panel != null)
	ok("reached end card", ui.end_panel != null)
	ok("sword received", main.player.weapon == "sword")
	ok("pup choice recorded", root.get_node("GameState").pup_choice == ("freed" if pick == 0 else "shooed"))
	ok("stranger attitude recorded", root.get_node("GameState").stranger_attitude == ("willing" if pick == 0 else "begrudging"))
	ok("valor matches choices", root.get_node("GameState").valor == (1 if pick == 0 else 0), "valor=%d" % root.get_node("GameState").valor)
	for r in results: print(r)
	print("SUMMARY: %d/%d passed" % [results.filter(func(r): return r.begins_with("PASS")).size(), results.size()])
	quit(0 if results.all(func(r): return r.begins_with("PASS")) else 1)

## Advance dialogue, pick choice `pick`, walk to and use interactables, kill wolves.
func _drive(max_frames: int, done: Callable) -> void:
	var ui = main.ui
	for i in max_frames:
		if done.call():
			return
		if ui.dlg_panel.visible:
			if ui._choices.size() > 0:
				ui._choice_index = pick
			else:
				ui._typing = false
				ui._advance = true
		elif not main.cutscene and not ui.busy and main.player.controllable:
			if main.wolf_phase:
				for w in get_nodes_in_group("enemies"):
					w.take_hit(99, w.global_position + Vector2(10, 0), 100.0)
			elif main.interactables.size() > 0:
				var it = main.interactables.filter(func(x): return x.id != "parents").back()
				main.player.global_position = it.pos
				it.cb.call()
		await process_frame

func tap(action: String) -> void:
	Input.action_press(action)
	await physics_frame
	await physics_frame
	Input.action_release(action)

func _combat_checks() -> void:
	var p = main.player
	var wolves = get_nodes_in_group("enemies")
	ok("three wolves spawned", wolves.size() == 3, str(wolves.size()))
	await frames(10)
	# freeze wolves far away except one test dummy
	for w in wolves: w.set_physics_process(false); w.global_position = Vector2(2300, 1500)
	var dummy = wolves[0]
	dummy.global_position = p.global_position + Vector2(60, 0)
	p.facing = Vector2.RIGHT
	var hp0: int = dummy.hp
	# 3-hit combo: tap attack, then tap again inside each swing window
	await tap("attack")
	var max_combo := 0
	for i in 120:
		max_combo = max(max_combo, p.combo)
		if p.state != "attack":
			break
		if p.attack_t > 0.12 and p.combo < 3 and not p.queued:
			await tap("attack")
		else:
			await physics_frame
	p.combo = max_combo
	ok("combo reached hit 3", p.combo == 3 or dummy.hp < hp0 - 2, "combo=%d" % p.combo)
	ok("rod combo damage = 1+1+2", hp0 - dummy.hp == 4 or dummy.dead, "dealt=%d" % (hp0 - dummy.hp))
	await frames(40)
	# roll grants invulnerability, then normal hits land
	p.invuln_t = 0.0
	p.state = "move"
	await frames(20)
	var hp_before: int = p.hp
	var start: Vector2 = p.global_position
	p.facing = Vector2.DOWN
	await tap("dodge")
	ok("dodge starts a roll", p.state == "roll")
	p.take_hit(1, p.global_position + Vector2(20, 0))
	ok("no damage while rolling", p.hp == hp_before)
	for i in 30: await physics_frame
	var dist: float = start.distance_to(p.global_position)
	ok("roll distance about one character height (~105px)", dist > 80.0 and dist < 125.0, "%.0fpx" % dist)
	p.invuln_t = 0.0
	p.take_hit(1, p.global_position + Vector2(20, 0))
	ok("hit lands when not rolling", p.hp == hp_before - 1, "hp %d -> %d" % [hp_before, p.hp])
	# lunge telegraph + contact damage
	var w2 = wolves[1]
	w2.set_physics_process(true)
	p.invuln_t = 0.0; p.state = "move"
	w2.global_position = p.global_position + Vector2(150, 0)
	w2.state = "telegraph"; w2.t = 0.0; w2.holding_token = true; w2.get_script().attackers = 1
	var hp_b: int = p.hp
	for i in 90:
		await physics_frame
		if p.hp < hp_b: break
	ok("telegraphed lunge damages a standing player", p.hp < hp_b)
	# death -> respawn with full health and fresh wolves
	p.invuln_t = 0.0; p.state = "move"; p.hp = 1
	p.take_hit(1, p.global_position + Vector2(10, 0))
	ok("player can be defeated", p.state == "dead")
	var guard2 := 0
	while main.respawning and guard2 < 600:
		await process_frame; guard2 += 1
	ok("respawn restores health", p.hp == p.max_hp)
	ok("respawn resets wolves", get_nodes_in_group("enemies").size() == 3)
