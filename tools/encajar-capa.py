#!/usr/bin/env python3
"""Mide la caja del ratón en la imagen base y guarda el encaje de la capa.

Por qué existe: la capa del esquema que va ENCIMA de la imagen no puede llevar
la transformación escrita a mano en el generador, porque cada vez que cambia la
imagen de base cambian los números y se desincroniza en silencio. Esto lo mide
y lo deja en un JSON; el generador lo lee.

    python3 tools/encajar-capa.py --img rat9/ui/assets/raton-original.png
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "rat9" / "ui" / "capa.json"

# Caja del ratón dentro del viewBox del ESQUEMA. Sale de los parámetros de
# tools/gen-mouse-svg.py: la silueta va de x 44 a 406 y de y 28 a 584.
BBOX_ESQUEMA = (44.0, 28.0, 362.0, 556.0)


def medir(img: Path, fuzz: float) -> tuple[int, int, int, int]:
    """Caja del ratón en la imagen, con ImageMagick (-fuzz + -trim)."""
    geo = subprocess.run(
        ["magick", str(img), "-fuzz", f"{fuzz}%", "-format", "%@", "info:"],
        capture_output=True, text=True, check=True).stdout.strip()
    # formato: WxH+X+Y
    wh, x, y = geo.split("+")
    w, h = wh.split("x")
    return int(w), int(h), int(x), int(y)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", default=str(ROOT / "rat9/ui/assets/raton-original.png"))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--fuzz", type=float, default=12.0)
    a = ap.parse_args()

    img = Path(a.img).resolve()
    if not img.is_file():
        raise SystemExit(f"no existe la imagen: {img}")

    tw, th, tx, ty = medir(img, a.fuzz)
    sx = tw / BBOX_ESQUEMA[2]
    sy = th / BBOX_ESQUEMA[3]
    mx = tx - sx * BBOX_ESQUEMA[0]
    my = ty - sy * BBOX_ESQUEMA[1]

    # tamaño de la imagen base (el viewBox de la capa tiene que ser el suyo)
    vw, vh = (int(v) for v in subprocess.run(
        ["magick", "identify", "-format", "%w %h", str(img)],
        capture_output=True, text=True, check=True).stdout.split())

    datos = {
        "imagen": img.relative_to(ROOT).as_posix(),
        "viewbox": [vw, vh],
        "bbox_imagen": [tx, ty, tw, th],
        "bbox_esquema": list(BBOX_ESQUEMA),
        "scale": [round(sx, 5), round(sy, 5)],
        "translate": [round(mx, 2), round(my, 2)],
    }
    Path(a.out).write_text(json.dumps(datos, indent=2))
    print(f"imagen base : {datos['imagen']}  {vw}x{vh}")
    print(f"raton en ella: {tw}x{th}+{tx}+{ty}")
    print(f"encaje      : escala {sx:.5f} x {sy:.5f}   traslado {mx:.1f}, {my:.1f}")
    print(f"escrito     : {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
