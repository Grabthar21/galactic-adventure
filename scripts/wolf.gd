extends CharacterBody2D
## Wolf enemy (placeholder art drawn in code). Approaches, crouches to telegraph, then lunges.

signal defeated

const SPEED := 120.0   # a little faster than the hero's walk, slower than a dodge
const LUNGE_SPEED := 620.0
const LUNGE_TIME := 0.28
const TELEGRAPH := 0.65
const MAX_ATTACKERS := 2
static var attackers := 0

var hp := 4
var dead := false
var target: Node2D
var state := "approach"   # approach, circle, telegraph, lunge, recover, stagger, dying
var t := 0.0
var lunge_dir := Vector2.ZERO
var hit_player := false
var knock := Vector2.ZERO
var flash := 0.0
var face := 1.0
var circle_sign := 1.0
var holding_token := false
var bob := 0.0


func _ready() -> void:
	add_to_group("enemies")
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(44, 14)
	shape.shape = rect
	add_child(shape)
	collision_layer = 2
	collision_mask = 1
	circle_sign = 1.0 if randf() < 0.5 else -1.0
	t = randf() * 0.5


func _release_token() -> void:
	if holding_token:
		holding_token = false
		attackers = max(attackers - 1, 0)


func take_hit(amount: int, from_pos: Vector2, force: float) -> void:
	if dead:
		return
	hp -= amount
	flash = 0.15
	knock = (global_position - from_pos).normalized() * force
	if state == "telegraph" or state == "lunge":
		_release_token()
	if hp <= 0:
		dead = true
		state = "dying"
		t = 0.0
		_release_token()
		collision_layer = 0
		remove_from_group("enemies")
	else:
		state = "stagger"
		t = 0.0


func _physics_process(delta: float) -> void:
	t += delta
	flash = maxf(flash - delta, 0.0)
	bob += delta
	if target == null:
		return
	var to: Vector2 = target.global_position - global_position
	var dist := to.length()
	match state:
		"approach":
			velocity = to.normalized() * SPEED
			if dist < 170.0:
				state = "circle"
				t = 0.0
		"circle":
			var tangent := Vector2(-to.y, to.x).normalized() * circle_sign
			var radial := to.normalized() * (dist - 150.0) * 2.0
			velocity = (tangent * 90.0 + radial).limit_length(SPEED)
			if dist > 260.0:
				state = "approach"
			elif t > 0.9 and attackers < MAX_ATTACKERS and target.state != "dead":
				attackers += 1
				holding_token = true
				state = "telegraph"
				t = 0.0
		"telegraph":
			velocity = Vector2.ZERO
			lunge_dir = to.normalized()
			if t >= TELEGRAPH:
				state = "lunge"
				t = 0.0
				hit_player = false
		"lunge":
			velocity = lunge_dir * LUNGE_SPEED
			var feet: Vector2 = target.global_position - global_position
			feet.y *= 1.6
			if not hit_player and feet.length() < 46.0 and not target.is_invulnerable():
				hit_player = true
				target.take_hit(1, global_position)
			if t >= LUNGE_TIME:
				state = "recover"
				t = 0.0
				_release_token()
		"recover":
			velocity = velocity.move_toward(Vector2.ZERO, 1500.0 * delta)
			if t >= 0.8:
				state = "circle"
				t = 0.0
				circle_sign = -circle_sign
		"stagger":
			velocity = knock
			knock = knock.move_toward(Vector2.ZERO, 1800.0 * delta)
			if t >= 0.35:
				state = "circle"
				t = 0.0
		"dying":
			velocity = knock
			knock = knock.move_toward(Vector2.ZERO, 1800.0 * delta)
			modulate.a = 1.0 - t / 0.6
			if t >= 0.6:
				defeated.emit()
				queue_free()
	if abs(velocity.x) > 5.0:
		face = signf(velocity.x)
	elif state == "telegraph":
		face = signf(to.x) if abs(to.x) > 1.0 else face
	move_and_slide()
	queue_redraw()


func _exit_tree() -> void:
	_release_token()


func _draw() -> void:
	var crouch := 6.0 if state == "telegraph" else 0.0
	var run := sin(bob * 14.0) * 3.0 if velocity.length() > 30.0 else 0.0
	var body_col := Color(0.42, 0.42, 0.46)
	var belly := Color(0.62, 0.62, 0.66)
	if flash > 0.0:
		body_col = Color.WHITE
		belly = Color.WHITE
	elif state == "telegraph" and int(t * 12.0) % 2 == 0:
		body_col = Color(0.75, 0.3, 0.3)
	# shadow
	draw_set_transform(Vector2.ZERO, 0.0, Vector2(1, 0.35))
	draw_circle(Vector2(0, 0), 34.0, Color(0, 0, 0, 0.25))
	draw_set_transform(Vector2(0, crouch), 0.0, Vector2(face, 1))
	# legs
	for lx in [-18.0, -8.0, 10.0, 20.0]:
		var sw: float = run if int(lx) % 2 == 0 else -run
		draw_line(Vector2(lx, -16), Vector2(lx + sw, -1), body_col.darkened(0.3), 5.0)
	# tail
	draw_line(Vector2(-26, -26), Vector2(-42, -34 + run), body_col, 7.0)
	# body
	draw_set_transform(Vector2(0, crouch - 24), 0.0, Vector2(face * 1.0, 0.55))
	draw_circle(Vector2.ZERO, 30.0, body_col)
	draw_set_transform(Vector2(0, crouch), 0.0, Vector2(face, 1))
	draw_circle(Vector2(4, -18), 12.0, belly)
	# head
	draw_circle(Vector2(30, -36), 13.0, body_col)
	draw_colored_polygon(PackedVector2Array([Vector2(36, -40), Vector2(52, -32), Vector2(38, -28)]), body_col)
	draw_colored_polygon(PackedVector2Array([Vector2(22, -44), Vector2(25, -58), Vector2(31, -46)]), body_col.darkened(0.15))
	draw_colored_polygon(PackedVector2Array([Vector2(30, -46), Vector2(35, -58), Vector2(38, -44)]), body_col.darkened(0.15))
	draw_circle(Vector2(36, -38), 2.2, Color(1.0, 0.85, 0.2) if state != "telegraph" else Color(1, 0.2, 0.1))
	draw_circle(Vector2(51, -33), 2.5, Color(0.1, 0.1, 0.1))
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	if state == "telegraph":
		var f := ThemeDB.fallback_font
		draw_string(f, Vector2(-6, -70), "!", HORIZONTAL_ALIGNMENT_LEFT, -1, 30, Color(1, 0.25, 0.2))
