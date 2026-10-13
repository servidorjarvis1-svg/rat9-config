"""
rat9.server — API local del configurador.

Solo escucha en localhost. Expone el estado del raton y el empaquetado
de perfiles. La escritura requiere que el proceso corra con root.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from rat9.protocol import Rat9, Rat9Error, REPORT_SIZE
from rat9.schema import MINIMAL_PROFILE, SCHEMA_PR0, NODE_TYPES, XML_TAGS

PROFILES_DIR = Path(__file__).parent.parent / "profiles"


def read_state() -> dict:
    """Estado del raton. No reclama la interfaz, no toca nada."""
    try:
        with Rat9(claim=False) as r:
            s = r.status()
            return {
                "connected": True,
                "profile": s.profile,
                # el firmware puede devolver basura (ej. 137 %): validar rango
                "battery": s.battery if s.battery is not None and s.battery <= 100 else None,
                "battery_raw": s.battery,
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

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/":
            self._json({"ok": True, "ui": "/ui/"})
        elif p == "/ui/" or p == "/ui/index.html":
            body = (Path(__file__).parent / "web" / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif p == "/api/state":
            self._json(read_state())
        elif p == "/api/schema":
            self._json({
                "schema_pr0": SCHEMA_PR0,
                "node_types": NODE_TYPES,
                "xml_tags": XML_TAGS,
                "minimal": MINIMAL_PROFILE,
            })
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

        if self.path == "/api/pack":
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
