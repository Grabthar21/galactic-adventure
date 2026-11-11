extends SceneTree
## Saves screenshots at key moments (needs a display, e.g. xvfb-run).
var main
func shot(name: String) -> void:
	for i in 4: await process_frame
	root.get_viewport().get_texture().get_image().save_png("res://build/shots/%s.png" % name)
func _initialize() -> void:
	main = load("res://main.tscn").instantiate()
	root.add_child(main)
	_run.call_deferred()
func adv(n: int) -> void:
	var ui = main.ui
	for i in n:
		if ui.dlg_panel.visible:
			if ui._choices.size() > 0: ui._choice_index = 0
			else: ui._typing = false; ui._advance = true
		await process_frame
func _run() -> void:
	DirAccess.make_dir_recursive_absolute("res://build/shots")
	for i in 10: await process_frame
	await shot("01_title")
	main.ui._pick_hero(0); main.ui._start()
	for i in 260: await process_frame
	await shot("02_farm")
	main.player.global_position = Vector2(1300, 980); main.player.weapon = "rod"
	main.cutscene = false
	main.ui.fade.color.a = 0
	main._spawn_wolves()
	for w in get_nodes_in_group("enemies"): w.global_position = main.player.global_position + Vector2(randf_range(-200, 200), randf_range(-140, 140))
	for i in 50: await process_frame
	main.player.state = "attack"; main.player.combo = 3; main.player.attack_t = 0.12; main.player.facing = Vector2.RIGHT
	await shot("03_wolves")
	for w in get_nodes_in_group("enemies"): w.queue_free()
	main.wolf_phase = false
	main.player.state = "move"
	await main._enter_for_dinner()
	await shot("04_dinner")
	quit()
