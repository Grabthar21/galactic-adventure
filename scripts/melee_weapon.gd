class_name MeleeWeapon
extends Resource
## A melee weapon the hero can hold: its picture, how it sits in the hand, and its combo.
##
## The hero's attack animations are drawn WITHOUT a weapon. Each attack strip comes with a
## weapon track (art/<hero>_<dir>_attack_track.json, made by tools/sprixen/weapon_track.py):
## for every frame, where the hand grips, which way the weapon points and how long it looks
## (shorter when it swings toward or away from the camera). The game draws the equipped weapon
## on that track, so a new weapon is just a new picture + numbers here -- a new .tres in
## res://weapons/ -- and needs no new animation of the hero.
##
## Picture convention: the weapon drawn straight and upright, point at the top, grip at the
## bottom, on a transparent background.

@export var id := ""
@export var display_name := ""
@export var texture: Texture2D
## Where the hand holds it, in the picture's pixels (the middle of the grip).
@export var grip_px := Vector2.ZERO
## The far end (point of a sword, end of a rod), in the picture's pixels.
@export var tip_px := Vector2.ZERO
## How long the weapon is in the game, grip to tip, as a share of the reference sword the
## animations were drawn with (1.0 = the same; a dagger ~0.6, a long sword ~1.2).
@export var length_scale := 1.0
## Which set of attack animations the hero uses with it ("sword" = the 3-slash combo).
## A weapon held differently (a spear's thrusts, say) would get its own set.
@export var moveset := "sword"

@export_group("Combo")
## Damage of each hit of the combo (1st, 2nd, 3rd).
@export var damage: Array[int] = [1, 1, 2]
## How far each hit reaches from the hero, in game px (perspective-corrected).
@export var reach: Array[float] = [95.0, 95.0, 115.0]
## Half-width of each hit's arc in front of the hero, in degrees.
@export var arc_half_deg: Array[float] = [75.0, 75.0, 90.0]
## How hard each hit knocks an enemy back (px/s).
@export var knockback: Array[float] = [260.0, 260.0, 520.0]
## A playback-speed factor for the whole combo (a heavy weapon < 1, a light one > 1).
@export var speed := 1.0

@export_group("Swing trail")
@export var trail_color := Color(1, 1, 1, 0.55)
@export var trail_width := 7.0


func length_px() -> float:
	return (tip_px - grip_px).length()
