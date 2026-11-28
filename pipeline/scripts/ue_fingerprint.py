"""Unreal side of approved-asset protection (UE 5.4, run in the editor's Python).

asset_guard.py notices THAT an approved .uasset changed (file hash). This script records and
compares WHAT a character's Unreal setup is, so a change can be explained in plain words:
  - skeletal mesh: skeleton, vertex count per LOD, material slots and their materials
  - character blueprint: mesh, anim blueprint, every component (mesh asset, attach bone,
    position, visibility) and every asset the blueprint uses (montages included)
This is exactly what went wrong when BP_ArthurAdvCharacter was edited by accident: the
blueprint's montage changed and nothing told us.

    import ue_fingerprint as fp
    fp.record(r"C:/.../pipeline/entries/arthur.json")    # at approval, stores entry["approved_ue"]
    print(fp.compare(r"C:/.../pipeline/entries/arthur.json"))  # any time later

Paths come from entry["protect"]["unreal"]. Written for UE 5.4; not yet run on Henry.
"""
import json

import unreal

EAL = unreal.EditorAssetLibrary


def _s(v):
    try:
        return v.get_path_name() if hasattr(v, "get_path_name") else str(v)
    except Exception:
        return str(v)


def _deps(package):
    reg = unreal.AssetRegistryHelpers.get_asset_registry()
    opts = unreal.AssetRegistryDependencyOptions(include_soft_package_references=True,
                                                 include_hard_package_references=True,
                                                 include_searchable_names=False,
                                                 include_soft_management_references=False,
                                                 include_hard_management_references=False)
    try:
        return sorted(str(d) for d in reg.get_dependencies(package, opts) or [] if str(d).startswith("/Game/"))
    except Exception as e:
        return [f"error: {e}"]


def skeletal_mesh(path):
    sk = EAL.load_asset(path)
    out = {"type": "SkeletalMesh"}
    try:
        out["skeleton"] = _s(sk.skeleton)
    except Exception:
        pass
    sub = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
    try:
        n = sub.get_lod_count(sk)
        out["lod_verts"] = [sub.get_num_verts(sk, i) for i in range(n)]
    except Exception as e:
        out["lod_verts"] = f"error: {e}"
    try:
        out["materials"] = [{"slot": str(m.material_slot_name), "material": _s(m.material_interface)}
                            for m in sk.materials]
    except Exception as e:
        out["materials"] = f"error: {e}"
    try:
        out["physics_asset"] = _s(sk.physics_asset)
    except Exception:
        pass
    return out


def blueprint(path):
    bp = EAL.load_asset(path)
    out = {"type": "Blueprint", "uses": _deps(path.split(".")[0])}
    try:
        cls = EAL.load_blueprint_class(path)
        cdo = unreal.get_default_object(cls)
        mesh = cdo.get_editor_property("mesh")
        out["mesh"] = _s(mesh.get_skeletal_mesh_asset() if hasattr(mesh, "get_skeletal_mesh_asset")
                         else mesh.get_editor_property("skeletal_mesh"))
        out["anim_class"] = _s(mesh.get_editor_property("anim_class"))
        t = mesh.get_editor_property("relative_location")
        r = mesh.get_editor_property("relative_rotation")
        out["mesh_offset"] = [round(t.x, 2), round(t.y, 2), round(t.z, 2), round(r.yaw, 2)]
        cap = cdo.get_editor_property("capsule_component")
        out["capsule"] = [round(cap.get_editor_property("capsule_half_height"), 2),
                          round(cap.get_editor_property("capsule_radius"), 2)]
    except Exception as e:
        out["cdo"] = f"error: {e}"
    comps = []
    try:
        sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
        lib = unreal.SubobjectDataBlueprintFunctionLibrary
        for h in sds.k2_gather_subobject_data_for_blueprint(bp):
            data = sds.k2_find_subobject_data_from_handle(h)
            obj = lib.get_object(data)
            if obj is None or not isinstance(obj, unreal.ActorComponent):
                continue
            c = {"name": str(lib.get_variable_name(data)), "class": obj.get_class().get_name()}
            for prop in ("static_mesh", "skeletal_mesh_asset", "skeletal_mesh"):
                try:
                    c["asset"] = _s(obj.get_editor_property(prop))
                    break
                except Exception:
                    pass
            if isinstance(obj, unreal.SceneComponent):
                try:
                    c["attach_bone"] = str(lib.get_socket_name(data)) if hasattr(lib, "get_socket_name") \
                        else str(obj.get_attach_socket_name())
                except Exception:
                    pass
                l, r = obj.get_editor_property("relative_location"), obj.get_editor_property("relative_rotation")
                c["at"] = [round(l.x, 2), round(l.y, 2), round(l.z, 2),
                           round(r.roll, 1), round(r.pitch, 1), round(r.yaw, 1)]
                c["visible"] = bool(obj.get_editor_property("visible"))
            comps.append(c)
    except Exception as e:
        comps.append({"error": str(e)})
    out["components"] = sorted(comps, key=lambda c: c.get("name", ""))
    return out


def fingerprint_asset(path):
    a = EAL.find_asset_data(path)
    cls = str(a.asset_class_path.asset_name) if hasattr(a, "asset_class_path") else str(a.asset_class)
    if cls == "SkeletalMesh":
        return skeletal_mesh(path)
    if cls == "Blueprint":
        return blueprint(path)
    return {"type": cls, "uses": _deps(path.split(".")[0])}


def fingerprint(entry):
    return {p: fingerprint_asset(p) for p in entry.get("protect", {}).get("unreal", [])}


def _diff(a, b, path=""):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            out += _diff(a.get(k), b.get(k), f"{path}.{k}" if path else k)
    elif isinstance(a, list) and isinstance(b, list) and all(isinstance(x, dict) for x in a + b):
        ka = {x.get("name", i): x for i, x in enumerate(a)}
        kb = {x.get("name", i): x for i, x in enumerate(b)}
        for k in sorted(set(ka) | set(kb), key=str):
            out += _diff(ka.get(k), kb.get(k), f"{path}[{k}]")
    elif a != b:
        if isinstance(a, list) and isinstance(b, list):
            gone, added = sorted(set(map(str, a)) - set(map(str, b))), sorted(set(map(str, b)) - set(map(str, a)))
            out.append(f"{path}: removed {gone} added {added}" if (gone or added) else f"{path}: {a} -> {b}")
        else:
            out.append(f"{path}: {a} -> {b}")
    return out


def record(entry_path):
    with open(entry_path, encoding="utf-8") as f:
        e = json.load(f)
    e["approved_ue"] = fingerprint(e)
    with open(entry_path, "w", encoding="utf-8") as f:
        json.dump(e, f, indent=2, ensure_ascii=False)
    return e["approved_ue"]


def compare(entry_path):
    with open(entry_path, encoding="utf-8") as f:
        e = json.load(f)
    old = e.get("approved_ue")
    if not old:
        return {"status": "NOT_RECORDED", "changes": []}
    changes = _diff(old, fingerprint(e))
    return {"status": "OK" if not changes else "CHANGED", "changes": changes}
