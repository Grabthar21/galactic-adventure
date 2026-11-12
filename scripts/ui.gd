extends CanvasLayer
## HUD, dialogue box with choices, toasts, objective, fades, title screen and end card.

signal title_started

var hearts: HBoxContainer
var objective_label: Label
var prompt_label: Label
var help_label: Label
var dlg_panel: PanelContainer
var dlg_name: Label
var dlg_text: Label
var dlg_hint: Label
var choice_box: VBoxContainer
var toast_box: VBoxContainer
var fade: ColorRect
var card: Label
var title: Control
var end_panel: Control

var busy := false          # dialogue or choice on screen
var closed_frame := -100   # frame the last dialogue closed (stops one key press doing two things)
var _typing := false
var _advance := false
var _choice_index := -1
var _choices: Array = []
var _choice_sel := 0
var _hero_sel := 0
var name_edit: LineEdit
var hero_preview: Array = []
var hero_test_btn: Button
var _skin_sel := 0
var _hair_sel := 0
var _swatches := {"skin": [], "hair": []}
var _preview_mat: ShaderMaterial
var _styles: Array = []        # [[key, label], ...] from art/arthur_styles.json ("" = default)
var _style_sel := 0
var _style_btns: Array = []


func _ready() -> void:
	layer = 10
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)

	hearts = HBoxContainer.new()
	hearts.position = Vector2(20, 16)
	root.add_child(hearts)

	objective_label = _label(root, 20, Color(1, 0.95, 0.75))
	objective_label.position = Vector2(20, 52)

	help_label = _label(root, 14, Color(1, 1, 1, 0.75))
	help_label.position = Vector2(20, 690)
	help_label.text = "Move: WASD / Arrows   Attack: J / Left-click / (X)   Dodge: Space / (A)   Interact: E / Enter / (B)"

	prompt_label = _label(root, 20, Color.WHITE)
	prompt_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	prompt_label.size = Vector2(1280, 30)
	prompt_label.position = Vector2(0, 560)

	toast_box = VBoxContainer.new()
	toast_box.position = Vector2(440, 90)
	toast_box.size = Vector2(400, 10)
	toast_box.alignment = BoxContainer.ALIGNMENT_BEGIN
	root.add_child(toast_box)

	# dialogue
	dlg_panel = PanelContainer.new()
	dlg_panel.position = Vector2(140, 500)
	dlg_panel.size = Vector2(1000, 190)
	dlg_panel.add_theme_stylebox_override("panel", _box(Color(0.1, 0.08, 0.14, 0.92), Color(0.85, 0.7, 0.35)))
	root.add_child(dlg_panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 6)
	dlg_panel.add_child(v)
	dlg_name = _label(v, 22, Color(1, 0.8, 0.35))
	dlg_text = _label(v, 21, Color.WHITE)
	dlg_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	dlg_text.custom_minimum_size = Vector2(960, 70)
	choice_box = VBoxContainer.new()
	v.add_child(choice_box)
	dlg_hint = _label(v, 13, Color(1, 1, 1, 0.5))
	dlg_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	dlg_panel.visible = false

	card = _label(root, 30, Color(1, 0.95, 0.85))
	card.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	card.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	card.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	card.size = Vector2(1000, 400)
	card.position = Vector2(140, 160)
	card.z_index = 5

	fade = ColorRect.new()
	fade.color = Color(0, 0, 0, 1)
	fade.set_anchors_preset(Control.PRESET_FULL_RECT)
	fade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(fade)
	root.move_child(card, -1)


func _label(parent: Node, size: int, col: Color) -> Label:
	var l := Label.new()
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", col)
	l.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.8))
	l.add_theme_constant_override("outline_size", 5)
	parent.add_child(l)
	return l


func _box(bg: Color, border: Color) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.border_color = border
	s.set_border_width_all(3)
	s.set_corner_radius_all(10)
	s.content_margin_left = 22
	s.content_margin_right = 22
	s.content_margin_top = 14
	s.content_margin_bottom = 12
	return s


# ---------- HUD ----------

func set_hp(hp: int, max_hp: int) -> void:
	for c in hearts.get_children():
		c.queue_free()
	for i in max_hp:
		var c := Control.new()
		c.custom_minimum_size = Vector2(32, 30)
		var full := i < hp
		c.draw.connect(func(): _draw_heart(c, full))
		hearts.add_child(c)


func _draw_heart(c: Control, full: bool) -> void:
	# Drawn shape (web builds have no system font fallback for a heart glyph)
	var col := Color(0.9, 0.15, 0.2) if full else Color(0.25, 0.2, 0.22)
	var pts := PackedVector2Array()
	for k in 40:
		var t := TAU * k / 40.0
		var x := 16.0 * pow(sin(t), 3)
		var y := -(13.0 * cos(t) - 5.0 * cos(2 * t) - 2.0 * cos(3 * t) - cos(4 * t))
		pts.append(Vector2(15, 14) + Vector2(x, y) * 0.85)
	c.draw_colored_polygon(pts, Color.BLACK)
	var inner := PackedVector2Array()
	for q in pts:
		inner.append(Vector2(15, 14) + (q - Vector2(15, 14)) * 0.82)
	c.draw_colored_polygon(inner, col)


func show_hearts(v: bool) -> void:
	hearts.visible = v


func set_objective(text: String) -> void:
	objective_label.text = ("Objective: " + GameState.fmt(text)) if text != "" else ""


func set_prompt(text: String) -> void:
	prompt_label.text = text


func toast(text: String, col := Color(1, 0.9, 0.5)) -> void:
	var l := _label(toast_box, 22, col)
	l.text = text
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.custom_minimum_size = Vector2(400, 0)
	var tw := create_tween()
	tw.tween_interval(2.6)
	tw.tween_property(l, "modulate:a", 0.0, 0.6)
	tw.tween_callback(l.queue_free)


# ---------- fades and cards ----------

func fade_out(t := 0.5) -> void:
	var tw := create_tween()
	tw.tween_property(fade, "color:a", 1.0, t)
	await tw.finished


func fade_in(t := 0.5) -> void:
	var tw := create_tween()
	tw.tween_property(fade, "color:a", 0.0, t)
	await tw.finished


func flash(col := Color(1, 1, 1)) -> void:
	fade.color = Color(col.r, col.g, col.b, 0.9)
	var tw := create_tween()
	tw.tween_property(fade, "color", Color(0, 0, 0, 0), 0.6)
	await tw.finished


func show_card(text: String, seconds: float) -> void:
	card.text = text
	card.modulate.a = 0.0
	var tw := create_tween()
	tw.tween_property(card, "modulate:a", 1.0, 0.6)
	tw.tween_interval(seconds)
	tw.tween_property(card, "modulate:a", 0.0, 0.6)
	await tw.finished


# ---------- dialogue ----------

func say(speaker: String, text: String) -> void:
	busy = true
	dlg_panel.visible = true
	_clear_choices()
	dlg_name.text = GameState.fmt(speaker)
	dlg_text.text = GameState.fmt(text)
	dlg_hint.text = "Next: E / Space / Enter"
	dlg_text.visible_ratio = 0.0
	_typing = true
	_advance = false
	var total := dlg_text.text.length()
	var shown := 0.0
	while _typing:
		await get_tree().process_frame
		shown += get_process_delta_time() * 55.0
		dlg_text.visible_ratio = clampf(shown / maxf(total, 1), 0.0, 1.0)
		if dlg_text.visible_ratio >= 1.0:
			_typing = false
	_advance = false
	while not _advance:
		await get_tree().process_frame
	dlg_panel.visible = false
	busy = false
	closed_frame = Engine.get_process_frames()


func choose(speaker: String, text: String, options: Array) -> int:
	busy = true
	dlg_panel.visible = true
	dlg_name.text = GameState.fmt(speaker)
	dlg_text.text = GameState.fmt(text)
	dlg_text.visible_ratio = 1.0
	dlg_hint.text = "Up/Down to pick, E / Enter to choose, or click"
	_clear_choices()
	_choice_index = -1
	_choice_sel = 0
	for i in options.size():
		var b := Button.new()
		b.text = GameState.fmt(options[i])
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.focus_mode = Control.FOCUS_NONE
		b.add_theme_font_size_override("font_size", 19)
		b.pressed.connect(func(): _choice_index = i)
		b.mouse_entered.connect(func(): _choice_sel = i; _refresh_choices())
		choice_box.add_child(b)
		_choices.append(b)
	_refresh_choices()
	# wait a frame so the key that opened this doesn't pick instantly
	await get_tree().process_frame
	while _choice_index < 0:
		await get_tree().process_frame
	var picked := _choice_index
	_clear_choices()
	dlg_panel.visible = false
	busy = false
	closed_frame = Engine.get_process_frames()
	return picked


func _clear_choices() -> void:
	for c in choice_box.get_children():
		c.queue_free()
	_choices.clear()


func _refresh_choices() -> void:
	for i in _choices.size():
		var b: Button = _choices[i]
		b.text = ("> " if i == _choice_sel else "   ") + b.text.trim_prefix("> ").trim_prefix("   ")
		b.modulate = Color(1, 0.9, 0.5) if i == _choice_sel else Color(0.85, 0.85, 0.85)


func _input(event: InputEvent) -> void:
	if title and title.visible:
		_title_input(event)
		return
	if not dlg_panel.visible:
		return
	if _choices.size() > 0:
		if event.is_action_pressed("move_up"):
			_choice_sel = (_choice_sel - 1 + _choices.size()) % _choices.size()
			_refresh_choices()
		elif event.is_action_pressed("move_down"):
			_choice_sel = (_choice_sel + 1) % _choices.size()
			_refresh_choices()
		elif event.is_action_pressed("interact") or event.is_action_pressed("dodge"):
			_choice_index = _choice_sel
		return
	if event.is_action_pressed("interact") or event.is_action_pressed("dodge") or event.is_action_pressed("attack"):
		if _typing:
			_typing = false
			dlg_text.visible_ratio = 1.0
		else:
			_advance = true
		get_viewport().set_input_as_handled()


# ---------- title ----------

func show_title() -> void:
	title = Control.new()
	title.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(title)
	var bg := ColorRect.new()
	bg.color = Color(0.07, 0.07, 0.16)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	title.add_child(bg)
	var rng := RandomNumberGenerator.new()
	rng.seed = 3
	for i in 120:
		var s := ColorRect.new()
		s.color = Color(1, 1, 1, rng.randf_range(0.2, 0.9))
		s.size = Vector2.ONE * rng.randf_range(1, 3)
		s.position = Vector2(rng.randf_range(0, 1280), rng.randf_range(0, 720))
		title.add_child(s)
	var t := _label(title, 56, Color(1, 0.85, 0.4))
	t.text = "SPACE PIECE"
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	t.size = Vector2(1280, 70)
	t.position = Vector2(0, 50)
	var st := _label(title, 20, Color(0.85, 0.85, 1))
	st.text = "Opening prototype: the first five minutes"
	st.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	st.size = Vector2(1280, 30)
	st.position = Vector2(0, 125)
	hero_preview.clear()
	for i in 2:
		var hero: String = ["arthur", "gwen"][i]
		var tr := TextureRect.new()
		var at := AtlasTexture.new()
		var strip := "res://art/%s_down_idle.png" % hero
		if ResourceLoader.exists(strip) and ResourceLoader.exists(strip.replace(".png", "_mask.png")):
			at.atlas = load(strip)
			tr.material = _make_preview_material(hero, strip.replace(".png", "_mask.png"))
		else:
			at.atlas = load("res://art/%s_frames.png" % hero)
		at.region = Rect2(0, 0, 98, 148)
		tr.texture = at
		tr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		tr.size = Vector2(150, 226)
		tr.position = Vector2(400 + i * 330, 190)
		title.add_child(tr)
		var b := Button.new()
		b.text = hero.capitalize()
		b.focus_mode = Control.FOCUS_NONE
		b.add_theme_font_size_override("font_size", 22)
		b.size = Vector2(150, 40)
		b.position = Vector2(400 + i * 330, 425)
		b.pressed.connect(func(): _pick_hero(i))
		title.add_child(b)
		hero_preview.append([tr, b])
	var nl := _label(title, 18, Color.WHITE)
	nl.text = "Name:"
	nl.position = Vector2(470, 497)
	name_edit = LineEdit.new()
	name_edit.max_length = 14
	name_edit.size = Vector2(260, 40)
	name_edit.position = Vector2(540, 490)
	name_edit.add_theme_font_size_override("font_size", 20)
	name_edit.text_submitted.connect(func(_t): _start())
	title.add_child(name_edit)
	var test_btn := Button.new()
	test_btn.text = "Test: Arthur cut-out rig (side walk)"
	test_btn.focus_mode = Control.FOCUS_NONE
	test_btn.add_theme_font_size_override("font_size", 16)
	test_btn.size = Vector2(330, 34)
	test_btn.position = Vector2(880, 495)
	test_btn.pressed.connect(func(): _pick_hero(2))
	title.add_child(test_btn)
	hero_test_btn = test_btn
	_build_appearance_picker()
	var go := Button.new()
	go.text = "Begin"
	go.focus_mode = Control.FOCUS_NONE
	go.add_theme_font_size_override("font_size", 26)
	go.size = Vector2(200, 50)
	go.position = Vector2(540, 560)
	go.pressed.connect(_start)
	title.add_child(go)
	var hint := _label(title, 15, Color(1, 1, 1, 0.6))
	hint.text = "Left/Right picks a hero (T = new-parts test). S / H / Y (or LB / RB / Y) change skin tone / hair colour / hairstyle.\nType a name if you like, then press Enter or click Begin. Keyboard or gamepad recommended."
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hint.size = Vector2(1280, 50)
	hint.position = Vector2(0, 630)
	_pick_hero(0)
	title.move_to_front()


# ---------- appearance (skin tone / hair colour) ----------

func _make_preview_material(hero: String, mask_path: String) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = load("res://shaders/recolor.gdshader")
	m.set_shader_parameter("mask_tex", load(mask_path))
	m.set_shader_parameter("has_mask", true)
	var path := "res://art/%s_anims.json" % hero
	if FileAccess.file_exists(path):
		var d = JSON.parse_string(FileAccess.get_file_as_string(path))
		if d is Dictionary and d.has("skin_ref") and d.has("hair_ref"):
			m.set_shader_parameter("skin_ref", Vector3(d.skin_ref[0], d.skin_ref[1], d.skin_ref[2]))
			m.set_shader_parameter("hair_ref", Vector3(d.hair_ref[0], d.hair_ref[1], d.hair_ref[2]))
	if hero == "arthur":
		_preview_mat = m
	return m


func _build_appearance_picker() -> void:
	var rows := [["Skin", "skin", GameState.SKIN_TONES, Color(0.945, 0.702, 0.51)],
			["Hair", "hair", GameState.HAIR_COLORS, Color(0.482, 0.278, 0.173)]]
	for r in rows.size():
		var lab := _label(title, 18, Color.WHITE)
		lab.text = rows[r][0] + ":"
		lab.position = Vector2(40, 200 + r * 120)
		var presets: Array = rows[r][2]
		for k in presets.size():
			var col: Color = presets[k][1] if presets[k][1] is Color else rows[r][3]
			var b := Button.new()
			b.focus_mode = Control.FOCUS_NONE
			b.tooltip_text = presets[k][0]
			b.size = Vector2(38, 38)
			b.position = Vector2(40 + (k % 4) * 46, 228 + r * 120 + (k / 4) * 46)
			var sb := _swatch_box(col, Color(0.15, 0.15, 0.2))
			b.add_theme_stylebox_override("normal", sb)
			b.add_theme_stylebox_override("hover", _swatch_box(col, Color(1, 1, 1, 0.7)))
			b.add_theme_stylebox_override("pressed", sb)
			var which: String = rows[r][1]
			b.pressed.connect(func(): _pick_look(which, k))
			title.add_child(b)
			_swatches[which].append(b)
	# hairstyles built by tools/sprixen (art/<hero>__<style>_*), listed in art/<hero>_styles.json
	_styles = [["", "Default"]]
	var sp := "res://art/arthur_styles.json"
	if FileAccess.file_exists(sp):
		var d = JSON.parse_string(FileAccess.get_file_as_string(sp))
		if d is Dictionary:
			_styles = []
			for key in d:
				_styles.append(["" if key == "default" else key, d[key]])
	var sl := _label(title, 18, Color.WHITE)
	sl.text = "Hairstyle:"
	sl.position = Vector2(40, 440)
	for k in _styles.size():
		var b := Button.new()
		b.text = _styles[k][1]
		b.focus_mode = Control.FOCUS_NONE
		b.add_theme_font_size_override("font_size", 15)
		b.size = Vector2(108, 32)
		b.position = Vector2(40 + (k % 2) * 116, 468 + (k / 2) * 38)
		b.pressed.connect(func(): _pick_style(k))
		title.add_child(b)
		_style_btns.append(b)
	var note := _label(title, 13, Color(1, 1, 1, 0.55))
	note.text = "Gwen's options apply once\nher new animations are built."
	note.position = Vector2(40, 470 + ((_styles.size() + 1) / 2) * 38)
	_pick_style(0)
	_pick_look("skin", 0)
	_pick_look("hair", 0)


func _pick_style(k: int) -> void:
	_style_sel = k
	GameState.hairstyle = _styles[k][0]
	for j in _style_btns.size():
		_style_btns[j].modulate = Color(1, 0.85, 0.4) if j == k else Color(0.7, 0.7, 0.7)
	# swap Arthur's preview to that style's front idle (+ its mask)
	var look := "arthur" if GameState.hairstyle == "" else "arthur__" + GameState.hairstyle
	var strip := "res://art/%s_down_idle.png" % look
	if hero_preview.size() > 0 and _preview_mat and ResourceLoader.exists(strip):
		var at: AtlasTexture = hero_preview[0][0].texture
		at.atlas = load(strip)
		_preview_mat.set_shader_parameter("mask_tex", load(strip.replace(".png", "_mask.png")))


func _swatch_box(bg: Color, border: Color) -> StyleBoxFlat:
	var s := _box(bg, border)
	s.set_content_margin_all(2)
	s.set_corner_radius_all(8)
	return s


func _pick_look(which: String, k: int) -> void:
	if which == "skin":
		_skin_sel = k
		GameState.skin_color = GameState.SKIN_TONES[k][1]
	else:
		_hair_sel = k
		GameState.hair_color = GameState.HAIR_COLORS[k][1]
	for j in _swatches[which].size():
		var sel: bool = j == k
		_swatches[which][j].scale = Vector2.ONE * (1.12 if sel else 1.0)
		_swatches[which][j].modulate = Color.WHITE if sel else Color(0.8, 0.8, 0.8)
	if _preview_mat:
		var s = GameState.skin_color
		var h = GameState.hair_color
		_preview_mat.set_shader_parameter("recolor_skin", s is Color)
		_preview_mat.set_shader_parameter("recolor_hair", h is Color)
		if s is Color:
			_preview_mat.set_shader_parameter("skin_color", Vector3(s.r, s.g, s.b))
		if h is Color:
			_preview_mat.set_shader_parameter("hair_color", Vector3(h.r, h.g, h.b))


func _pick_hero(i: int) -> void:
	var old_default := "Gwen" if _hero_sel == 1 else "Arthur"
	_hero_sel = i
	if name_edit.text == "" or name_edit.text == old_default:
		name_edit.text = "Gwen" if i == 1 else "Arthur"
	for j in hero_preview.size():
		var on := j == i or (i == 2 and j == 0)
		hero_preview[j][0].modulate = Color.WHITE if on else Color(0.45, 0.45, 0.5)
		hero_preview[j][1].modulate = Color(1, 0.85, 0.4) if j == i else Color(0.7, 0.7, 0.7)
	if hero_test_btn:
		hero_test_btn.modulate = Color(1, 0.85, 0.4) if i == 2 else Color(0.7, 0.7, 0.7)


func _title_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.physical_keycode == KEY_LEFT:
			_pick_hero(0)
		elif event.physical_keycode == KEY_RIGHT:
			_pick_hero(1)
		elif event.physical_keycode == KEY_T and not name_edit.has_focus():
			_pick_hero(2)
		elif event.physical_keycode in [KEY_ENTER, KEY_KP_ENTER] and not name_edit.has_focus():
			_start()
	elif event is InputEventJoypadButton and event.pressed:
		if event.button_index == JOY_BUTTON_DPAD_LEFT:
			_pick_hero(0)
		elif event.button_index == JOY_BUTTON_DPAD_RIGHT:
			_pick_hero(1)
		elif event.button_index in [JOY_BUTTON_A, JOY_BUTTON_START]:
			_start()


func _start() -> void:
	if not title.visible:
		return
	GameState.hero = ["arthur", "gwen", "arthur_v2"][_hero_sel]
	var n := name_edit.text.strip_edges()
	GameState.hero_name = n if n != "" else ("Gwen" if _hero_sel == 1 else "Arthur")
	title.visible = false
	title.queue_free()
	title_started.emit()


# ---------- end card ----------

func show_end(lines: Array) -> void:
	end_panel = Control.new()
	end_panel.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(end_panel)
	var bg := ColorRect.new()
	bg.color = Color(0.05, 0.05, 0.1, 0.96)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	end_panel.add_child(bg)
	var t := _label(end_panel, 44, Color(1, 0.85, 0.4))
	t.text = "To be continued..."
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	t.size = Vector2(1280, 60)
	t.position = Vector2(0, 110)
	var body := _label(end_panel, 22, Color.WHITE)
	body.text = "\n".join(lines)
	body.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	body.size = Vector2(1280, 300)
	body.position = Vector2(0, 210)
	var b := Button.new()
	b.text = "Play again"
	b.add_theme_font_size_override("font_size", 24)
	b.size = Vector2(220, 50)
	b.position = Vector2(530, 560)
	b.pressed.connect(func(): GameState.reset(); get_tree().reload_current_scene())
	end_panel.add_child(b)
	b.grab_focus()
