"""Minimal stand-in for Unreal's Python API, backed by Blender (bpy).
Records spawned actors in Unreal space (cm, left-handed) and builds matching
Blender meshes with Y flipped, so the picture matches the Unreal layout."""
import math
import bpy
import bmesh
from mathutils import Vector as BV

ACTORS = []


def log(msg):
    print(msg)


class Vector:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)

    def __add__(self, o): return Vector(self.x + o.x, self.y + o.y, self.z + o.z)
    def __sub__(self, o): return Vector(self.x - o.x, self.y - o.y, self.z - o.z)
    def __mul__(self, s): return Vector(self.x * s, self.y * s, self.z * s)
    def length(self): return math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)
    def t(self): return (self.x, self.y, self.z)


class Rotator:
    def __init__(self, roll=0.0, pitch=0.0, yaw=0.0):
        self.roll, self.pitch, self.yaw = roll, pitch, yaw

    def axes(self):
        # UE FRotationMatrix rows: X, Y, Z axes
        P, Y, R = (math.radians(a) for a in (self.pitch, self.yaw, self.roll))
        SP, CP, SY, CY, SR, CR = math.sin(P), math.cos(P), math.sin(Y), math.cos(Y), math.sin(R), math.cos(R)
        X = (CP * CY, CP * SY, SP)
        Yx = (SR * SP * CY - CR * SY, SR * SP * SY + CR * CY, -SR * CP)
        Z = (-(CR * SP * CY + SR * SY), CY * SR - CR * SP * SY, CR * CP)
        return X, Yx, Z


class LinearColor:
    def __init__(self, r, g, b, a=1): self.c = (r, g, b, a)


class CollisionEnabled: NO_COLLISION = 0
class ComponentMobility: MOVABLE = 2


class _Comp:
    def __init__(self, actor): self.actor = actor; self.props = {}
    def set_material(self, i, m): self.actor.mat = m
    def set_collision_enabled(self, c): self.actor.collide = False
    def set_editor_property(self, k, val): self.props[k] = val


class Actor:
    def __init__(self, kind, loc, rot):
        self.kind, self.loc, self.rot = kind, loc, rot or Rotator()
        self.scale = Vector(1, 1, 1)
        self.label, self.folder, self.tags = "", "", []
        self.mat, self.collide, self.hidden = None, True, False
        self.static_mesh_component = _Comp(self)
        self.light_component = _Comp(self)
        ACTORS.append(self)

    def set_actor_scale3d(self, s): self.scale = s
    def set_actor_label(self, l): self.label = l
    def set_folder_path(self, f): self.folder = f
    def set_actor_hidden_in_game(self, h): self.hidden = h
    def set_editor_property(self, k, v): pass
    def get_world_settings(self): return self


class _Asset:
    def __init__(self, path): self.path = path; self.color = None


class EditorActorSubsystem:
    def spawn_actor_from_object(self, mesh, loc, rot): return Actor(mesh.path.split("/")[-1], loc, rot)
    def spawn_actor_from_class(self, cls, loc, rot=None): return Actor(cls.__name__, loc, rot)
    def get_all_level_actors(self): return list(ACTORS)
    def destroy_actor(self, a): ACTORS.remove(a)


class LevelEditorSubsystem:
    def load_level(self, p): pass
    def new_level(self, p): pass
    def save_current_level(self): pass


_subs = {}


def get_editor_subsystem(cls):
    return _subs.setdefault(cls, cls())


class EditorAssetLibrary:
    _assets = {}

    @staticmethod
    def load_asset(p): return EditorAssetLibrary._assets.setdefault(p, _Asset(p))
    @staticmethod
    def does_asset_exist(p): return p in EditorAssetLibrary._assets
    @staticmethod
    def save_loaded_asset(a): pass
    @staticmethod
    def load_blueprint_class(p): return type("BP", (), {})


class MaterialEditingLibrary:
    @staticmethod
    def set_material_instance_parent(mi, p): pass
    @staticmethod
    def get_vector_parameter_names(m): return ["Color"]
    @staticmethod
    def set_material_instance_vector_parameter_value(mi, n, c): mi.color = c.c


class MathLibrary:
    @staticmethod
    def make_rot_from_x(d):
        yaw = math.degrees(math.atan2(d.y, d.x))
        pitch = math.degrees(math.atan2(d.z, math.hypot(d.x, d.y)))
        return Rotator(0, pitch, yaw)

    @staticmethod
    def get_up_vector(r): return Vector(*r.axes()[2])


class _Tools:
    def create_asset(self, name, path, cls, fac):
        return EditorAssetLibrary.load_asset(f"{path}/{name}")


class AssetToolsHelpers:
    @staticmethod
    def get_asset_tools(): return _Tools()


class MaterialInstanceConstant: pass
class MaterialInstanceConstantFactoryNew: pass
class DirectionalLight: pass
class SkyLight: pass
class SkyAtmosphere: pass
class ExponentialHeightFog: pass
class PlayerStart: pass


class TopLevelAssetPath:
    def __init__(self, *a): pass


class _AD:
    asset_name = "BP_ThirdPersonGameMode"
    package_name = "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode"


class _Reg:
    def get_assets_by_class(self, *a): return [_AD()]


class AssetRegistryHelpers:
    @staticmethod
    def get_asset_registry(): return _Reg()


class EditorLevelLibrary:
    @staticmethod
    def get_editor_world(): return Actor("World", Vector(), None)


# ------------------------------------------------------------ Blender side
def _unit_mesh(kind):
    bm = bmesh.new()
    if kind == "Cube":
        bmesh.ops.create_cube(bm, size=1.0)
    elif kind == "Cylinder":
        bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.5, radius2=0.5, depth=1.0)
    elif kind == "Sphere":
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=0.5)
    return bm


def to_blender(skip_hidden=True):
    mats = {}
    groups = {}
    for a in ACTORS:
        if a.kind not in ("Cube", "Cylinder", "Sphere"):
            continue
        if skip_hidden and a.hidden:
            continue
        groups.setdefault(a.mat.path if a.mat else "none", []).append(a)
    for key, actors in groups.items():
        bm_all = bmesh.new()
        for a in actors:
            bm = _unit_mesh(a.kind)
            X, Y, Z = a.rot.axes()
            s = a.scale
            for vtx in bm.verts:
                lx, ly, lz = vtx.co.x * 100 * s.x, vtx.co.y * 100 * s.y, vtx.co.z * 100 * s.z
                wx = a.loc.x + lx * X[0] + ly * Y[0] + lz * Z[0]
                wy = a.loc.y + lx * X[1] + ly * Y[1] + lz * Z[1]
                wz = a.loc.z + lx * X[2] + ly * Y[2] + lz * Z[2]
                vtx.co = BV((wx / 100, -wy / 100, wz / 100))   # cm -> m, flip Y
            me = bpy.data.meshes.new("tmp")
            bm.normal_update()
            bm.to_mesh(me)
            bm.free()
            bm_all.from_mesh(me)
            bpy.data.meshes.remove(me)
        # Y flip mirrors the winding; fix it
        bmesh.ops.reverse_faces(bm_all, faces=bm_all.faces)
        me = bpy.data.meshes.new(key.split("/")[-1])
        bm_all.to_mesh(me)
        bm_all.free()
        for p in me.polygons:
            p.use_smooth = False
        ob = bpy.data.objects.new(key.split("/")[-1], me)
        bpy.context.scene.collection.objects.link(ob)
        if actors[0].mat is not None:
            m = bpy.data.materials.new(key.split("/")[-1])
            m.use_nodes = True
            bsdf = m.node_tree.nodes["Principled BSDF"]
            r, g, b, _ = actors[0].mat.color
            bsdf.inputs["Base Color"].default_value = (r, g, b, 1)
            bsdf.inputs["Roughness"].default_value = 0.85
            me.materials.append(m)
