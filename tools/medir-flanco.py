#!/usr/bin/env python3
"""Mide DONDE estan de verdad los controles del flanco en el render.

Por que existe: colocar los botones laterales y la rueda del pulgar "a ojo" sale
mal, y ya ha salido mal dos veces. El flanco izquierdo del render es una banda
estrecha recorrida por juntas (lineas oscuras que separan una pieza de la
siguiente). Esas juntas son minimos de brillo: se pueden MEDIR.

Metodo: para cada fila del raton se toma la banda del flanco (los primeros X% del
ancho local, medido con la silueta que ya calcula tools/trazar-silueta.py) y se
saca su brillo medio. Las juntas salen como caidas bruscas de ese perfil. Ademas
se mide la VARIANZA local: una pieza estriada (la rueda del pulgar, el boton de
modos) tiene mucha mas varianza que una lisa.

La salida va en unidades del ESQUEMA, no de la imagen: es lo que puede consumir
tools/gen-mouse-svg.py directamente.

    python3 tools/medir-flanco.py            # tabla por pantalla
    python3 tools/medir-flanco.py --crop     # y un recorte del flanco para mirarlo
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "rat9/ui/assets/raton-original.png"

# Mismas constantes que gen-mouse-svg.py: es la conversion entre la caja del raton
# en la imagen y la caja del raton en el dibujo.
Y_NOSE, Y_HEEL = 60.0, 700.0
BANDA = 0.20          # fraccion del ancho local que se toma como flanco
SUAVIZADO = 9         # filas de media movil, para que el ruido no invente juntas


def cargar_modulo(nombre: str, ruta: Path):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", default=str(IMG))
    ap.add_argument("--crop", action="store_true", help="guardar un recorte del flanco")
    a = ap.parse_args()

    ts = cargar_modulo("ts", ROOT / "tools/trazar-silueta.py")
    img = Image.open(a.img).convert("RGB")
    arr = np.asarray(img).astype(float) / 255.0
    gris = arr.mean(axis=2)

    m = ts.mascara(arr, 0.02)
    filas = ts.contornos(m)
    ys = sorted(filas)
    y0, y1 = ys[0], ys[-1]
    alto = y1 - y0
    print(f"raton en la imagen: y {y0}..{y1}  ({alto} px de alto)")
    print(f"convertir a esquema: y_esq = {Y_NOSE:.0f} + v * {Y_HEEL - Y_NOSE:.0f}\n")

    # ── perfil de la banda del flanco ────────────────────────────────────────
    vals, var, xs_band = [], [], []
    for y in ys:
        a0, b0 = filas[y]
        ancho = b0 - a0
        if ancho < 30:
            continue
        x1 = a0 + int(BANDA * ancho)
        trozo = gris[y, a0:x1]
        vals.append(trozo.mean())
        var.append(trozo.var())
        xs_band.append((a0, x1))
    vals = np.array(vals)
    var = np.array(var)

    def suavizar(v, n):
        if len(v) < n:
            return v
        k = np.ones(n) / n
        return np.convolve(v, k, mode="same")

    vs = suavizar(vals, SUAVIZADO)
    vv = suavizar(var, SUAVIZADO)

    # ── juntas: caidas bruscas de brillo ──────────────────────────────────────
    print("  v      y_esq   brillo   varianza   nota")
    marcas = []
    for i, y in enumerate(ys):
        if i >= len(vs):
            break
        v = (y - y0) / alto
        y_esq = Y_NOSE + v * (Y_HEEL - Y_NOSE)
        d = vs[i] - (vs[i - 2] if i >= 2 else vs[i])
        nota = ""
        if d < -0.045 and 0.03 < v < 0.97:
            nota = "JUNTA"
            marcas.append((round(float(y_esq), 1), round(float(v), 3),
                           round(float(d), 3)))
        if i % 8 == 0 or nota:
            print(f"  {v:5.3f}  {y_esq:6.1f}   {vs[i]:5.3f}    {vv[i]:6.4f}   {nota}")

    print("\nJUNTAS detectadas (y del esquema, v, caida):")
    for t in marcas:
        print("   ", t)

    # ── zonas estriadas: varianza alta sostenida ─────────────────────────────
    umbral_var = float(np.percentile(vv[vv > 0], 82)) if (vv > 0).any() else 0.0
    print(f"\nZonas estriadas (varianza > {umbral_var:.4f}):")
    dentro = False
    ini = None
    for i, y in enumerate(ys):
        if i >= len(vv):
            break
        alto_v = vv[i] > umbral_var
        if alto_v and not dentro:
            ini, dentro = y, True
        elif not alto_v and dentro:
            if y - ini > 6:
                vv0 = (ini - y0) / alto
                vv1 = (y - y0) / alto
                print(f"    y_esq {Y_NOSE + vv0 * 640:6.1f} .. {Y_NOSE + vv1 * 640:6.1f}"
                      f"   (v {vv0:.3f}..{vv1:.3f}, {y - ini} px)")
            dentro = False

    if a.crop:
        rec = img.crop((0, y0, int(0.55 * img.width), y1))
        sal = ROOT / "docs/research/shots/flanco-recorte.png"
        rec.resize((rec.width * 2, rec.height * 2), Image.LANCZOS).save(sal)
        print(f"\nrecorte del flanco: {sal}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
