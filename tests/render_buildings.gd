extends SceneTree
## Screenshots Arthur in front of the farmhouse and the cottage (real renderer, under xvfb).
var _f := 0
var _main: Node


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


func _shot(pos: Vector2, path: String) -> void:
	var p = _main.player
	p.global_position = pos
	_main.cam.reset_smoothing()


func _process(_d: float) -> bool:
	_f += 1
	if _f == 5:
		_find(root, "_start")._start()
	if _f == 150:
		_main.ui.visible = false
		for c in _main.ui.get_children():
			if c is CanvasItem: c.visible = false
		_main.player.set_physics_process(false)
		_shot(Vector2(1105, 560), "")
	if _f == 175:
		root.get_texture().get_image().save_png("/tmp/bld_farmhouse.png")
		_shot(Vector2(560, 575), "")
	if _f == 200:
		root.get_texture().get_image().save_png("/tmp/bld_cottage.png")
		_shot(Vector2(1640, 560), "")
	if _f == 225:
		root.get_texture().get_image().save_png("/tmp/bld_barn.png")
		return true
	return false
