extends SceneTree
## Renders the player with several skin/hair choices in several animations through the real
## GPU path (run under xvfb) and saves /tmp/appearance_render.png for a visual check.
## usage: xvfb-run -a godot --rendering-driver opengl3 --path . -s tests/render_appearance.gd

var _frames := 0


func _initialize() -> void:
	var bg := ColorRect.new()
	bg.color = Color(0.43, 0.65, 0.33)
	bg.size = Vector2(1280, 720)
	root.add_child(bg)


func _spawn() -> void:
	var gs = root.get_node("GameState")
	var combos := [[0, 0], [1, 1], [2, 4], [4, 5], [5, 6], [3, 3]]
	var anims := ["idle_down", "walk_side", "walk_down", "walk_up"]
	for y in anims.size():
		for x in combos.size():
			var p = load("res://scripts/player.gd").new()
			root.add_child(p)
			p.setup("arthur")
			p.set_physics_process(false)     # keep the chosen animation (no movement logic)
			p.set_process(false)
			p.set_appearance(gs.SKIN_TONES[combos[x][0]][1], gs.HAIR_COLORS[combos[x][1]][1])
			p.sprite.play(anims[y])
			p.sprite.pause()
			p.sprite.frame = 3
			p.sprite.scale = Vector2(1.1, 1.1)
			p.position = Vector2(110 + x * 205, 172 + y * 176)


func _process(_delta: float) -> bool:
	_frames += 1
	if _frames == 2:
		_spawn()
	if _frames == 8:
		var img := root.get_texture().get_image()
		img.save_png("/tmp/appearance_render.png")
		print("saved /tmp/appearance_render.png ", img.get_size())
		return true
	return false
