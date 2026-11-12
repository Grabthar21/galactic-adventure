extends SceneTree
## Screenshots the title screen with a few appearance picks (real renderer, run under xvfb).
var _f := 0
var _ui: Node


func _initialize() -> void:
	var main = load(ProjectSettings.get_setting("application/run/main_scene")).instantiate()
	root.add_child(main)


func _find(n: Node) -> Node:
	if n.has_method("_pick_look"):
		return n
	for c in n.get_children():
		var r = _find(c)
		if r:
			return r
	return null


func _process(_d: float) -> bool:
	_f += 1
	if _f == 5:
		_ui = _find(root)
	var shots := {8: [0, 0, 0], 12: [5, 5, 1], 16: [4, 1, 1], 20: [2, 4, 0]}
	for k in shots:
		if _f == k and _ui:
			_ui._pick_look("skin", shots[k][0])
			_ui._pick_look("hair", shots[k][1])
			_ui._pick_style(shots[k][2])
		if _f == k + 2:
			root.get_texture().get_image().save_png("/tmp/title_%d.png" % k)
	if _f == 24:
		print("title shots saved; ui found: ", _ui != null)
		return true
	return false
