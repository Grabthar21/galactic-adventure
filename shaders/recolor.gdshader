// Player customization: recolours skin and hair on the character sprites.
// The build (tools/sprixen/masks.py) writes a mask strip beside every animation strip:
//   R = skin weight, G = hair weight (same layout as the colour strip, so the same UV works
//   for both). Each masked pixel is re-shaded: its brightness relative to the reference colour
//   is applied to the chosen colour, so shading, line art and highlights are kept.
shader_type canvas_item;

uniform sampler2D mask_tex : filter_linear;
uniform bool has_mask = false;
uniform bool recolor_skin = false;
uniform bool recolor_hair = false;
uniform vec3 skin_ref = vec3(0.945, 0.694, 0.502);
uniform vec3 hair_ref = vec3(0.478, 0.278, 0.173);
uniform vec3 skin_color = vec3(0.945, 0.694, 0.502);
uniform vec3 hair_color = vec3(0.478, 0.278, 0.173);

varying vec4 tint;   // vertex colour (modulate: hurt flash, roll fade)

const vec3 LUMA = vec3(0.299, 0.587, 0.114);

vec3 reshade(vec3 c, vec3 ref, vec3 target) {
	float r = dot(c, LUMA) / max(dot(ref, LUMA), 0.001);
	vec3 o = target * r;
	// highlights brighter than the new colour can hold go toward white instead of clipping
	float over = max(max(o.r, max(o.g, o.b)) - 1.0, 0.0);
	o = clamp(o, 0.0, 1.0) + over * 0.5;
	// keep the drawing's subtle warm/cool shading variation
	o += (c - ref * r) * 0.5;
	return clamp(o, 0.0, 1.0);
}

void vertex() {
	tint = COLOR;
}

void fragment() {
	vec4 c = texture(TEXTURE, UV);
	if (has_mask) {
		vec4 m = texture(mask_tex, UV);
		if (recolor_skin) {
			c.rgb = mix(c.rgb, reshade(c.rgb, skin_ref, skin_color), m.r);
		}
		if (recolor_hair) {
			c.rgb = mix(c.rgb, reshade(c.rgb, hair_ref, hair_color), m.g);
		}
	}
	COLOR = c * tint;
}
