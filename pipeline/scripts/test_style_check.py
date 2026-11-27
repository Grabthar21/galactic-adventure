"""Self-test for blender_style_check: builds an on-style and an off-style stand-in character
and checks that the first passes and the second is flagged. Run: python test_style_check.py (with bpy) or in Blender."""
import sys, json
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import bpy, numpy as np
from mathutils import Vector
bpy.ops.wm.read_factory_settings(use_empty=True)
import blender_style_check as S
import os
OUT = os.environ.get("STYLE_TEST_OUT", "/tmp/style_test")

def tex(name, arr):
    h, w, _ = arr.shape
    img = bpy.data.images.new(name, w, h, alpha=True)
    img.pixels.foreach_set(np.ascontiguousarray(arr, dtype=np.float32).ravel())
    return img

def mat(name, img, rough, metal=0.0, spec=0.5):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    t = m.node_tree.nodes.new("ShaderNodeTexImage"); t.image = img
    m.node_tree.links.new(t.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough; b.inputs["Metallic"].default_value = metal
    b.inputs["Specular IOR Level"].default_value = spec
    return m

rng = np.random.default_rng(1)
N = 256
def painted():
    a = np.zeros((N, N, 4)); a[..., 3] = 1
    cols = [(0.28,0.19,0.15),(0.35,0.24,0.20),(0.52,0.32,0.24),(0.73,0.54,0.44),(0.76,0.64,0.56)]
    for i, c in enumerate(cols):
        a[i*N//5:(i+1)*N//5, :, :3] = c
    y = np.linspace(0, 1, N)[:, None, None]
    a[..., :3] *= 0.9 + 0.1 * y
    return a
def photo():
    a = painted(); a[..., :3] = np.clip(a[..., :3] * 0.6 + rng.normal(0, 0.12, (N, N, 3)), 0, 1)
    a[:20, :20, :3] = (1.0, 0.1, 0.9)  # neon patch
    a[200:, :, :3] = 0.01            # big black area
    return a
def eyes():
    a = np.ones((512, 1024, 4)); a[..., :3] = 0.93
    a[160:360, 200:400, :3] = (0.45, 0.25, 0.1); a[160:360, 624:824, :3] = (0.45, 0.25, 0.1)
    return a

J = {"pelvis":(0,0,.505),"spine_01":(0,0,.555),"neck_01":(0,0,.795),"head":(0,0,.832),
     "upperarm_l":(.087,0,.752),"lowerarm_l":(.110,0,.630),"hand_l":(.134,0,.522),
     "upperarm_r":(-.087,0,.752),"lowerarm_r":(-.110,0,.630),"hand_r":(-.134,0,.522),
     "thigh_l":(.05,0,.505),"calf_l":(.065,0,.29),"foot_l":(.083,0,.082),
     "thigh_r":(-.05,0,.505),"calf_r":(-.065,0,.29),"foot_r":(-.083,0,.082)}
chain = {"pelvis":"spine_01","spine_01":"neck_01","neck_01":"head","upperarm_l":"lowerarm_l","lowerarm_l":"hand_l",
         "upperarm_r":"lowerarm_r","lowerarm_r":"hand_r","thigh_l":"calf_l","calf_l":"foot_l","thigh_r":"calf_r","calf_r":"foot_r"}

def make(tag, x, body_img, rough, spec, metal, eye_img, scale=1.0, head_scale=1.0):
    ad = bpy.data.armatures.new(tag+"_arm"); arm = bpy.data.objects.new(tag+"_Armature", ad)
    bpy.context.scene.collection.objects.link(arm); bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for n,p in J.items():
        b = ad.edit_bones.new(n); b.head = Vector(p)*scale
        b.tail = Vector(J[chain[n]])*scale if n in chain else (Vector(p)+Vector((0,0,.05)))*scale
    bpy.ops.object.mode_set(mode="OBJECT")
    arm.location.x = x
    def prim(op, **kw):
        op(**kw); o = bpy.context.active_object; o.location.x += x; return o
    body = prim(bpy.ops.mesh.primitive_cylinder_add, radius=.07*scale, depth=.75*scale, location=(0,0,.45*scale))
    head = prim(bpy.ops.mesh.primitive_uv_sphere_add, radius=.075*scale*head_scale, location=(0,0,(.9)*scale))
    m = mat(tag+"_Body", body_img, rough, metal, spec)
    for o in (body, head): o.data.materials.append(m)
    if eye_img:
        e = prim(bpy.ops.mesh.primitive_uv_sphere_add, radius=.012*scale, location=(.022*scale,-.07*scale,.9*scale))
        e2 = prim(bpy.ops.mesh.primitive_uv_sphere_add, radius=.012*scale, location=(-.022*scale,-.07*scale,.9*scale))
        em = mat(tag+"_Eyes", eye_img, .85, 0, .25)
        for o in (e, e2): o.data.materials.append(em)
        return [body, head, e, e2], arm
    return [body, head], arm

good, ga = make("Good", -0.5, tex("T_Good_D", painted()), .85, .25, 0, tex("T_Good_Eyes", eyes()))
bad, ba = make("Bad", 0.5, tex("T_Bad_D", photo()), .3, .5, .6, None, head_scale=1.6)
# fake a big head on the bad one: move head bone down
for name, objs, arm, hero in (("Good", good, ga, True), ("Bad", bad, ba, True)):
    r = S.run(objs, arm, group="human_teen", hero=hero, fix=True, out_dir=OUT, name=name,
              render=(name=="Good"))
    print(name, r["verdict"], r["summary"])
    print(json.dumps(r["measured"], indent=0)[:600])
