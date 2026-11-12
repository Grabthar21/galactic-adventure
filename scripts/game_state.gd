extends Node
## Global state for the opening prototype: hero choice, name, Valor and story flags.
## Also registers the input actions so the project works without editing the Input Map.

var hero := "arthur"          # "arthur" or "gwen"
var hero_name := "Arthur"
var valor := 0
var pup_choice := ""          # "freed" or "shooed"
var stranger_attitude := ""   # "willing" or "begrudging"
# Appearance (title screen). null = the drawing's own colours.
var skin_color = null          # Color or null
var hair_color = null          # Color or null

# Customization presets. Index 0 = as drawn.
const SKIN_TONES := [
	["As drawn", null],
	["Fair", Color(1.0, 0.86, 0.74)],
	["Tan", Color(0.85, 0.62, 0.45)],
	["Olive", Color(0.76, 0.56, 0.38)],
	["Brown", Color(0.58, 0.39, 0.26)],
	["Deep", Color(0.42, 0.27, 0.18)],
]
const HAIR_COLORS := [
	["As drawn", null],
	["Black", Color(0.12, 0.10, 0.10)],
	["Dark brown", Color(0.30, 0.19, 0.12)],
	["Auburn", Color(0.55, 0.20, 0.10)],
	["Ginger", Color(0.85, 0.42, 0.16)],
	["Blond", Color(0.93, 0.78, 0.45)],
	["Platinum", Color(0.92, 0.90, 0.84)],
]


func _ready() -> void:
	_add_action("move_left", [KEY_A, KEY_LEFT], [], [[JOY_AXIS_LEFT_X, -1.0]], [JOY_BUTTON_DPAD_LEFT])
	_add_action("move_right", [KEY_D, KEY_RIGHT], [], [[JOY_AXIS_LEFT_X, 1.0]], [JOY_BUTTON_DPAD_RIGHT])
	_add_action("move_up", [KEY_W, KEY_UP], [], [[JOY_AXIS_LEFT_Y, -1.0]], [JOY_BUTTON_DPAD_UP])
	_add_action("move_down", [KEY_S, KEY_DOWN], [], [[JOY_AXIS_LEFT_Y, 1.0]], [JOY_BUTTON_DPAD_DOWN])
	# Attack: J or left mouse; gamepad X (Xbox) / Square (PlayStation)
	_add_action("attack", [KEY_J], [MOUSE_BUTTON_LEFT], [], [JOY_BUTTON_X])
	# Dodge roll: Space; gamepad A (Xbox) / Cross (PlayStation)  [confirmed binding]
	_add_action("dodge", [KEY_SPACE], [], [], [JOY_BUTTON_A])
	# Interact / talk: E or Enter; gamepad B (Xbox) / Circle (PlayStation)
	_add_action("interact", [KEY_E, KEY_ENTER, KEY_KP_ENTER], [], [], [JOY_BUTTON_B])


func _add_action(action: String, keys: Array, mouse: Array, axes: Array, buttons: Array) -> void:
	if InputMap.has_action(action):
		return  # respect an existing binding
	InputMap.add_action(action, 0.3)
	for k in keys:
		var e := InputEventKey.new()
		e.physical_keycode = k
		InputMap.action_add_event(action, e)
	for m in mouse:
		var e := InputEventMouseButton.new()
		e.button_index = m
		InputMap.action_add_event(action, e)
	for a in axes:
		var e := InputEventJoypadMotion.new()
		e.axis = a[0]
		e.axis_value = a[1]
		InputMap.action_add_event(action, e)
	for b in buttons:
		var e := InputEventJoypadButton.new()
		e.button_index = b
		InputMap.action_add_event(action, e)


func reset() -> void:
	valor = 0
	pup_choice = ""
	stranger_attitude = ""


func is_gwen() -> bool:
	return hero == "gwen"


## Pick wording by protagonist: g("son", "daughter")
func g(male: String, female: String) -> String:
	return female if is_gwen() else male


## Replace {name} with the player's chosen name.
func fmt(text: String) -> String:
	return text.replace("{name}", hero_name)
