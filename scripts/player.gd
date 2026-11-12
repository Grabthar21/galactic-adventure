extends CharacterBody2D
## The hero (Arthur or Gwen). Movement, 3-hit combo, dodge roll with i-frames, health.

signal hp_changed(hp: int, max_hp: int)
signal died

const SPEED := 119.0           # matched to the traced stride (95 cell px per 0.6 s cycle) so the planted foot does not slide
const SPEED_V2 := 119.0         # cut-out test hero: matched to its stride (tools/cutout)
const SIDE_WALK_FPS := 20.0
# Arthur's Sprixen premium walk: 29-frame loop; at 36 fps one cycle (2 steps) takes 0.8 s,
# which covers ~95 px of ground, so the feet keep pace with SPEED.
const SIDE_WALK_FPS_BY_HERO := {"arthur": 36.0}
# Front/back Sprixen walk strips: fps chosen so a two-step cycle keeps pace with SPEED
const WALK_FPS_BY_DIR := {"down": 37.5, "up": 30.0}   # 30- and 24-frame loops -> 0.8 s per two steps, same cadence as the side walk
const IDLE_SIDE_FPS := 12.0     # 32-frame breathing loops (tools/sprixen/breathe.py) = ~2.7 s per calm breath
var walk_speed := SPEED
const ROLL_DIST := 105.0      # about one character height at gameplay scale
const ROLL_TIME := 0.32
const ROLL_COOLDOWN := 0.15
const CELL := Vector2(98, 148) # frame size in the prepared sheets
const SCALE := 0.75
const SWING_TIMES := [0.26, 0.26, 0.40]  # combo hit 1, 2, 3
const HIT_AT := 0.07

var max_hp := 5
var hp := 5
var weapon := ""               # "", "rod", "sword"
var controllable := false
var facing := Vector2.DOWN     # last movement direction (8-way, normalized)
var anim_dir := "down"         # down / up / side
var state := "move"            # move, attack, roll, hurt, dead
var combo := 0
var attack_t := 0.0
var queued := false
var hit_done := false
var roll_t := 0.0
var roll_cd := 0.0
var roll_vec := Vector2.ZERO
var invuln_t := 0.0
var hurt_t := 0.0
var knock := Vector2.ZERO

var sprite: AnimatedSprite2D
var fx: Node2D
var _masks := {}               # animation name -> skin/hair mask strip (player customization)
var _recolor: ShaderMaterial


func _ready() -> void:
	collision_layer = 4   # player; walls are layer 1, wolves layer 2
	collision_mask = 1
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(30, 14)
	shape.shape = rect
	add_child(shape)
	sprite = AnimatedSprite2D.new()
	sprite.scale = Vector2(SCALE, SCALE)
	sprite.offset = Vector2(0, -CELL.y / 2.0 + 2.0)
	add_child(sprite)
	fx = Node2D.new()
	fx.draw.connect(_draw_fx)
	add_child(fx)


func setup(hero: String) -> void:
	# "arthur_v2" = test of the new cut-out parts: side views from the parts rig,
	# front/back still from the approved Arthur sheet
	var base := "arthur" if hero == "arthur_v2" else hero
	var tex: Texture2D = load("res://art/%s_frames.png" % base)
	walk_speed = SPEED_V2 if hero == "arthur_v2" else SPEED
	var frames := SpriteFrames.new()
	frames.remove_animation("default")
	# Frame rates written by tools/sprixen/build_char.py (art/<hero>_anims.json), if present
	var anims := _load_manifest(base)
	# Sheet rows: 0 idle (front), 1 walk side (faces right), 2 walk down, 3 walk up
	# Front/back: Sprixen strips (art/<hero>_<down|up>_<walk|idle>.png, tools/sprixen) when present,
	# otherwise the original sheet.
	if not _add_strip(frames, "idle_down", "res://art/%s_down_idle.png" % base, _fps(anims, "idle_down", IDLE_SIDE_FPS)):
		_add_anim(frames, tex, "idle_down", [[0, 0], [0, 0], [0, 1], [0, 0], [0, 3], [0, 0], [0, 0], [0, 2]], 4.0)
	# Front/back walks: the sheet's 4th frame repeats the 3rd pose, so play 0,1,2,1 for a clean L-R-L-R step.
	var front_back_order := [0, 1, 2, 1] if base == "arthur" else [0, 1, 2, 3]
	if not _add_strip(frames, "walk_down", "res://art/%s_down_walk.png" % base, _fps(anims, "walk_down", WALK_FPS_BY_DIR.down)):
		_add_anim(frames, tex, "walk_down", front_back_order.map(func(c): return [2, c]), 8.0)
	if not _add_strip(frames, "walk_up", "res://art/%s_up_walk.png" % base, _fps(anims, "walk_up", WALK_FPS_BY_DIR.up)):
		_add_anim(frames, tex, "walk_up", front_back_order.map(func(c): return [3, c]), 8.0)
	if not _add_strip(frames, "idle_up", "res://art/%s_up_idle.png" % base, _fps(anims, "idle_up", IDLE_SIDE_FPS)):
		_add_anim(frames, tex, "idle_up", [[3, 0]], 1.0)
	var side_path := "res://art/%s_side_walk.png" % hero
	if ResourceLoader.exists(side_path):
		# Skinned 12-frame side cycle from tools/walk_skin.py (frame 0 = near heel strike)
		var side_tex: Texture2D = load(side_path)
		var count := int(side_tex.get_width() / CELL.x)
		var cells := []
		for c in count:
			cells.append([0, c])
		var side_fps: float = SIDE_WALK_FPS_BY_HERO.get(hero, SIDE_WALK_FPS)
		if hero == base:
			side_fps = _fps(anims, "walk_side", side_fps)
		_add_anim(frames, side_tex, "walk_side", cells, side_fps)
		var idle_path := "res://art/%s_side_idle.png" % hero
		if ResourceLoader.exists(idle_path):
			# Breathing idle loop (tools/sprixen/build_idle_strip.py); a single-cell file still works
			var idle_tex: Texture2D = load(idle_path)
			var idle_count := int(idle_tex.get_width() / CELL.x)
			var idle_cells := []
			for c in idle_count:
				idle_cells.append([0, c])
			_add_anim(frames, idle_tex, "idle_side", idle_cells, _fps(anims, "idle_side", IDLE_SIDE_FPS) if idle_count > 1 else 1.0)
		else:
			_add_anim(frames, side_tex, "idle_side", [[0, count / 3]], 1.0)
	else:
		_add_anim(frames, tex, "walk_side", [[1, 0], [1, 1], [1, 2], [1, 3]], 8.0)
		_add_anim(frames, tex, "idle_side", [[1, 0]], 1.0)
	sprite.sprite_frames = frames
	_setup_recolor(anims)
	sprite.play("idle_down")


## Skin / hair customization: shaders/recolor.gdshader with the mask strip of the current animation.
func _setup_recolor(anims: Dictionary) -> void:
	_recolor = ShaderMaterial.new()
	_recolor.shader = load("res://shaders/recolor.gdshader")
	if anims.has("skin_ref"):
		var s: Array = anims["skin_ref"]
		_recolor.set_shader_parameter("skin_ref", Vector3(s[0], s[1], s[2]))
	if anims.has("hair_ref"):
		var h: Array = anims["hair_ref"]
		_recolor.set_shader_parameter("hair_ref", Vector3(h[0], h[1], h[2]))
	sprite.material = _recolor
	if not sprite.animation_changed.is_connected(_apply_mask):
		sprite.animation_changed.connect(_apply_mask)
	set_appearance(GameState.skin_color, GameState.hair_color)


## skin / hair: a Color, or null to keep the colours as drawn.
func set_appearance(skin, hair) -> void:
	if _recolor == null:
		return
	_recolor.set_shader_parameter("recolor_skin", skin is Color)
	_recolor.set_shader_parameter("recolor_hair", hair is Color)
	if skin is Color:
		_recolor.set_shader_parameter("skin_color", Vector3(skin.r, skin.g, skin.b))
	if hair is Color:
		_recolor.set_shader_parameter("hair_color", Vector3(hair.r, hair.g, hair.b))
	_apply_mask()


func _apply_mask() -> void:
	if _recolor == null:
		return
	var m = _masks.get(String(sprite.animation))
	_recolor.set_shader_parameter("has_mask", m != null)
	if m != null:
		_recolor.set_shader_parameter("mask_tex", m)


func _load_manifest(hero_name: String) -> Dictionary:
	var path := "res://art/%s_anims.json" % hero_name
	if not FileAccess.file_exists(path):
		return {}
	var data = JSON.parse_string(FileAccess.get_file_as_string(path))
	return data if data is Dictionary else {}


func _fps(anims: Dictionary, key: String, fallback: float) -> float:
	if anims.has(key) and anims[key] is Dictionary and anims[key].has("fps"):
		return float(anims[key]["fps"])
	return fallback


## Adds a one-row strip of CELL-sized frames as a looping animation; false if the file is missing.
func _add_strip(frames: SpriteFrames, anim: String, path: String, fps: float) -> bool:
	if not ResourceLoader.exists(path):
		return false
	var t: Texture2D = load(path)
	var cells := []
	for c in int(t.get_width() / CELL.x):
		cells.append([0, c])
	_add_anim(frames, t, anim, cells, fps)
	return true


func _add_anim(frames: SpriteFrames, tex: Texture2D, anim: String, cells: Array, fps: float) -> void:
	# a strip built by tools/sprixen has a matching <strip>_mask.png for skin/hair recolouring
	var mask_path := tex.resource_path.replace(".png", "_mask.png")
	if tex.resource_path.ends_with(".png") and ResourceLoader.exists(mask_path):
		_masks[anim] = load(mask_path)
	else:
		_masks.erase(anim)
	frames.add_animation(anim)
	frames.set_animation_speed(anim, fps)
	frames.set_animation_loop(anim, true)
	for c in cells:
		var at := AtlasTexture.new()
		at.atlas = tex
		at.region = Rect2(c[1] * CELL.x, c[0] * CELL.y, CELL.x, CELL.y)
		frames.add_frame(anim, at)


func heal_full() -> void:
	hp = max_hp
	state = "move"
	invuln_t = 0.0
	sprite.modulate = Color.WHITE
	sprite.rotation = 0.0
	hp_changed.emit(hp, max_hp)


func is_invulnerable() -> bool:
	return state == "roll" or invuln_t > 0.0 or state == "dead"


func damage_value() -> int:
	var base := 2 if weapon == "sword" else 1
	return base + (1 if combo == 3 else 0)


func take_hit(amount: int, from_pos: Vector2) -> void:
	if is_invulnerable():
		return
	hp = max(hp - amount, 0)
	hp_changed.emit(hp, max_hp)
	knock = (global_position - from_pos).normalized() * 420.0
	invuln_t = 0.9
	if hp <= 0:
		state = "dead"
		velocity = Vector2.ZERO
		died.emit()
	else:
		state = "hurt"
		hurt_t = 0.2


func _physics_process(delta: float) -> void:
	invuln_t = max(invuln_t - delta, 0.0)
	roll_cd = max(roll_cd - delta, 0.0)
	var input := Vector2.ZERO
	if controllable:
		input = Input.get_vector("move_left", "move_right", "move_up", "move_down")

	match state:
		"move":
			velocity = input * walk_speed
			if input.length() > 0.1:
				facing = input.normalized()
			if controllable and weapon != "" and Input.is_action_just_pressed("attack"):
				_start_attack(1)
			elif controllable and Input.is_action_just_pressed("dodge") and roll_cd <= 0.0:
				_start_roll(input)
		"attack":
			attack_t += delta
			velocity = facing * (60.0 if attack_t < 0.1 else 0.0)
			if Input.is_action_just_pressed("attack") and controllable:
				queued = true
			if not hit_done and attack_t >= HIT_AT:
				hit_done = true
				_apply_hit()
			if controllable and Input.is_action_just_pressed("dodge") and roll_cd <= 0.0 and attack_t > 0.12:
				_start_roll(input)
			elif attack_t >= SWING_TIMES[combo - 1]:
				if queued and combo < 3:
					_start_attack(combo + 1)
				else:
					state = "move"
					combo = 0
			fx.queue_redraw()
		"roll":
			roll_t += delta
			velocity = roll_vec * (ROLL_DIST / ROLL_TIME)
			sprite.rotation = (roll_t / ROLL_TIME) * TAU * (1.0 if roll_vec.x >= 0.0 else -1.0)
			if roll_t >= ROLL_TIME:
				state = "move"
				sprite.rotation = 0.0
				roll_cd = ROLL_COOLDOWN
		"hurt":
			hurt_t -= delta
			velocity = knock
			knock = knock.move_toward(Vector2.ZERO, 2000.0 * delta)
			if hurt_t <= 0.0:
				state = "move"
		"dead":
			velocity = knock
			knock = knock.move_toward(Vector2.ZERO, 2000.0 * delta)

	move_and_slide()
	_update_anim()
	sprite.modulate.a = 0.75 if state == "roll" else (0.35 if (invuln_t > 0.0 and int(invuln_t * 14.0) % 2 == 0) else 1.0)


func _start_attack(n: int) -> void:
	state = "attack"
	combo = n
	attack_t = 0.0
	queued = false
	hit_done = false
	var input := Input.get_vector("move_left", "move_right", "move_up", "move_down")
	if input.length() > 0.1:
		facing = input.normalized()


func _start_roll(input: Vector2) -> void:
	state = "roll"
	roll_t = 0.0
	combo = 0
	roll_vec = input.normalized() if input.length() > 0.1 else facing
	facing = roll_vec


func _apply_hit() -> void:
	var reach := 95.0 if combo < 3 else 115.0
	for e in get_tree().get_nodes_in_group("enemies"):
		if not is_instance_valid(e) or e.dead:
			continue
		var to: Vector2 = e.global_position - global_position
		to.y *= 1.4  # top-down perspective: vertical distances read shorter
		if to.length() <= reach and (to.length() < 30.0 or facing.angle_to(to.normalized()) < deg_to_rad(75)):
			e.take_hit(damage_value(), global_position, 260.0 if combo < 3 else 520.0)


func _update_anim() -> void:
	if sprite.sprite_frames == null:
		return
	var d := facing
	if abs(d.x) > abs(d.y) * 0.9:
		anim_dir = "side"
		sprite.flip_h = d.x < 0.0
	else:
		anim_dir = "down" if d.y > 0.0 else "up"
		sprite.flip_h = false
	var moving := velocity.length() > 20.0 and state == "move"
	var anim := ("walk_" if moving or state == "roll" else "idle_") + anim_dir
	if sprite.animation != anim:
		sprite.play(anim)
	# legs keep pace with actual speed (e.g. a half-pushed stick walks slower, not skating)
	sprite.speed_scale = clampf(velocity.length() / walk_speed, 0.5, 1.5) if moving else 1.0


func _draw_fx() -> void:
	if state != "attack":
		return
	var p := clampf(attack_t / SWING_TIMES[combo - 1], 0.0, 1.0)
	var center := Vector2(0, -38)
	var base := facing.angle()
	var arc := deg_to_rad(150.0 if combo == 3 else 110.0)
	var dir := 1.0 if combo % 2 == 1 else -1.0
	var start := base - dir * arc / 2.0
	var cur := start + dir * arc * minf(p * 1.8, 1.0)
	var length := 70.0 if weapon == "rod" else 78.0
	var col := Color(0.75, 0.75, 0.78) if weapon == "rod" else Color(0.85, 0.9, 1.0)
	# swoosh trail
	var pts := PackedVector2Array()
	var steps := 10
	for i in steps + 1:
		var a := lerpf(start, cur, float(i) / steps)
		pts.append(center + Vector2.from_angle(a) * length)
	if pts.size() > 1:
		fx.draw_polyline(pts, Color(1, 1, 1, 0.55 * (1.0 - p)), 10.0 if combo == 3 else 6.0, true)
	# weapon
	var tip := center + Vector2.from_angle(cur) * length
	fx.draw_line(center + Vector2.from_angle(cur) * 14.0, tip, col, 5.0 if weapon == "rod" else 6.0, true)
	if weapon == "sword":
		var hilt := center + Vector2.from_angle(cur) * 18.0
		var perp := Vector2.from_angle(cur + PI / 2.0) * 9.0
		fx.draw_line(hilt - perp, hilt + perp, Color(0.8, 0.65, 0.2), 4.0, true)
