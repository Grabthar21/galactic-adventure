"""Lint a generated graph: unreachable action nodes, dangling inputs, unused outputs."""
import importlib, sys

OPTIONAL_IN = {"self", "Condition", "Tolerance", "bTeleportPhysics", "PlayerIndex", "Tag", "B"}


def lint(mod_name, graph_attr="g"):
    m = importlib.import_module(mod_name)
    g = getattr(m, graph_attr)
    problems = []
    for n in g.nodes:
        if "Comment" in n.name:
            continue
        ex = n.pins.get("execute")
        if ex is not None and not ex.links:
            problems.append(f"UNREACHED  {n.name}")
        for p in n.pins.values():
            if p.out or p.cat == "exec" or p.name in OPTIONAL_IN:
                continue
            if not p.links and p.default is None and p.default_object is None and not ("VariableSet" in n.name and p.cat == "object"):
                problems.append(f"NO INPUT   {n.name}.{p.name}")
        outs = [p for p in n.pins.values() if p.out and p.cat != "exec"]
        if outs and ex is None and not any(p.links for p in outs) and "Event" not in n.name:
            problems.append(f"UNUSED     {n.name}")
    return problems


if __name__ == "__main__":
    for mod in sys.argv[1:]:
        ps = lint(mod)
        print(mod, "OK" if not ps else "\n  " + "\n  ".join(ps))
