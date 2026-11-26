extends SceneTree
## Screenshots the longest dialogue line and a long choice to check nothing is cut off.
var _f := 0
var _main: Node


func _initialize() -> void:
	_main = load(ProjectSettings.get_setting("application/run/main_scene")).instantiate()
	root.add_child(_main)


func _process(_d: float) -> bool:
	_f += 1
	if _f == 5:
		_main.ui._start()
	if _f == 120:
		_main.ui.say("Father", "We are truly grateful for all that we have. We are grateful for this bounteous meal, for our comfortable shelter, and most especially for each other and the love we share. Amen.")
	if _f == 420:
		root.get_texture().get_image().save_png("/tmp/dlg_long.png")
		_main.ui._advance = true
	if _f == 430:
		_main.ui.choose("The Stranger", "Will you escort me to Initium? I cannot tell you why, only that the matter is of galactic importance and time is short.", ["I'll help you. It sounds like the right thing to do.", "Fine. But only because I don't seem to have a choice.", "Who are you, and why should I trust you?"])
	if _f == 470:
		root.get_texture().get_image().save_png("/tmp/dlg_choice.png")
		return true
	return false
