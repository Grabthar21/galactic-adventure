extends Node2D
## The farm (outdoor area) and the family home interior. The farmhouse, cottage and barn are
## Blender-rendered sprites; everything else is still a placeholder drawn in code.
## Collision walls are StaticBody2D rectangles on layer 1.

const FARM := Rect2(0, 0, 2400, 1600)
const ROOM := Rect2(3000, 0, 800, 600)

## Buildings: Blender renders in art/buildings (see its README). Each sprite is drawn at the
## hero's in-game scale (0.75) and anchored at the building's ground centre, so it y-sorts
## with the characters. ORIGIN is that ground centre in the image's pixels.
const ART_SCALE := 0.75
const BUILDINGS := {
	"farmhouse": {"tex": "res://art/buildings/farmhouse.png", "origin": Vector2(364, 668.5),
		"pos": Vector2(1105, 413),
		# walls, then the rain barrel (world px, relative to pos)
		"solid": [Rect2(-240, -80, 480, 160), Rect2(205, 60, 50, 50)]},
	"cottage": {"tex": "res://art/buildings/farm_cottage.png", "origin": Vector2(290, 464.2),
		"pos": Vector2(470, 468),
		"solid": [Rect2(-186, -67, 372, 134)]},
	"barn": {"tex": "res://art/buildings/barn.png", "origin": Vector2(307, 599.8),
		"pos": Vector2(1645, 394),
		"solid": [Rect2(-200, -106, 400, 212)]},
}
const HOUSE_DOOR := Vector2(1105, 525)
const PEN := Rect2(1400, 800, 500, 340)
const FIELD := Rect2(260, 620, 520, 380)

var night := false
var rng := RandomNumberGenerator.new()
var grass_dots: Array = []
var trees: Array = []


func _ready() -> void:
	rng.seed = 7
	for i in 900:
		grass_dots.append([Vector2(rng.randf_range(0, FARM.size.x), rng.randf_range(0, FARM.size.y)), rng.randf_range(2, 5), rng.randf()])
	# border trees
	var x := 0.0
	while x < FARM.size.x:
		trees.append(Vector2(x + rng.randf_range(-10, 10), rng.randf_range(10, 70)))
		trees.append(Vector2(x + rng.randf_range(-10, 10), FARM.size.y - rng.randf_range(10, 70)))
		x += rng.randf_range(70, 110)
	# second row behind the house roofs (the camera can now see above y = 0)
	x = 0.0
	while x < FARM.size.x:
		trees.append(Vector2(x + rng.randf_range(-10, 10), rng.randf_range(-80, -40)))
		x += rng.randf_range(70, 110)
	var y := 100.0
	while y < FARM.size.y - 100:
		trees.append(Vector2(rng.randf_range(10, 70), y))
		trees.append(Vector2(FARM.size.x - rng.randf_range(10, 70), y))
		y += rng.randf_range(70, 110)
	# solid areas
	for b in BUILDINGS.values():
		for r in b.solid:
			_block(Rect2(b.pos + r.position, r.size))
	# pen fence: top, right, bottom; the west side is the open gate
	_block(Rect2(PEN.position.x, PEN.position.y, PEN.size.x, 10))
	_block(Rect2(PEN.end.x - 10, PEN.position.y, 10, PEN.size.y))
	_block(Rect2(PEN.position.x, PEN.end.y - 10, PEN.size.x, 10))
	# map bounds (inside the tree line)
	_block(Rect2(-100, -100, FARM.size.x + 200, 190))
	_block(Rect2(-100, FARM.size.y - 90, FARM.size.x + 200, 190))
	_block(Rect2(-100, -100, 190, FARM.size.y + 200))
	_block(Rect2(FARM.size.x - 90, -100, 190, FARM.size.y + 200))
	# room walls
	_block(Rect2(ROOM.position.x - 100, ROOM.position.y - 100, ROOM.size.x + 200, 230))
	_block(Rect2(ROOM.position.x - 100, ROOM.end.y - 40, ROOM.size.x + 200, 140))
	_block(Rect2(ROOM.position.x - 100, ROOM.position.y - 100, 140, ROOM.size.y + 200))
	_block(Rect2(ROOM.end.x - 40, ROOM.position.y - 100, 140, ROOM.size.y + 200))
	_block(Rect2(3290, 250, 220, 70))   # table


## Sprites for the buildings; main.gd adds them to the y-sorted actors layer.
func make_building_sprites() -> Array:
	var out := []
	for id in BUILDINGS:
		var b: Dictionary = BUILDINGS[id]
		var sp := Sprite2D.new()
		sp.name = id
		sp.texture = load(b.tex)
		sp.centered = false
		sp.offset = -b.origin
		sp.scale = Vector2(ART_SCALE, ART_SCALE)
		sp.position = b.pos
		sp.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
		out.append(sp)
	return out


func _block(r: Rect2) -> void:
	var body := StaticBody2D.new()
	body.collision_layer = 1
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = r.size
	shape.shape = rect
	shape.position = r.get_center()
	body.add_child(shape)
	add_child(body)


func set_night(v: bool) -> void:
	night = v
	queue_redraw()


func _draw() -> void:
	_draw_farm()
	_draw_room()


func _draw_farm() -> void:
	draw_rect(Rect2(-200, -260, FARM.size.x + 400, FARM.size.y + 460), Color(0.47, 0.66, 0.33))
	for d in grass_dots:
		draw_circle(d[0], d[1], Color(0.38, 0.58, 0.27) if d[2] < 0.6 else Color(0.55, 0.74, 0.38))
	# paths
	var dirt := Color(0.72, 0.6, 0.42)
	draw_rect(Rect2(1080, 500, 50, 700), dirt)
	draw_rect(Rect2(440, 560, 1360, 50), dirt)
	draw_rect(Rect2(1620, 500, 50, 80), dirt)
	# crop field
	draw_rect(FIELD, Color(0.55, 0.42, 0.28))
	var row := FIELD.position.y + 25
	while row < FIELD.end.y:
		draw_line(Vector2(FIELD.position.x + 15, row), Vector2(FIELD.end.x - 15, row), Color(0.45, 0.33, 0.2), 6.0)
		var cx := FIELD.position.x + 30
		while cx < FIELD.end.x - 20:
			draw_circle(Vector2(cx, row - 6), 7.0, Color(0.35, 0.6, 0.25))
			cx += 34
		row += 46
	# pen
	draw_rect(PEN, Color(0.6, 0.55, 0.35, 0.5))
	for hb in [Vector2(1520, 900), Vector2(1760, 1000)]:
		draw_rect(Rect2(hb - Vector2(30, 18), Vector2(60, 36)), Color(0.85, 0.75, 0.4))
		draw_rect(Rect2(hb - Vector2(30, 18), Vector2(60, 36)), Color(0.65, 0.55, 0.25), false, 2.0)
	var fence := Color(0.5, 0.35, 0.2)
	draw_line(PEN.position, Vector2(PEN.end.x, PEN.position.y), fence, 5.0)
	draw_line(Vector2(PEN.end.x, PEN.position.y), PEN.end, fence, 5.0)
	draw_line(Vector2(PEN.position.x, PEN.end.y), PEN.end, fence, 5.0)
	var px := PEN.position.x
	while px <= PEN.end.x:
		draw_rect(Rect2(px - 4, PEN.position.y - 16, 8, 20), fence)
		draw_rect(Rect2(px - 4, PEN.end.y - 16, 8, 20), fence)
		px += 50
	var py := PEN.position.y
	while py <= PEN.end.y:
		draw_rect(Rect2(PEN.end.x - 4, py - 16, 8, 20), fence)
		py += 50
	draw_rect(Rect2(PEN.position.x - 4, PEN.position.y - 16, 8, 20), fence)
	draw_rect(Rect2(PEN.position.x - 4, PEN.end.y - 16, 8, 20), fence)
	# trees
	for tp in trees:
		draw_circle(tp + Vector2(0, 10), 34, Color(0, 0, 0, 0.18))
		draw_rect(Rect2(tp.x - 7, tp.y - 10, 14, 26), Color(0.4, 0.28, 0.18))
		draw_circle(tp + Vector2(0, -26), 34, Color(0.2, 0.42, 0.22))
		draw_circle(tp + Vector2(-12, -36), 20, Color(0.27, 0.52, 0.27))
	# signpost hint
	var f := ThemeDB.fallback_font
	draw_string(f, Vector2(1420, 1180), "Livestock pen", HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color(0.2, 0.15, 0.1, 0.7))


func _draw_room() -> void:
	draw_rect(Rect2(ROOM.position - Vector2(400, 400), ROOM.size + Vector2(800, 800)), Color(0.08, 0.06, 0.05))
	draw_rect(ROOM, Color(0.62, 0.45, 0.3))
	var py := ROOM.position.y + 130
	while py < ROOM.end.y:
		draw_line(Vector2(ROOM.position.x, py), Vector2(ROOM.end.x, py), Color(0.52, 0.37, 0.24), 2.0)
		py += 36
	draw_rect(Rect2(ROOM.position.x, ROOM.position.y, ROOM.size.x, 130), Color(0.78, 0.68, 0.52))
	draw_rect(Rect2(ROOM.position.x, ROOM.position.y + 118, ROOM.size.x, 12), Color(0.45, 0.32, 0.22))
	# window and hearth
	var sky := Color(0.15, 0.2, 0.4) if night else Color(0.6, 0.78, 0.92)
	draw_rect(Rect2(3120, 30, 90, 66), sky)
	draw_rect(Rect2(3120, 30, 90, 66), Color(0.4, 0.28, 0.18), false, 5.0)
	draw_rect(Rect2(3560, 20, 130, 110), Color(0.45, 0.42, 0.4))
	draw_rect(Rect2(3590, 60, 70, 70), Color(0.12, 0.08, 0.06))
	draw_circle(Vector2(3625, 112), 16.0, Color(1.0, 0.55, 0.15))
	# table
	draw_rect(Rect2(3290, 240, 220, 80), Color(0.45, 0.3, 0.18))
	draw_rect(Rect2(3290, 240, 220, 80), Color(0.32, 0.2, 0.12), false, 3.0)
	for bowl in [Vector2(3340, 270), Vector2(3460, 270), Vector2(3400, 300)]:
		draw_circle(bowl, 12.0, Color(0.9, 0.88, 0.82))
		draw_circle(bowl, 8.0, Color(0.7, 0.45, 0.25))
	# doormat / exit
	draw_rect(Rect2(3360, ROOM.end.y - 50, 80, 14), Color(0.6, 0.25, 0.2))
