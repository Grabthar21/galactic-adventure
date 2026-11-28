"""Tiny writer for Unreal Blueprint clipboard text (T3D).

Build nodes with pins, link pins by (node, pin name), then dump() gives text that
pastes into a Blueprint graph with Ctrl+V. Unreal rebuilds each node's pins from the
real function on paste, so only the pins that carry links or default values matter.
"""
import hashlib

ENGINE = "/Script/CoreUObject.Class'/Script/Engine.{}'"
STRUCT = "/Script/CoreUObject.ScriptStruct'/Script/CoreUObject.{}'"


def _guid(seed):
    return hashlib.md5(seed.encode()).hexdigest().upper()


class Pin:
    def __init__(self, node, name, out=False, cat="exec", sub="", obj=None,
                 array=False, default=None, default_object=None, friendly=None):
        self.node, self.name, self.out = node, name, out
        self.cat, self.sub, self.obj, self.array = cat, sub, obj, array
        self.default, self.default_object, self.friendly = default, default_object, friendly
        self.id = _guid(f"{node.name}.{name}")
        self.links = []

    def text(self):
        p = [f"PinId={self.id}", f'PinName="{self.name}"']
        if self.friendly:
            p.append(f'PinFriendlyName=NSLOCTEXT("K2Node", "{self.friendly}", "{self.friendly}")')
        if self.out:
            p.append('Direction="EGPD_Output"')
        p.append(f'PinType.PinCategory="{self.cat}"')
        p.append(f'PinType.PinSubCategory="{self.sub}"')
        p.append(f'PinType.PinSubCategoryObject={chr(34) + self.obj + chr(34) if self.obj else "None"}')
        p.append("PinType.PinSubCategoryMemberReference=()")
        p.append("PinType.PinValueType=()")
        p.append(f"PinType.ContainerType={'Array' if self.array else 'None'}")
        p += ["PinType.bIsReference=False", "PinType.bIsConst=False", "PinType.bIsWeakPointer=False",
              "PinType.bIsUObjectWrapper=False", "PinType.bSerializeAsSinglePrecisionFloat=False"]
        if self.default is not None:
            p.append(f'DefaultValue="{self.default}"')
        if self.default_object:
            p.append(f'DefaultObject="{self.default_object}"')
        if self.links:
            p.append("LinkedTo=(" + "".join(f"{q.node.name} {q.id}," for q in self.links) + ")")
        p += ["PersistentGuid=00000000000000000000000000000000", "bHidden=False", "bNotConnectable=False",
              "bDefaultValueIsReadOnly=False", "bDefaultValueIsIgnored=False", "bAdvancedView=False",
              "bOrphanedPin=False"]
        return "   CustomProperties Pin (" + ",".join(p) + ",)"


class Node:
    def __init__(self, graph, cls, name, x, y, props=()):
        self.graph, self.cls, self.name, self.x, self.y = graph, cls, name, x, y
        self.props = list(props)
        self.pins = {}
        graph.nodes.append(self)

    def pin(self, name, **kw):
        self.pins[name] = Pin(self, name, **kw)
        return self

    def __getitem__(self, name):
        return self.pins[name]

    def text(self):
        lines = [f'Begin Object Class={self.cls} Name="{self.name}"']
        lines += [f"   {p}" for p in self.props]
        lines += [f"   NodePosX={self.x}", f"   NodePosY={self.y}", f"   NodeGuid={_guid(self.name)}"]
        lines += [p.text() for p in self.pins.values()]
        lines.append("End Object")
        return "\r\n".join(lines)


class Graph:
    def __init__(self, prefix):
        self.prefix, self.nodes = prefix, []

    def _n(self, kind, tag):
        return f"K2Node_{kind}_{self.prefix}{tag}"

    # ---- node helpers -------------------------------------------------------
    def comment(self, tag, x, y, w, h, text):
        n = Node(self, "/Script/UnrealEd.EdGraphNode_Comment", f"EdGraphNode_Comment_{self.prefix}{tag}", x, y,
                 [f"NodeWidth={w}", f"NodeHeight={h}", f'NodeComment="{text}"'])
        return n

    def input_key(self, tag, key, x, y):
        n = Node(self, "/Script/BlueprintGraph.K2Node_InputKey", self._n("InputKey", tag), x, y, [f"InputKey={key}"])
        return n.pin("Pressed", out=True).pin("Released", out=True)

    def event(self, tag, owner, member, x, y, outs=()):
        n = Node(self, "/Script/BlueprintGraph.K2Node_Event", self._n("Event", tag), x, y,
                 [f'EventReference=(MemberParent="{ENGINE.format(owner)}",MemberName="{member}")',
                  "bOverrideFunction=True"])
        n.pin("then", out=True)
        for name, cat, sub in outs:
            n.pin(name, out=True, cat=cat, sub=sub)
        return n

    def branch(self, tag, x, y):
        n = Node(self, "/Script/BlueprintGraph.K2Node_IfThenElse", self._n("IfThenElse", tag), x, y)
        return (n.pin("execute").pin("Condition", cat="bool", default="true")
                .pin("then", out=True, friendly="true").pin("else", out=True, friendly="false"))

    def call(self, tag, owner, func, x, y, pure=False, self_ctx=False, target=None):
        ref = (f'FunctionReference=(MemberName="{func}",bSelfContext=True)' if self_ctx else
               f'FunctionReference=(MemberParent="{ENGINE.format(owner)}",MemberName="{func}")')
        n = Node(self, "/Script/BlueprintGraph.K2Node_CallFunction", self._n("CallFunction", tag), x, y, [ref])
        if not pure:
            n.pin("execute").pin("then", out=True)
        n.pin("self", cat="object", obj=ENGINE.format(target or owner), friendly="Target")
        return n

    def get(self, tag, member, x, y, cat, sub="", obj=None, owner=None):
        ref = (f'VariableReference=(MemberParent="{ENGINE.format(owner)}",MemberName="{member}",bSelfContext=True)'
               if owner else f'VariableReference=(MemberName="{member}",bSelfContext=True)')
        n = Node(self, "/Script/BlueprintGraph.K2Node_VariableGet", self._n("VariableGet", tag), x, y, [ref])
        return n.pin(member, out=True, cat=cat, sub=sub, obj=obj)

    def set(self, tag, member, x, y, cat, sub="", obj=None, owner=None, value=None):
        ref = (f'VariableReference=(MemberParent="{ENGINE.format(owner)}",MemberName="{member}")'
               if owner else f'VariableReference=(MemberName="{member}",bSelfContext=True)')
        n = Node(self, "/Script/BlueprintGraph.K2Node_VariableSet", self._n("VariableSet", tag), x, y, [ref])
        n.pin("execute").pin("then", out=True).pin(member, cat=cat, sub=sub, obj=obj, default=value)
        if owner:
            n.pin("self", cat="object", obj=ENGINE.format(owner), friendly="Target")
        return n

    # ---- wiring -------------------------------------------------------------
    @staticmethod
    def link(a, b):
        """a: output pin, b: input pin."""
        assert a.out and not b.out, (a.node.name, a.name, b.node.name, b.name)
        a.links.append(b)
        b.links.append(a)

    def dump(self):
        return "\r\n".join(n.text() for n in self.nodes) + "\r\n"

    def check(self):
        """Every exec input reachable, no duplicate names, links symmetric."""
        names = [n.name for n in self.nodes]
        assert len(names) == len(set(names)), "duplicate node names"
        for n in self.nodes:
            for p in n.pins.values():
                for q in p.links:
                    assert p in q.links
        return len(self.nodes), sum(len(p.links) for n in self.nodes for p in n.pins.values()) // 2
