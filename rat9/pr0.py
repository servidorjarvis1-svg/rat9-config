"""
rat9.pr0 — parser y generador del formato de perfil .pr0 del R.A.T.9.

El formato NO es XML. Es texto UTF-16LE con la gramática de corchetes:

    [tag nombre_del_nodo attr=valor attr=valor [hijo] [hijo]]

Reglas de serializacion (del codigo original, WritePr0.cs / PersistAttributes.cs):
  - Los atributos uint se escriben en hexadecimal de 8 digitos: 0xXXXXXXXX
  - Los atributos marcados como PersistDecimal van en decimal
  - Los valores por defecto NO se escriben
  - Las cadenas con espacios o caracteres especiales van entrecomilladas con '
  - El nodo puede llevar su "nombre" como primer elemento del tag:
    [actioncommand=<guid> name=MiMacro ...]
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- tokenizer ---------------------------------------------------------------

TOKEN_NAME = re.compile(r"[A-Za-z_][\w-]*(=[^\s\[\]]+)?")

TOKEN_ATTR = re.compile(
    r"""(?P<key>[A-Za-z_][\w-]*)=(?P<val>"[^"]*"|'[^']*'|[^\s\[\]]+)""")


class Pr0SyntaxError(ValueError):
    pass


@dataclass
class Node:
    tag: str
    name: str | None = None       # el "name" dentro del corchete inicial
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    def find(self, tag: str):
        return [c for c in self.children if c.tag == tag]

    def first(self, tag: str):
        for c in self.children:
            if c.tag == tag:
                return c
        return None

    def get(self, key, default=None):
        return self.attrs.get(key, default)

    def int_attr(self, key, default=None):
        """Lee un atributo como entero. Acepta 0x10, 16 y 16 decimal."""
        v = self.attrs.get(key)
        if v is None:
            return default
        if isinstance(v, int):
            return v
        s = str(v).strip()
        try:
            return int(s, 16) if s.lower().startswith("0x") else int(s)
        except ValueError:
            return default


def parse(text: str) -> Node:
    """Parsea un perfil .pr0 completo.

    Gramática:
        [tag[=nombre] [attr=valor ...] [hijo ...]]
    """
    root = None
    stack: list[Node] = []
    i, n = 0, len(text)
    pending: str | None = None   # token leido tras '[' esperando ver si es ']'

    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
            continue

        if c == '[':
            i += 1
            # leer el nombre del nodo (puede ser tag o tag=guid)
            while i < n and text[i].isspace():
                i += 1
            m = TOKEN_NAME.match(text, i)
            if not m:
                raise Pr0SyntaxError(f"se esperaba un nombre de nodo en pos {i}")
            i = m.end()
            head = m.group(0)
            tag, _, nm = head.partition('=')
            node = Node(tag=tag, name=nm or None)
            if stack:
                stack[-1].children.append(node)
            elif root is None:
                root = node
            stack.append(node)
            continue

        if c == ']':
            i += 1
            if not stack:
                raise Pr0SyntaxError(f"corchete de cierre sin abrir en pos {i-1}")
            stack.pop()
            continue

        if c == '[':
            continue

        # atributo nombre=valor
        m = TOKEN_ATTR.match(text, i)
        if m:
            v = m.group("val")
            if v[:1] in "\"'":
                v = v[1:-1]
            if not stack:
                raise Pr0SyntaxError(f"atributo fuera de nodo en pos {i}")
            stack[-1].attrs[m.group("key")] = v
            i = m.end()
            continue

        raise Pr0SyntaxError(f"token inesperado {text[i]!r} en pos {i}")

    if stack:
        raise Pr0SyntaxError(f"{len(stack)} nodos sin cerrar")
    if root is None:
        raise Pr0SyntaxError("perfil vacio")
    return root


# --- generador ---------------------------------------------------------------

def quote(s: str) -> str:
    if re.search(r"[\s'\[\]=\r\n]", s):
        return "'" + s.replace("'", "\\'") + "'"
    return s


def esc(v) -> str:
    """Formatea un valor: hex de 8 digitos para enteros, texto para cadenas."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return f"0x{v:08X}"
    return quote(str(v))


def serialize(node: Node, indent: int = 0, hex_attrs: bool = True) -> str:
    """Serializa un nodo a texto .pr0."""
    pad = "  " * indent
    head = node.tag
    if node.name:
        head += "=" + node.name
    parts = [f"{k}={esc(v) if hex_attrs and isinstance(v, int) else quote(str(v))}"
             for k, v in node.attrs.items()]
    inner = " ".join(parts)
    line = f"[{head}" + (f" {inner}" if inner else "")
    if not node.children:
        return pad + line + "]"
    lines = [pad + line]
    for c in node.children:
        lines.append(serialize(c, indent + 1, hex_attrs))
    lines.append(pad + "]")
    return "\n".join(lines)


# --- atajos para construir un perfil desde la GUI ----------------------------

def build_profile(commands: list[Node], name: str = "Linux",
                  short: str = "L") -> str:
    """Ensambla un perfil completo a partir de una lista de comandos."""
    guids = "0123456789abcdef"
    def guid(n: int) -> str:
        h = f"{n:032x}"
        return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"

    controller = Node("controller", name=guid(1), attrs={"req": "group"})
    member = Node("member", name=guid(2),
                  attrs={"req": "name shortname", "name": name, "shortname": short})
    controls = Node("controls", attrs={"num": "1", "notempty": "true"})
    shifts = Node("shifts", attrs={"num": "1"})
    shift = Node("shift", name=guid(3), attrs={"req": "name", "name": "Shift1"})
    assignments = Node("assignments")
    controller.children += [member, controls, shifts]
    shifts.children.append(shift)
    controllers = Node("controllers", children=[controller])
    shift.children.append(assignments)

    cmds = Node("commands")
    cmds.children += commands

    root = Node("profile", children=[controllers, cmds])
    return serialize(root) + "\n"


def key_action(usage: int, down: bool = True, time_ms: int = 0,
               page: int = 0x7) -> Node:
    a = {"device": "keyboard", "page": page, "usage": usage, "value": 1 if down else 0}
    if time_ms:
        a["time"] = time_ms
    return Node("action", attrs=a)


def mouse_action(usage: int, down: bool = True, time_ms: int = 0) -> Node:
    a = {"device": "mouse", "page": 0x9, "usage": usage, "value": 1 if down else 0}
    if time_ms:
        a["time"] = time_ms
    return Node("action", attrs=a)


def wheel_action(up: bool = True, time_ms: int = 0) -> Node:
    a = {"device": "mouse", "page": 0x1, "usage": 0x38,
         "value": 1 if up else 0xFF}
    if time_ms:
        a["time"] = time_ms
    return Node("action", attrs=a)


def hotkey_action(usage: int, time_ms: int = 0) -> Node:
    a = {"device": "hotkey", "page": 0xC, "usage": usage, "value": 1}
    if time_ms:
        a["time"] = time_ms
    return Node("action", attrs=a)


def block(actions: list[Node], block_type: str = "press",
          closed: bool = False) -> Node:
    n = Node("actionblock", name="macro" if closed else None)
    if block_type != "press":
        n.attrs["type"] = block_type
    n.children = actions
    return n


def command(name: str, guid: str, press=None, repeat=None, release=None) -> Node:
    n = Node("actioncommand", name=guid, attrs={"name": name})
    for b in (press, repeat, release):
        if b is not None:
            n.children.append(b)
    return n
