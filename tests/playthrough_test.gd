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
	ui._pick_hero(["arthur", "gwen", "arthur_v2"].find(hero))
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
	ok("roll distance short (~96px)", dist > 80.0 and dist < 112.0, "%.0fpx" % dist)
	p.invuln_t = 0.0
	p.take_hit(1, p.global_position + Vector2(20, 0))
	ok("hit lands when not rolling", p.hp == hp_before - 1, "hp %d -> %d" % [hp_before, p.hp])
	await _roll_checks(p, wolves)
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


## Running is the default gait; the dodge roll is a short burst a little faster than running,
## dodges a real wolf lunge, ends with a short vulnerable get-up, and walls stop it.
func _roll_checks(p, wolves) -> void:
	p.invuln_t = 0.0; p.state = "move"; p.velocity = Vector2.ZERO
	var run_speed: float = p.walk_speed * p.RUN_MULT
	# default movement = run
	Input.action_press("move_right")
	for i in 12: await physics_frame
	var v_run: float = p.velocity.length()
	if p.sprite.sprite_frames.has_animation("run_side"):
		ok("default movement is the run", absf(v_run - run_speed) < 2.0 and String(p.sprite.animation) == "run_side",
			"%.0f px/s, %s" % [v_run, p.sprite.animation])
	else:   # a hero without run strips yet (Gwen) keeps walking
		ok("no run strips: walks", absf(v_run - p.walk_speed) < 2.0, "%.0f px/s" % v_run)
	# roll speed: a little faster than the run
	await tap("dodge")
	var v_roll := 0.0
	for i in 6:
		await physics_frame
		if p.state == "roll": v_roll = maxf(v_roll, p.velocity.length())
	var v_late := v_roll
	while p.state == "roll":
		await physics_frame
		if p.state == "roll": v_late = p.velocity.length()
	Input.action_release("move_right")
	ok("roll slows as he comes up (end under the run)", v_late < run_speed, "end %.0f px/s" % v_late)
	ok("roll bursts off the mark (start about 2x the run)", v_roll > run_speed * 1.8 and v_roll < run_speed * 2.4,
		"roll start %.0f vs run %.0f px/s" % [v_roll, run_speed])
	while p.state == "roll": await physics_frame
	# the get-up at the end of the roll is not protected
	p.invuln_t = 0.0; p.state = "move"
	for i in 20: await physics_frame
	await tap("dodge")
	while p.state == "roll" and p.roll_t < p.ROLL_IFRAMES + 0.01: await physics_frame
	var hp_a: int = p.hp
	if p.state == "roll":
		p.take_hit(1, p.global_position + Vector2(20, 0))
	ok("end of the roll (get-up) is not invulnerable", p.hp == hp_a - 1, "hp %d -> %d" % [hp_a, p.hp])
	p.hp = p.max_hp; p.invuln_t = 0.0; p.state = "move"; p.knock = Vector2.ZERO
	for i in 30: await physics_frame
	# a real wolf lunge is dodged by rolling as it leaps
	var w = wolves[2]
	w.set_physics_process(true)
	p.invuln_t = 0.0; p.state = "move"
	w.global_position = p.global_position + Vector2(150, 0)
	w.state = "telegraph"; w.t = 0.0; w.holding_token = true; w.get_script().attackers = 1
	var hp_b: int = p.hp
	while w.state == "telegraph": await physics_frame
	Input.action_press("move_up")
	await tap("dodge")
	Input.action_release("move_up")
	while w.state == "lunge": await physics_frame
	ok("rolling as the wolf leaps dodges the bite", p.hp == hp_b, "hp %d -> %d" % [hp_b, p.hp])
	w.set_physics_process(false); w.global_position = Vector2(2300, 1500); w.state = "circle"
	w._release_token()
	while p.state == "roll": await physics_frame
	# walls stop a roll
	p.invuln_t = 0.0; p.state = "move"
	var wall := StaticBody2D.new()
	wall.collision_layer = 1
	var cs := CollisionShape2D.new()
	var rs := RectangleShape2D.new()
	rs.size = Vector2(20, 200)
	cs.shape = rs
	wall.add_child(cs)
	p.get_parent().add_child(wall)
	wall.global_position = p.global_position + Vector2(80, 0)   # nearer than a full roll (96px)
	for i in 30: await physics_frame   # roll cooldown
	var x0: float = p.global_position.x
	Input.action_press("move_right")
	await tap("dodge")
	Input.action_release("move_right")
	var max_x := x0
	while p.state == "roll":
		await physics_frame
		max_x = maxf(max_x, p.global_position.x)
	ok("a wall stops the roll", max_x - x0 > 20.0 and max_x < wall.global_position.x - 10.0,
		"rolled %.0fpx, stopped at x %.0f, wall face at %.0f" % [max_x - x0, max_x, wall.global_position.x - 10.0])
	wall.queue_free()
	p.hp = p.max_hp; p.hp_changed.emit(p.hp, p.max_hp)
