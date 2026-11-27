import sys, math, json, runpy
sys.path.insert(0, "/home/claude/preview")
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
import unreal
g = {"LAYOUT": json.load(open("/home/claude/galactic-adventure/levels/farm_blockout.json")), "__name__": "x"}
runpy.run_path("/home/claude/galactic-adventure/levels/ue_build_farm_blockout.py", init_globals=g)
unreal.to_blender()
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.samples = 24; sc.cycles.use_denoising = True
sc.cycles.device = "CPU"
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
nt = w.node_tree; sky = nt.nodes.new("ShaderNodeTexSky")
try: sky.sky_type = "NISHITA"
except Exception: pass
sky.sun_elevation = math.radians(42); sky.sun_rotation = math.radians(215)
nt.links.new(sky.outputs[0], nt.nodes["Background"].inputs[0]); nt.nodes["Background"].inputs[1].default_value = 0.12
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sc.collection.objects.link(sun)
sun.data.energy = 2.6; sun.data.angle = math.radians(3)
sun.rotation_euler = (math.radians(48), 0, math.radians(-125))
sc.view_settings.view_transform = "AgX"; sc.view_settings.exposure = -0.6; sc.view_settings.look = "AgX - Punchy"
from mathutils import Vector
def ue(x,y,z): return Vector((x,-y,z))
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
shots = {
 "start": (ue(-23.75, 3.0, 2.4), ue(-12, -26, 3.0), 70),
 "hilltop": (ue(-6.9, -76.5, 14.2), ue(-4, -5, 0), 75),
 "overview": (ue(-75, 75, 60), ue(5, -20, 0), 60),
}
for name,(p,t,fov) in shots.items():
    cam.location = p
    cam.rotation_euler = (t-p).to_track_quat("-Z","Y").to_euler()
    cam.data.angle = math.radians(fov); cam.data.clip_end = 1000
    sc.render.filepath = f"/home/claude/renders/farm_{name}.png"
    bpy.ops.render.render(write_still=True)
    print("rendered", name)
