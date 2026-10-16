#!/usr/bin/env python3
"""Renderiza un SVG del proyecto a PNG resolviendo antes las variables CSS.

Por qué existe: los renderizadores de SVG no soportan `var(--x)` igual de bien
que un navegador (resvg ni lo intenta en `stop-color`; librsvg lo resuelve a
medias). En vez de duplicar los colores en el SVG, este script sustituye cada
`var(--token)` por el valor declarado en el propio `<style>` y renderiza el
resultado. Así el SVG sigue usando tokens en el repositorio y aun así se puede
previsualizar desde la terminal.

    python3 tools/svg-render.py rat9/ui/diagram-mouse.svg salida.png [--bg #0a0d13] [--zoom 2]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TOKEN_RE = re.compile(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", re.IGNORECASE)


def resolve_tokens(svg: str) -> tuple[str, dict[str, str]]:
    """Sustituye var(--token) por su valor. Devuelve (svg, tokens)."""
    style_blocks = re.findall(r"<style[^>]*>(.*?)</style>", svg, re.DOTALL)
    tokens: dict[str, str] = {}
    for block in style_blocks:
        for name, value in TOKEN_RE.findall(block):
            tokens.setdefault(name.lower(), value.strip())

    if not tokens:
        return svg, {}

    # var(--x) y var(--x, fallback)
    def sub(m: re.Match) -> str:
        name = m.group(1).lower()
        fallback = m.group(2)
        return tokens.get(name, (fallback or "").strip() or "none")

    svg = re.sub(r"var\(\s*(--[a-z0-9-]+)\s*(?:,\s*([^)]*))?\)", sub, svg,
                 flags=re.IGNORECASE)
    # deja las declaraciones en el <style> para que el SVG siga siendo válido
    return svg, tokens


def main() -> int:
    ap = argparse.ArgumentParser(description="SVG a PNG resolviendo tokens CSS")
    ap.add_argument("svg")
    ap.add_argument("png")
    ap.add_argument("--bg", default=None,
                    help="color de fondo (si se omite, queda transparente)")
    ap.add_argument("--zoom", type=float, default=2.0)
    ap.add_argument("--width", type=int, default=None,
                    help="ancho final en px (implica recomponer sobre --bg)")
    args = ap.parse_args()

    src = Path(args.svg)
    if not src.is_file():
        sys.exit(f"no existe: {src}")
    svg, tokens = resolve_tokens(src.read_text())
    print(f"tokens resueltos: {len(tokens)}")

    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as fh:
        fh.write(svg)
        tmp = Path(fh.name)

    raw = tmp.with_suffix(".raw.png")
    try:
        subprocess.run(["rsvg-convert", "-z", str(args.zoom), "-o", str(raw),
                        str(tmp)], check=True)
        if args.bg or args.width:
            out = Path(args.png)
            out.parent.mkdir(parents=True, exist_ok=True)
            cmd = ["magick", str(raw)]
            if args.width:
                cmd += ["-resize", f"{args.width}x"]
            if args.bg:
                # -background TIENE que ir despues de la imagen de entrada;
                # -flatten compone sobre ese color y de paso quita el alfa.
                cmd += ["-background", args.bg, "-flatten"]
            cmd += [str(out)]
            subprocess.run(cmd, check=True)
            print(f"escrito: {out}")
        else:
            Path(args.png).write_bytes(raw.read_bytes())
            print(f"escrito: {args.png}")
    finally:
        tmp.unlink(missing_ok=True)
        raw.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
