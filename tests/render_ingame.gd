extends SceneTree
## Starts the game with a chosen look and screenshots gameplay (real renderer, under xvfb).
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


func _process(_d: float) -> bool:
	_f += 1
	if _f == 5:
		var ui = _find(root, "_pick_look")
		ui._pick_look("skin", 4)
		ui._pick_look("hair", 3)
		ui._pick_style(1)
		ui._start()
	if _f == 200:
		root.get_texture().get_image().save_png("/tmp/ingame.png")
		print("saved; player skin=", root.get_node("GameState").skin_color)
		return true
	return false
