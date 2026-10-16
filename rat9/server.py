"""
rat9.server — API local del configurador.

Solo escucha en localhost. Expone el estado del raton y el empaquetado
de perfiles. La escritura requiere que el proceso corra con root.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from rat9.protocol import (Rat9, Rat9Error, REPORT_SIZE, AXIS_X, AXIS_Y,
                            N_MODES, FACTORY_DPI)
from rat9.schema import (MINIMAL_PROFILE, SCHEMA_PR0, NODE_TYPES, XML_TAGS,
                         RAT9_BUTTONS, RAT9_AXES, HOTKEYS,
                         BLOCK_PRESS, BLOCK_REPEAT, BLOCK_RELEASE,
                         PLAYBACK_OPEN, PLAYBACK_CLOSED,
                         SENS_MIN, SENS_MAX)
from rat9 import pr0

PROFILES_DIR = Path(__file__).parent.parent / "profiles"


def read_state() -> dict:
    """Estado del raton. No reclama la interfaz, no toca nada."""
    try:
        with Rat9(claim=False) as r:
            s = r.status()
            return {
                "connected": True,
                "mode": s.mode,
                # battery() ya descarta valores corruptos del firmware
                "battery": s.battery,
                "dpi": [
                    {"mode": d.mode, "axis": d.axis_name, "dpi": d.dpi,
                     "factory": FACTORY_DPI[d.mode],
                     "changed": d.dpi is not None and d.dpi != FACTORY_DPI[d.mode]}
                    for d in r.all_dpi()
                ],
            }
    except Rat9Error as e:
        return {"connected": False, "error": str(e)}


def pack_profile(xml: str) -> dict:
    """Empaqueta un perfil y devuelve los bloques, sin escribir."""
    payload = bytes([0, 0, 0, 1, 0xFF, 0xFF, 0xFF, 0xFF, 0, 0]) + \
        xml.encode("utf-16-le")
    blocks = [payload[i:i + REPORT_SIZE].hex()
              for i in range(0, len(payload), REPORT_SIZE)]
    return {
        "xml_chars": len(xml),
        "payload_bytes": len(payload),
        "block_count": len(blocks),
        "block_size": REPORT_SIZE,
        "blocks": blocks,
    }


def list_profiles() -> list[dict]:
    if not PROFILES_DIR.exists():
        return []
    return [
        {"name": p.stem, "bytes": p.stat().st_size}
        for p in sorted(PROFILES_DIR.glob("*.pr0"))
    ]


def read_profile(name: str) -> str | None:
    p = (PROFILES_DIR / f"{name}.pr0").resolve()
    if not str(p).startswith(str(PROFILES_DIR.resolve())) or not p.exists():
        return None
    return p.read_text()


def write_profile(name: str, xml: str) -> dict:
    if not xml.lstrip().startswith("["):
        raise ValueError("el perfil debe empezar por '[' (formato pr0)")
    PROFILES_DIR.mkdir(exist_ok=True)
    p = PROFILES_DIR / f"{name}.pr0"
    p.write_text(xml)
    return {"name": name, "bytes": p.stat().st_size}


def parse_profile(xml: str) -> dict:
    """Parsea un perfil .pr0 y lo devuelve estructurado para la GUI."""
    try:
        root = pr0.parse(xml)
    except pr0.Pr0SyntaxError as e:
        return {"error": f"sintaxis: {e}"}

    def dump(n):
        return {
            "tag": n.tag,
            "name": n.name,
            "attrs": n.attrs,
            "children": [dump(c) for c in n.children],
        }

    cmds = root.first("commands")
    commands = []
    if cmds:
        for c in cmds.children:
            blocks = []
            for b in c.children:
                actions = [{
                    "device": a.attrs.get("device"),
                    "page": a.int_attr("page"),
                    "usage": a.int_attr("usage"),
                    "value": a.int_attr("value", 1),
                    "time": a.int_attr("time", 0),
                } for a in b.children if a.tag == "action"]
                blocks.append({
                    "type": b.attrs.get("type", BLOCK_PRESS),
                    "closed": b.name == "macro",
                    "actions": actions,
                })
            commands.append({
                "name": c.attrs.get("name"),
                "guid": c.name,
                "blocks": blocks,
            })
    return {"ok": True, "root": dump(root), "commands": commands}


def build_from_gui(spec: dict) -> dict:
    """Construye un perfil .pr0 desde la estructura que envia la GUI."""
    cmds = []
    for i, c in enumerate(spec.get("commands", [])):
        guid = c.get("guid") or f"{i+1:08x}-0000-0000-0000-000000000000"
        blocks = []
        for b in c.get("blocks", []):
            acts = []
            for a in b.get("actions", []):
                dev = a.get("device", "keyboard")
                page = int(a.get("page") or
                           {"keyboard": 0x7, "mouse": 0x9, "hotkey": 0xC}[dev])
                usage = int(a.get("usage") or 0)
                value = int(a.get("value", 1))
                time = int(a.get("time") or 0)
                if dev == "keyboard":
                    n = pr0.key_action(usage, value == 1, time)
                elif dev == "mouse":
                    if page == 0x1 and usage == 0x38:
                        n = pr0.wheel_action(value == 1, time)
                    else:
                        n = pr0.mouse_action(usage, value == 1, time)
                else:
                    n = pr0.hotkey_action(usage, time)
                acts.append(n)
            blocks.append(pr0.block(acts, b.get("type", BLOCK_PRESS),
                                    bool(b.get("closed"))))
        cmds.append(pr0.command(c.get("name") or f"Macro {i+1}", guid,
                                *blocks[:3]))
    xml = pr0.build_profile(cmds, spec.get("name", "Linux"),
                            spec.get("short", "L"))
    return {"xml": xml, "pack": pack_profile(xml)}


class Handler(BaseHTTPRequestHandler):
    def _json(self, obj, status=200):
        body = json.dumps(obj, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # silencio

    def _static(self, fn: str, ctype: str, subdir: str = "web"):
        """Sirve un fichero de rat9/<subdir>/. `fn` no puede salirse de ahi."""
        base = (Path(__file__).parent / subdir).resolve()
        fp = (base / fn).resolve()
        # sin esto, "/ui/../../etc/passwd" se sirve tan tranquilo
        if base not in fp.parents or not fp.is_file():
            self._json({"error": "no encontrado"}, 404)
            return
        body = fp.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    MIME = {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".json": "application/json",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".woff2": "font/woff2",
        ".woff": "font/woff",
        ".ttf": "font/ttf",
    }

    def query_xml(self):
        from urllib.parse import parse_qs, urlparse
        q = parse_qs(urlparse(self.path).query)
        v = q.get("xml", [""])
        return v[0]

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/":
            self._json({"ok": True, "ui": "/ui/"})
        elif p in ("/ui", "/ui/"):
            # la interfaz nueva vive en rat9/ui/
            self._static("index.html", self.MIME[".html"], "ui")
        elif p.startswith("/ui/"):
            fn = p[len("/ui/"):]
            self._static(fn, self.MIME.get(Path(fn).suffix,
                                           "application/octet-stream"), "ui")
        elif p == "/editor" or p == "/editor/":
            self._json({"ok": True, "ui": "/editor/editor.html"})
        elif p.startswith("/editor/"):
            fn = p[len("/editor/"):]
            self._static(fn, self.MIME.get(Path(fn).suffix,
                                           "application/octet-stream"))
        elif p == "/api/state":
            self._json(read_state())
        elif p == "/api/schema":
            self._json({
                "schema_pr0": SCHEMA_PR0,
                "node_types": NODE_TYPES,
                "xml_tags": XML_TAGS,
                "minimal": MINIMAL_PROFILE,
            })
        elif p == "/api/catalog":
            self._json({
                "buttons": RAT9_BUTTONS,
                "axes": RAT9_AXES,
                "hotkeys": HOTKEYS,
                "blocks": [BLOCK_PRESS, BLOCK_REPEAT, BLOCK_RELEASE],
                "playback": [PLAYBACK_OPEN, PLAYBACK_CLOSED],
                "sensitivity": {"min": SENS_MIN, "max": SENS_MAX},
            })
        elif p == "/api/keys":
            fp = Path(__file__).parent / "web" / "keys.json"
            self._json(json.loads(fp.read_text()))
        elif p == "/api/buttons":
            # nombres legibles de cada tecla (HID usage -> nombre)
            fp = Path(__file__).parent / "web" / "keys.json"
            self._json(json.loads(fp.read_text()))
        elif p == "/api/hotkeys":
            self._json(HOTKEYS)
        elif p == "/api/parse":
            self._json(parse_profile(self.query_xml()))
        elif p == "/api/profiles":
            self._json(list_profiles())
        elif p.startswith("/api/profile/"):
            xml = read_profile(p[len("/api/profile/"):])
            if xml is None:
                self._json({"error": "no encontrado"}, 404)
            else:
                self._json({"name": p.rsplit("/", 1)[-1], "xml": xml})
        else:
            self._json({"error": "ruta desconocida"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            self._json({"error": "JSON invalido"}, 400)
            return

        if self.path == "/api/build":
            try:
                self._json(build_from_gui(data))
            except (KeyError, TypeError, ValueError) as e:
                self._json({"error": str(e)}, 400)
        elif self.path == "/api/pack":
            self._json(pack_profile(data.get("xml") or MINIMAL_PROFILE))
        elif self.path == "/api/profile":
            try:
                self._json(write_profile(data["name"], data["xml"]))
            except (KeyError, ValueError) as e:
                self._json({"error": str(e)}, 400)
        else:
            self._json({"error": "ruta desconocida"}, 404)


def serve(port: int = 8766, host: str = "127.0.0.1"):
    srv = HTTPServer((host, port), Handler)
    print(f"rat9-config en http://{host}:{port}")
    print("Ctrl+C para salir")
    srv.serve_forever()


if __name__ == "__main__":
    import sys
    serve(int(sys.argv[1]) if len(sys.argv) > 1 else 8766)
