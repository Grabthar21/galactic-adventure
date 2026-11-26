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
const RUN_MULT := 1.8           # run speed = walk speed x1.8; run strips' fps come from art/<hero>_anims.json
# Default way of moving. "run" (the family's choice, 24 Nov): the run strips at walk_speed x RUN_MULT.
# "walk" is kept in the back pocket: the walk strips at walk_speed. Falls back to walking if a
# hero has no run strips yet.
const DEFAULT_GAIT := "run"
var running := false
# Dodge roll (Space / gamepad A): a short burst a little faster than running. Enemy attacks miss
# during the roll's i-frames; walls stop it like normal movement (move_and_slide, wall layer 1).
# The roll bursts off the mark and slows as he comes up: speed falls in a straight line from
# ROLL_BURST x the average at the start to (2 - ROLL_BURST) x at the end. With 192 px in 0.36 s
# (25 Nov: the distance doubled, same timing) that is ~907 px/s off the mark (about 4.2x the run),
# easing to ~160 px/s; the average is ~533 px/s.
const ROLL_BURST := 1.7
const ROLL_TIME := 0.36
const ROLL_DIST := 192.0        # about 1.7 of Arthur's on-screen heights
const ROLL_IFRAMES := 0.30      # invulnerable for the first 0.30 s; the last ~0.06 s (getting up) is not
const ROLL_COOLDOWN := 0.25
const CELL := Vector2(98, 148) # frame size in the prepared sheets
const SCALE := 0.75
# strips from tools/sprixen may be drawn larger than the 98x148 cells (the smooth Sprixen-style
# look, e.g. 147x222): the cell is read from each strip's height and drawn at SCALE * 148 / height
var _anim_cell := {}           # animation name -> Vector2 cell size
# 3-slash combo (left click / J / gamepad X). Each click during a swing queues the next slash,
# which starts the moment the current one ends -- the attack strips are cut from one continuous
# Sprixen take, so slash 2 begins in the pose slash 1 ends in. Timings below are the fallback when
# a hero has no attack strips; with strips, each slash lasts its strip (frames / fps) and lands
# on the frame the weapon track marks as the hit.
const SWING_TIMES := [0.26, 0.26, 0.40]  # combo hit 1, 2, 3
const HIT_AT := 0.07
const ATTACK_CANCEL := 0.12     # a dodge can cut a swing short after this long
const REF_WEAPON_LEN := 64.0    # game px, grip to tip, of a length_scale 1.0 weapon (no-track fallback)
const TRAIL_LIFE := 0.11        # s a point of the swing trail lasts

var max_hp := 5
var hp := 5
var weapon: MeleeWeapon = null # equipped melee weapon (res://weapons/*.tres); null = unarmed
var controllable := false
var facing := Vector2.DOWN     # last movement direction (8-way, normalized)
var anim_dir := "down"         # down / up / side
var state := "move"            # move, attack, roll, hurt, dead
var combo := 0
var attack_t := 0.0
var queued := false
var hit_done := false
var recover_t := 0.0
var _attack_anim := ""         # attack strip playing ("" = none: the fallback swing)
var _tracks := {}              # attack anim name -> weapon track {frames, hit, full_len}
var _trail: Array = []         # [local tip position, age] of the swing trail
var fx_back: Node2D            # weapon drawn behind the body (a swing on his far side)
var roll_t := 0.0
var roll_cd := 0.0
var roll_vec := Vector2.ZERO
var invuln_t := 0.0
var roll_time := ROLL_TIME
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
	fx_back = Node2D.new()
	fx_back.draw.connect(_draw_weapon.bind(true))
	add_child(fx_back)
	sprite = AnimatedSprite2D.new()
	sprite.scale = Vector2(SCALE, SCALE)
	sprite.offset = Vector2(0, -CELL.y / 2.0 + 2.0)
	sprite.animation_changed.connect(_apply_cell)
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
	roll_time = ROLL_TIME
	var frames := SpriteFrames.new()
	frames.remove_animation("default")
	# Hairstyle: tools/sprixen builds a full strip set per style as art/<hero>__<style>_*
	var look := base
	if GameState.hairstyle != "" and ResourceLoader.exists("res://art/%s__%s_down_walk.png" % [base, GameState.hairstyle]):
		look = "%s__%s" % [base, GameState.hairstyle]
	# Frame rates written by tools/sprixen/build_char.py (art/<look>_anims.json), if present
	var anims := _load_manifest(look)
	# Sheet rows: 0 idle (front), 1 walk side (faces right), 2 walk down, 3 walk up
	# Front/back: Sprixen strips (art/<hero>_<down|up>_<walk|idle>.png, tools/sprixen) when present,
	# otherwise the original sheet.
	if not _add_strip(frames, "idle_down", "res://art/%s_down_idle.png" % look, _fps(anims, "idle_down", IDLE_SIDE_FPS)):
		_add_anim(frames, tex, "idle_down", [[0, 0], [0, 0], [0, 1], [0, 0], [0, 3], [0, 0], [0, 0], [0, 2]], 4.0)
	# Front/back walks: the sheet's 4th frame repeats the 3rd pose, so play 0,1,2,1 for a clean L-R-L-R step.
	var front_back_order := [0, 1, 2, 1] if base == "arthur" else [0, 1, 2, 3]
	if not _add_strip(frames, "walk_down", "res://art/%s_down_walk.png" % look, _fps(anims, "walk_down", WALK_FPS_BY_DIR.down)):
		_add_anim(frames, tex, "walk_down", front_back_order.map(func(c): return [2, c]), 8.0)
	if not _add_strip(frames, "walk_up", "res://art/%s_up_walk.png" % look, _fps(anims, "walk_up", WALK_FPS_BY_DIR.up)):
		_add_anim(frames, tex, "walk_up", front_back_order.map(func(c): return [3, c]), 8.0)
	# Run strips (tools/sprixen, art/<hero>_<side|down|up>_run.png); optional
	for d in ["side", "down", "up"]:
		# run cells are wider than walk cells (a run's stride reaches further): width from the manifest
		var rw := 0.0
		if anims.has("run_" + d) and anims["run_" + d] is Dictionary and anims["run_" + d].has("cell_w"):
			rw = float(anims["run_" + d]["cell_w"])
		_add_strip(frames, "run_" + d, "res://art/%s_%s_run.png" % [look, d], _fps(anims, "run_" + d, 30.0), rw)
		# Roll strips (optional): played once per dodge, timed to last exactly roll_time
		var key: String = "roll_" + d
		var cw := float(anims[key]["cell_w"]) if anims.has(key) and anims[key] is Dictionary and anims[key].has("cell_w") else rw
		if _add_strip(frames, key, "res://art/%s_%s_roll.png" % [look, d], 30.0, cw):
			frames.set_animation_speed(key, frames.get_frame_count(key) / roll_time)
			frames.set_animation_loop(key, false)
	_load_attacks(frames, look, anims)
	if not _add_strip(frames, "idle_up", "res://art/%s_up_idle.png" % look, _fps(anims, "idle_up", IDLE_SIDE_FPS)):
		_add_anim(frames, tex, "idle_up", [[3, 0]], 1.0)
	var side_path := "res://art/%s_side_walk.png" % (look if hero == base else hero)
	if ResourceLoader.exists(side_path):
		# Skinned 12-frame side cycle from tools/walk_skin.py (frame 0 = near heel strike)
		var side_tex: Texture2D = load(side_path)
		var count := int(side_tex.get_width() / _strip_cell(side_tex).x)
		var cells := []
		for c in count:
			cells.append([0, c])
		var side_fps: float = SIDE_WALK_FPS_BY_HERO.get(hero, SIDE_WALK_FPS)
		if hero == base:
			side_fps = _fps(anims, "walk_side", side_fps)
		_add_anim(frames, side_tex, "walk_side", cells, side_fps, _strip_cell(side_tex))
		var idle_path := "res://art/%s_side_idle.png" % (look if hero == base else hero)
		if ResourceLoader.exists(idle_path):
			# Breathing idle loop (tools/sprixen/build_idle_strip.py); a single-cell file still works
			var idle_tex: Texture2D = load(idle_path)
			var idle_count := int(idle_tex.get_width() / _strip_cell(idle_tex).x)
			var idle_cells := []
			for c in idle_count:
				idle_cells.append([0, c])
			_add_anim(frames, idle_tex, "idle_side", idle_cells, _fps(anims, "idle_side", IDLE_SIDE_FPS) if idle_count > 1 else 1.0, _strip_cell(idle_tex))
		else:
			_add_anim(frames, side_tex, "idle_side", [[0, count / 3]], 1.0, _strip_cell(side_tex))
	else:
		_add_anim(frames, tex, "walk_side", [[1, 0], [1, 1], [1, 2], [1, 3]], 8.0)
		_add_anim(frames, tex, "idle_side", [[1, 0]], 1.0)
	sprite.sprite_frames = frames
	_setup_recolor(anims)
	sprite.play("idle_down")
	_apply_cell()


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
func _add_strip(frames: SpriteFrames, anim: String, path: String, fps: float, cell_w: float = 0.0) -> bool:
	if not ResourceLoader.exists(path):
		return false
	var t: Texture2D = load(path)
	var cell := _strip_cell(t)
	if cell_w > 0.0:
		cell.x = cell_w
	var cells := []
	for c in int(t.get_width() / cell.x):
		cells.append([0, c])
	_add_anim(frames, t, anim, cells, fps, cell)
	return true


## A one-row strip's cell: its height, with the 98:148 cell shape.
func _strip_cell(t: Texture2D) -> Vector2:
	var h := float(t.get_height())
	return Vector2(round(h * CELL.x / CELL.y), h)


## Size, anchor and filtering follow the current animation's cell (big smooth strips are drawn
## smaller with smooth filtering; the original 98x148 cells keep the crisp pixel look).
func _apply_cell() -> void:
	var cell: Vector2 = _anim_cell.get(String(sprite.animation), CELL)
	var k := CELL.y / cell.y
	sprite.scale = Vector2(SCALE * k, SCALE * k)
	sprite.offset = Vector2(0, -cell.y / 2.0 + 2.0 / k)
	sprite.texture_filter = CanvasItem.TEXTURE_FILTER_PARENT_NODE if cell.y == CELL.y else CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS


func _add_anim(frames: SpriteFrames, tex: Texture2D, anim: String, cells: Array, fps: float, cell: Vector2 = CELL) -> void:
	_anim_cell[anim] = cell
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
		at.region = Rect2(c[1] * cell.x, c[0] * cell.y, cell.x, cell.y)
		frames.add_frame(anim, at)


func heal_full() -> void:
	hp = max_hp
	state = "move"
	invuln_t = 0.0
	sprite.modulate = Color.WHITE
	sprite.rotation = 0.0
	hp_changed.emit(hp, max_hp)


func is_invulnerable() -> bool:
	return (state == "roll" and roll_t < ROLL_IFRAMES) or invuln_t > 0.0 or state == "dead"


## Equip a melee weapon: a MeleeWeapon resource, or its id (res://weapons/<id>.tres); "" or null
## = unarmed. Any weapon with moveset "sword" uses the same slash animations -- the game draws the
## weapon's own picture in his hand, so swapping weapons needs no new art of the hero.
func equip(w) -> void:
	if w is String:
		w = load("res://weapons/%s.tres" % w) if w != "" else null
	weapon = w
	fx.queue_redraw()
	fx_back.queue_redraw()


func weapon_id() -> String:
	return weapon.id if weapon != null else ""


func damage_value() -> int:
	return int(_combo_stat(weapon.damage if weapon else [1, 1, 2], 1))


func _combo_stat(arr: Array, fallback):
	if arr.is_empty():
		return fallback
	return arr[clampi(combo - 1, 0, arr.size() - 1)]


## Attack strips (tools/sprixen weapon_track.py): art/<look>_<dir>_attack<1-3>.png, plus an
## optional art/<look>_<dir>_attack_rec.png (back to the stance when no further click comes),
## and the weapon track art/<look>_<dir>_attack_track.json.
func _load_attacks(frames: SpriteFrames, look: String, anims: Dictionary) -> void:
	for d in ["side", "down", "up"]:
		var track_path := "res://art/%s_%s_attack_track.json" % [look, d]
		var track = null
		if FileAccess.file_exists(track_path):
			track = JSON.parse_string(FileAccess.get_file_as_string(track_path))
		for part in ["attack1", "attack2", "attack3", "attack_rec"]:
			var anim: String = part + "_" + d
			var cw := 0.0
			if anims.has(anim) and anims[anim] is Dictionary and anims[anim].has("cell_w"):
				cw = float(anims[anim]["cell_w"])
			if _add_strip(frames, anim, "res://art/%s_%s_%s.png" % [look, d, part], _fps(anims, anim, 24.0), cw):
				frames.set_animation_loop(anim, false)
				if track is Dictionary and track.has(part):
					var t: Dictionary = track[part]
					t["full_len"] = float(track.get("full_len", 0.0))
					_tracks[anim] = t


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
			running = DEFAULT_GAIT == "run" and input.length() > 0.1 and sprite.sprite_frames != null \
				and sprite.sprite_frames.has_animation("run_" + anim_dir)
			velocity = input * walk_speed * (RUN_MULT if running else 1.0)
			if input.length() > 0.1:
				facing = input.normalized()
			if controllable and weapon != null and Input.is_action_just_pressed("attack"):
				_start_attack(1)
			elif controllable and Input.is_action_just_pressed("dodge") and roll_cd <= 0.0:
				_start_roll(input)
		"attack":
			attack_t += delta
			velocity = facing * (60.0 if attack_t < 0.1 else 0.0)
			if Input.is_action_just_pressed("attack") and controllable and combo < 3:
				queued = true
			if not hit_done and attack_t >= hit_time():
				hit_done = true
				_apply_hit()
			if controllable and Input.is_action_just_pressed("dodge") and roll_cd <= 0.0 and attack_t > ATTACK_CANCEL:
				_start_roll(input)
			elif attack_t >= swing_time():
				if queued and combo < 3:
					_start_attack(combo + 1)
				else:
					_end_attack()
		"recover":
			# easing back to the stance after the last slash; any input takes over at once
			recover_t += delta
			velocity = Vector2.ZERO
			if controllable and weapon != null and Input.is_action_just_pressed("attack"):
				_start_attack(1)
			elif controllable and Input.is_action_just_pressed("dodge") and roll_cd <= 0.0:
				_start_roll(input)
			elif input.length() > 0.1 or recover_t >= _strip_time("attack_rec_" + anim_dir):
				state = "move"
				combo = 0
				_attack_anim = ""
		"roll":
			# distance covered so far: ROLL_DIST * (B*u - (B-1)*u^2), u = share of the roll's time;
			# this frame's velocity moves exactly the step between, whatever the frame rate
			var u0: float = clampf(roll_t / roll_time, 0.0, 1.0)
			roll_t += delta
			var u1: float = clampf(roll_t / roll_time, 0.0, 1.0)
			var step: float = ROLL_DIST * ((ROLL_BURST * u1 - (ROLL_BURST - 1.0) * u1 * u1)
				- (ROLL_BURST * u0 - (ROLL_BURST - 1.0) * u0 * u0))
			velocity = roll_vec * (step / maxf(delta, 0.0001))
			if not _has_roll_art():   # placeholder until the roll strips exist: spin the sprite
				sprite.rotation = (roll_t / roll_time) * TAU * (1.0 if roll_vec.x >= 0.0 else -1.0)
			if roll_t >= roll_time:
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
	_update_trail(delta)
	fx.queue_redraw()
	fx_back.queue_redraw()
	sprite.modulate.a = 0.75 if (state == "roll" and not _has_roll_art()) else (0.35 if (invuln_t > 0.0 and int(invuln_t * 14.0) % 2 == 0) else 1.0)


func _start_attack(n: int) -> void:
	state = "attack"
	combo = n
	attack_t = 0.0
	queued = false
	hit_done = false
	var input := Input.get_vector("move_left", "move_right", "move_up", "move_down")
	if input.length() > 0.1 and n == 1:
		facing = input.normalized()   # aim the first slash; the rest of the combo keeps its line
	_update_anim()
	var anim := "attack%d_%s" % [n, anim_dir]
	_attack_anim = anim if sprite.sprite_frames != null and sprite.sprite_frames.has_animation(anim) else ""
	if _attack_anim != "":
		sprite.play(_attack_anim)
		sprite.frame = 0
		sprite.speed_scale = _weapon_speed()


func _end_attack() -> void:
	var rec := "attack_rec_" + anim_dir
	if sprite.sprite_frames != null and sprite.sprite_frames.has_animation(rec):
		state = "recover"
		recover_t = 0.0
		_attack_anim = rec
		sprite.play(rec)
		sprite.frame = 0
		sprite.speed_scale = _weapon_speed()
	else:
		state = "move"
		combo = 0
		_attack_anim = ""


func _weapon_speed() -> float:
	return weapon.speed if weapon != null and weapon.speed > 0.0 else 1.0


## Seconds a strip takes at the weapon's speed (0 if missing).
func _strip_time(anim: String) -> float:
	if sprite.sprite_frames == null or not sprite.sprite_frames.has_animation(anim):
		return 0.0
	return sprite.sprite_frames.get_frame_count(anim) / sprite.sprite_frames.get_animation_speed(anim) / _weapon_speed()


## How long the current slash lasts.
func swing_time() -> float:
	if _attack_anim.begins_with("attack") and _attack_anim != "" and not _attack_anim.begins_with("attack_rec"):
		return _strip_time(_attack_anim)
	return SWING_TIMES[combo - 1] / _weapon_speed()


## When in the current slash the blow lands.
func hit_time() -> float:
	if _tracks.has(_attack_anim) and _tracks[_attack_anim].has("hit"):
		var fps := sprite.sprite_frames.get_animation_speed(_attack_anim) * _weapon_speed()
		return float(_tracks[_attack_anim]["hit"]) / fps
	return HIT_AT / _weapon_speed()


func _start_roll(input: Vector2) -> void:
	state = "roll"
	roll_t = 0.0
	combo = 0
	_attack_anim = ""
	roll_vec = input.normalized() if input.length() > 0.1 else facing
	facing = roll_vec
	_update_anim()
	if _has_roll_art():
		sprite.frame = 0
		sprite.play()


func _has_roll_art() -> bool:
	return sprite.sprite_frames != null and sprite.sprite_frames.has_animation("roll_" + anim_dir)


func _apply_hit() -> void:
	var reach: float = _combo_stat(weapon.reach if weapon else [], 95.0 if combo < 3 else 115.0)
	var arc: float = _combo_stat(weapon.arc_half_deg if weapon else [], 75.0)
	var kb: float = _combo_stat(weapon.knockback if weapon else [], 260.0 if combo < 3 else 520.0)
	for e in get_tree().get_nodes_in_group("enemies"):
		if not is_instance_valid(e) or e.dead:
			continue
		var to: Vector2 = e.global_position - global_position
		to.y *= 1.4  # top-down perspective: vertical distances read shorter
		if to.length() <= reach and (to.length() < 30.0 or absf(facing.angle_to(to.normalized())) < deg_to_rad(arc)):
			e.take_hit(damage_value(), global_position, kb)


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
	var base_speed := walk_speed
	if (moving or state == "roll") and DEFAULT_GAIT == "run" and sprite.sprite_frames.has_animation("run_" + anim_dir):
		anim = "run_" + anim_dir
		base_speed = walk_speed * RUN_MULT
	if (state == "attack" or state == "recover") and _attack_anim != "":
		if sprite.animation != _attack_anim:
			sprite.play(_attack_anim)
		sprite.speed_scale = _weapon_speed()
		return
	if state == "roll" and _has_roll_art():
		anim = "roll_" + anim_dir    # one roll per dodge: its fps is set so it lasts roll_time
		if sprite.animation != anim:
			sprite.play(anim)
		sprite.speed_scale = 1.0
		return
	if sprite.animation != anim:
		sprite.play(anim)
	# legs keep pace with actual speed (e.g. a half-pushed stick walks slower, not skating)
	sprite.speed_scale = clampf(velocity.length() / base_speed, 0.5, 2.0) if moving else 1.0


func _draw_fx() -> void:
	_draw_weapon(false)


## Where the weapon is this instant, in this node's space: {grip, angle (grip->tip), length (px,
## after foreshortening), behind}. From the attack strip's weapon track, blended between its
## frames so the blade moves smoothly even between drawn frames; or the code swing when the
## hero has no attack strips. Empty when no weapon is out.
func weapon_pose() -> Dictionary:
	if weapon == null or not (state == "attack" or state == "recover"):
		return {}
	var full := REF_WEAPON_LEN * weapon.length_scale
	if _tracks.has(_attack_anim) and String(sprite.animation) == _attack_anim:
		var tr: Dictionary = _tracks[_attack_anim]
		var fr: Array = tr["frames"]
		if fr.is_empty():
			return {}
		var i := clampi(sprite.frame, 0, fr.size() - 1)
		var j := mini(i + 1, fr.size() - 1)
		var u := sprite.frame_progress if j != i else 0.0
		var a: Dictionary = fr[i]
		var b: Dictionary = fr[j]
		if a.get("h", false):
			return {}     # the blade can't be seen in this frame (behind him, or put away)
		if b.get("h", false):
			b = a
		var cell: Vector2 = _anim_cell.get(_attack_anim, CELL)
		var g := Vector2(a["g"][0], a["g"][1]).lerp(Vector2(b["g"][0], b["g"][1]), u)
		# the track's angles run on continuously through the swing (no wrap at 360), so a plain
		# blend turns the blade the way the slash turns
		var ang := deg_to_rad(lerpf(a["a"], b["a"], u))
		var vis := lerpf(a["l"], b["l"], u)
		var full_c: float = tr["full_len"] if tr["full_len"] > 0.0 else maxf(vis, 1.0)
		var local := (g - cell / 2.0 + sprite.offset) * sprite.scale
		if sprite.flip_h:
			local.x = -local.x
			ang = PI - ang
		var k := sprite.scale.x * weapon.length_scale
		return {"grip": local, "angle": ang, "length": vis * k, "full": full_c * k,
			"behind": bool(a["b"]) if u < 0.5 else bool(b["b"])}
	if state != "attack":
		return {}
	# fallback swing: an arc in front of him
	var p := clampf(attack_t / swing_time(), 0.0, 1.0)
	var center := Vector2(0, -38)
	var arc := deg_to_rad(150.0 if combo == 3 else 110.0)
	var dir := 1.0 if combo % 2 == 1 else -1.0
	var start := facing.angle() - dir * arc / 2.0
	var cur := start + dir * arc * (1.0 - pow(1.0 - minf(p * 1.6, 1.0), 3.0))
	return {"grip": center + Vector2.from_angle(cur) * 12.0, "angle": cur, "length": full,
		"full": full, "behind": facing.y < -0.5}


func _update_trail(delta: float) -> void:
	for t in _trail:
		t[3] += delta
	while not _trail.is_empty() and _trail[0][3] > TRAIL_LIFE:
		_trail.pop_front()
	var pose := weapon_pose()
	if pose.is_empty() or state != "attack":
		return
	_trail.append([pose.grip, pose.angle, pose.length * 0.92, 0.0])


func _draw_weapon(back: bool) -> void:
	var canvas: Node2D = fx_back if back else fx
	var pose := weapon_pose()
	# swing trail, in front of everything
	if not back and _trail.size() > 1 and weapon != null:
		# the tip's path between samples follows the swing's curve (grip, angle and reach blended)
		const SUB := 5
		for i in range(1, _trail.size()):
			var p0: Array = _trail[i - 1]
			var p1: Array = _trail[i]
			var prev: Vector2 = p0[0] + Vector2.from_angle(p0[1]) * p0[2]
			for k in range(1, SUB + 1):
				var u := float(k) / SUB
				var g: Vector2 = (p0[0] as Vector2).lerp(p1[0], u)
				var tip: Vector2 = g + Vector2.from_angle(lerp_angle(p0[1], p1[1], u)) * lerpf(p0[2], p1[2], u)
				var f: float = 1.0 - lerpf(p0[3], p1[3], u) / TRAIL_LIFE
				var col := weapon.trail_color
				col.a *= f
				canvas.draw_line(prev, tip, col, maxf(1.0, weapon.trail_width * f), true)
				prev = tip
	if pose.is_empty() or bool(pose.behind) != back:
		return
	var tex := weapon.texture
	if tex == null:
		var tip: Vector2 = pose.grip + Vector2.from_angle(pose.angle) * pose.length
		canvas.draw_line(pose.grip, tip, Color(0.85, 0.9, 1.0), 5.0, true)
		return
	# picture: upright, grip_px held, tip_px straight above it; scale so grip->tip = full length,
	# then squash along the blade by length/full (a blade swung toward or away from the camera)
	var s: float = pose.full / maxf(weapon.length_px(), 1.0)
	var fore: float = clampf(pose.length / maxf(pose.full, 0.001), 0.05, 1.0)
	canvas.draw_set_transform(pose.grip, pose.angle + PI / 2.0, Vector2(s, s * fore))
	canvas.draw_texture(tex, -weapon.grip_px)
	canvas.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
