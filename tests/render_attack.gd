extends SceneTree
## Equips Father's Sword, then plays the full 3-slash combo (attack pressed during each swing, as
## a player clicking would) facing right, left, down and up. Saves a crop around the hero every
## other frame: /tmp/atk/<dir>_<nnn>.png (real renderer, under xvfb). Checks each slash's
## animation plays and that the combo reaches slash 3.
var _f := 0
var _main: Node
var _player: Node
var _dirs := ["right", "left", "down", "up"]
var _i := -1
var _k := 0
var _shot := 0
var _max_combo := 0
var _seen := {}
var _fails := 0
const CROP := Vector2i(300, 260)


func _initialize() -> void:
	_main = load(ProjectSettings.get_setting("application/run/main_scene")).instantiate()
	root.add_child(_main)
	DirAccess.make_dir_recursive_absolute("/tmp/atk")


func _find(n: Node, m: String) -> Node:
	if n.has_method(m):
		return n
	for c in n.get_children():
		var r = _find(c, m)
		if r:
			return r
	return null


func _check(ok: bool, what: String) -> void:
	print(("PASS " if ok else "FAIL ") + what)
	if not ok:
		_fails += 1


func _release_all() -> void:
	for a in ["move_right", "move_left", "move_down", "move_up", "attack"]:
		Input.action_release(a)


func _process(_d: float) -> bool:
	_f += 1
	if _f == 5:
		_find(root, "_pick_look")._start()
	if _f == 280:
		_player = _find(root, "_update_anim")
		_player.equip(OS.get_environment("WEAPON") if OS.get_environment("WEAPON") != "" else "fathers_sword")
		_player.controllable = true
	if _f < 300:
		return false
	if _i == -1 or _k >= 110:
		if _i >= 0:
			_check(_max_combo == 3, "%s: combo reached slash 3 (got %d)" % [_dirs[_i], _max_combo])
			var d: String = "side" if _dirs[_i] in ["right", "left"] else _dirs[_i]
			if _player.sprite.sprite_frames.has_animation("attack1_" + d):
				for n in [1, 2, 3]:
					_check(_seen.has("attack%d_%s" % [n, d]), "%s: slash %d strip played" % [_dirs[_i], n])
		_i += 1
		_k = 0
		_shot = 0
		_max_combo = 0
		_seen = {}
		if _i >= _dirs.size():
			_release_all()
			print("SUMMARY: %d failed" % _fails)
			return true
	var dir: String = _dirs[_i]
	# 0-5: tap the direction to face it; then click attack every 6 frames until slash 3 starts
	if _k == 0:
		_release_all()
		Input.action_press("move_" + dir)
	if _k == 4:
		Input.action_release("move_" + dir)
	if _k >= 12 and _k % 6 == 0 and _max_combo < 3:
		Input.action_press("attack")
	if _k >= 12 and _k % 6 == 1:
		Input.action_release("attack")
	if _player.state == "attack":
		_max_combo = maxi(_max_combo, _player.combo)
		_seen[String(_player.sprite.animation)] = true
	if _k >= 10 and _k % 2 == 0:
		var img := root.get_texture().get_image()
		var c: Vector2 = _player.get_global_transform_with_canvas().origin
		var r := Rect2i(Vector2i(c) - Vector2i(CROP.x / 2, CROP.y - 60), CROP)
		r = r.intersection(Rect2i(Vector2i.ZERO, img.get_size()))
		img.get_region(r).save_png("/tmp/atk/%s_%03d.png" % [dir, _shot])
		_shot += 1
	_k += 1
	return false
