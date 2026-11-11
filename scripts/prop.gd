extends Node2D
## Placeholder characters and objects drawn in code. Origin is at the feet / base,
## so they y-sort correctly with the hero. Swap any of these for real art later.

@export var kind := "father"   # father, mother, stranger, pup, swinebot, rod, tub, craft, key
var label := ""
var t := 0.0
var follow: Node2D = null       # if set, trail behind this node (used by the Stranger)
var tank_off := false           # Swine-Bot tank removed
var night := false


func _process(delta: float) -> void:
	t += delta
	if follow:
		var to := follow.global_position - global_position
		if to.length() > 90.0:
			global_position += to.normalized() * minf(to.length() - 90.0, 210.0 * delta)
	queue_redraw()


func _person(skin: Color, hair: Color, shirt: Color, pants: Color, tall: float, beard := false, long_hair := false) -> void:
	var h := tall
	draw_set_transform(Vector2.ZERO, 0.0, Vector2(1, 0.3))
	draw_circle(Vector2.ZERO, 26.0, Color(0, 0, 0, 0.22))
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	draw_rect(Rect2(-14, -h * 0.42, 11, h * 0.42), pants)
	draw_rect(Rect2(3, -h * 0.42, 11, h * 0.42), pants)
	draw_rect(Rect2(-16, -6, 14, 6), Color(0.35, 0.22, 0.12))
	draw_rect(Rect2(2, -6, 14, 6), Color(0.35, 0.22, 0.12))
	draw_rect(Rect2(-19, -h * 0.78, 38, h * 0.38), shirt)
	draw_rect(Rect2(-26, -h * 0.76, 8, h * 0.3), shirt.darkened(0.1))
	draw_rect(Rect2(18, -h * 0.76, 8, h * 0.3), shirt.darkened(0.1))
	draw_circle(Vector2(-22, -h * 0.45), 5.0, skin)
	draw_circle(Vector2(22, -h * 0.45), 5.0, skin)
	var head := Vector2(0, -h * 0.88)
	if long_hair:
		draw_rect(Rect2(head.x - 17, head.y - 8, 34, 30), hair)
	draw_circle(head, 15.0, skin)
	draw_arc(head + Vector2(0, -2), 16.0, PI, TAU, 16, hair, 9.0)
	draw_circle(head + Vector2(-5, 1), 2.0, Color(0.15, 0.1, 0.08))
	draw_circle(head + Vector2(5, 1), 2.0, Color(0.15, 0.1, 0.08))
	if beard:
		draw_arc(head + Vector2(0, 4), 12.0, 0.2, PI - 0.2, 12, hair, 6.0)


func _draw() -> void:
	match kind:
		"father":
			_person(Color(0.93, 0.76, 0.6), Color(0.4, 0.26, 0.15), Color(0.45, 0.55, 0.35), Color(0.3, 0.25, 0.2), 118.0, true)
		"mother":
			_person(Color(0.93, 0.76, 0.6), Color(0.55, 0.3, 0.15), Color(0.6, 0.35, 0.4), Color(0.45, 0.3, 0.35), 110.0, false, true)
		"stranger":
			_draw_stranger()
		"pup":
			_draw_pup()
		"swinebot":
			_draw_swinebot()
		"rod":
			draw_line(Vector2(-26, -4), Vector2(26, -10), Color(0.55, 0.55, 0.6), 5.0)
			draw_circle(Vector2(26, -10), 4.0, Color(0.4, 0.4, 0.45))
			if int(t * 3.0) % 2 == 0:
				draw_circle(Vector2(0, -7), 3.0, Color(1, 1, 0.7, 0.8))
		"tub":
			draw_set_transform(Vector2(0, -10), 0.0, Vector2(1, 0.45))
			draw_circle(Vector2.ZERO, 46.0, Color(0.35, 0.3, 0.28))
			draw_circle(Vector2.ZERO, 38.0, Color(0.08, 0.07, 0.06))
			draw_circle(Vector2(-10, -8), 8.0, Color(0.3, 0.25, 0.35, 0.6))
			draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
		"craft":
			_draw_craft()
	if label != "":
		var f := ThemeDB.fallback_font
		var w := f.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, 15).x
		var y := -150.0 if kind in ["father", "mother", "stranger"] else -70.0
		draw_string_outline(f, Vector2(-w / 2.0, y), label, HORIZONTAL_ALIGNMENT_LEFT, -1, 15, 4, Color(0, 0, 0, 0.7))
		draw_string(f, Vector2(-w / 2.0, y), label, HORIZONTAL_ALIGNMENT_LEFT, -1, 15, Color(1, 0.95, 0.8))


func _draw_stranger() -> void:
	# Ancient bronze automaton (placeholder — the creature's type is still undecided).
	var bronze := Color(0.62, 0.45, 0.25)
	var dark := Color(0.35, 0.25, 0.15)
	var glow := Color(0.4, 0.9, 1.0, 0.6 + 0.4 * sin(t * 3.0))
	draw_set_transform(Vector2.ZERO, 0.0, Vector2(1, 0.3))
	draw_circle(Vector2.ZERO, 30.0, Color(0, 0, 0, 0.25))
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	draw_rect(Rect2(-16, -50, 12, 50), dark)
	draw_rect(Rect2(4, -50, 12, 50), dark)
	draw_colored_polygon(PackedVector2Array([Vector2(-28, -110), Vector2(28, -110), Vector2(20, -48), Vector2(-20, -48)]), bronze)
	draw_line(Vector2(-14, -100), Vector2(14, -60), dark, 3.0)  # crack / damage
	draw_rect(Rect2(-36, -108, 10, 46), bronze.darkened(0.15))
	draw_rect(Rect2(26, -108, 10, 46), bronze.darkened(0.15))
	draw_rect(Rect2(-15, -138, 30, 28), bronze)
	draw_rect(Rect2(-10, -128, 20, 6), Color(0.05, 0.1, 0.12))
	draw_circle(Vector2(-5, -125), 2.5, glow)
	draw_circle(Vector2(5, -125), 2.5, glow)
	draw_line(Vector2(0, -138), Vector2(0, -148), dark, 2.0)
	draw_circle(Vector2(0, -149), 3.0, glow)


func _draw_pup() -> void:
	var c := Color(0.55, 0.55, 0.6)
	var wag := sin(t * 10.0) * 4.0
	draw_set_transform(Vector2.ZERO, 0.0, Vector2(1, 0.35))
	draw_circle(Vector2.ZERO, 18.0, Color(0, 0, 0, 0.22))
	draw_set_transform(Vector2(0, -12), 0.0, Vector2(1, 0.6))
	draw_circle(Vector2.ZERO, 15.0, c)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	draw_line(Vector2(-14, -14), Vector2(-24, -20 + wag), c, 4.0)
	draw_circle(Vector2(14, -20), 9.0, c)
	draw_colored_polygon(PackedVector2Array([Vector2(9, -26), Vector2(11, -36), Vector2(15, -27)]), c.darkened(0.2))
	draw_colored_polygon(PackedVector2Array([Vector2(15, -27), Vector2(19, -36), Vector2(21, -25)]), c.darkened(0.2))
	draw_circle(Vector2(18, -21), 1.6, Color.BLACK)


func _draw_swinebot() -> void:
	var metal := Color(0.72, 0.6, 0.55)
	var dark := Color(0.4, 0.33, 0.3)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2(1, 0.35))
	draw_circle(Vector2.ZERO, 40.0, Color(0, 0, 0, 0.22))
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	for lx in [-26.0, -12.0, 12.0, 26.0]:
		draw_rect(Rect2(lx - 4, -18, 8, 18), dark)
	draw_set_transform(Vector2(0, -34), 0.0, Vector2(1, 0.62))
	draw_circle(Vector2.ZERO, 38.0, metal)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	for rx in [-22.0, -8.0, 8.0, 22.0]:
		draw_circle(Vector2(rx, -24), 2.0, dark)
	draw_circle(Vector2(36, -40), 16.0, metal)
	draw_rect(Rect2(46, -44, 10, 10), metal.darkened(0.1))
	draw_circle(Vector2(52, -40), 1.8, dark)
	draw_circle(Vector2(52, -36), 1.8, dark)
	draw_circle(Vector2(38, -46), 3.0, Color(0.3, 1.0, 0.5) if int(t * 2.0) % 2 == 0 else Color(0.2, 0.6, 0.3))
	draw_colored_polygon(PackedVector2Array([Vector2(28, -54), Vector2(34, -64), Vector2(38, -54)]), dark)
	if not tank_off:
		draw_rect(Rect2(-24, -74, 40, 20), Color(0.3, 0.32, 0.35))
		draw_rect(Rect2(-24, -74, 40, 4), Color(0.45, 0.47, 0.5))


func _draw_craft() -> void:
	var hull := Color(0.55, 0.58, 0.62)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2(1, 0.3))
	draw_circle(Vector2.ZERO, 90.0, Color(0.15, 0.1, 0.05, 0.6))
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	draw_colored_polygon(PackedVector2Array([Vector2(-80, -20), Vector2(50, -40), Vector2(90, -20), Vector2(50, 0), Vector2(-70, 4)]), hull)
	draw_colored_polygon(PackedVector2Array([Vector2(-20, -30), Vector2(-60, -80), Vector2(0, -34)]), hull.darkened(0.2))
	draw_colored_polygon(PackedVector2Array([Vector2(20, -40), Vector2(60, -36), Vector2(40, -54)]), Color(0.3, 0.6, 0.8, 0.8))
	# fire and smoke
	for i in 5:
		var ph := fmod(t * 0.6 + i * 0.2, 1.0)
		draw_circle(Vector2(-40 + sin(t + i) * 8.0, -40 - ph * 120.0), 10.0 + ph * 22.0, Color(0.3, 0.3, 0.32, 0.5 * (1.0 - ph)))
	var fl := 0.8 + 0.2 * sin(t * 20.0)
	draw_circle(Vector2(-44, -30), 12.0 * fl, Color(1.0, 0.5, 0.1, 0.9))
	draw_circle(Vector2(-44, -32), 6.0 * fl, Color(1.0, 0.9, 0.4))
