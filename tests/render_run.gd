extends SceneTree
## Starts the game, then walks and runs (Shift) in each direction and saves a screenshot of each
## (real renderer, under xvfb): /tmp/run_<walk|run>_<dir>.png. Also checks the run animations load
## with the manifest's frame counts and wide cells, and that holding Run plays them.
var _f := 0
var _main: Node
var _player: Node
var _steps := [
	["move_right", false], ["move_right", true],
	["move_left", false], ["move_left", true],
	["move_down", false], ["move_down", true],
	["move_up", false], ["move_up", true],
]
var _i := 0
var _fails := 0


func _initialize() -> void:
	_main = load(ProjectSettings.get_setting("application/run/main_scene")).instantiate()
	root.add_child(_main)


func _find(n: Node, m: String) -> Node:
	if n.has_method(m):
		return n
	for c in n.get_children():
		var r = _find(c, m)
		if r:
			return r
	return null


func _release_all() -> void:
	for a in ["move_right", "move_left", "move_down", "move_up", "run"]:
		Input.action_release(a)


func _check(ok: bool, what: String) -> void:
	print(("PASS " if ok else "FAIL ") + what)
	if not ok:
		_fails += 1


func _process(_d: float) -> bool:
	_f += 1
	if _f == 5:
		var ui = _find(root, "_pick_look")
		ui._start()
	if _f == 60:
		_player = _find(root, "_update_anim")
		var sf: SpriteFrames = _player.sprite.sprite_frames
		for d in ["side", "down", "up"]:
			_check(sf.has_animation("run_" + d), "run_%s loaded" % d)
			if sf.has_animation("run_" + d):
				var t: AtlasTexture = sf.get_frame_texture("run_" + d, 0)
				_check(t.region.size.x == 240.0, "run_%s cell 240 wide (got %s)" % [d, t.region.size.x])
				_check(sf.get_frame_count("run_" + d) == {"side": 18, "down": 26, "up": 23}[d], "run_%s frame count" % d)
	# each step: hold the keys 40 frames, screenshot, check the animation
	var k := _f - 160
	if k >= 0 and _i < _steps.size():
		var s = _steps[_i]
		if k % 50 == 0:
			_release_all()
			Input.action_press(s[0])
			if s[1]:
				Input.action_press("run")
		if k % 50 == 40:
			var dir: String = {"move_right": "right", "move_left": "left", "move_down": "down", "move_up": "up"}[s[0]]
			var kind := "run" if s[1] else "walk"
			var want: String = kind + "_" + ("side" if dir in ["right", "left"] else dir)
			_check(String(_player.sprite.animation) == want, "%s %s plays %s (got %s)" % [kind, dir, want, _player.sprite.animation])
			root.get_texture().get_image().save_png("/tmp/run_%s_%s.png" % [kind, dir])
			_i += 1
	if _i >= _steps.size():
		_release_all()
		print("SUMMARY: %d failed" % _fails)
		return true
	return false
