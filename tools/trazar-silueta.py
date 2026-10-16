#!/usr/bin/env python3
"""Mide la SILUETA del raton en el render y la escribe como tablas de contorno.

Por qué existe: el esquema y el render son dos capas que van superpuestas, pero
el raton del render es una imagen generada y su forma no es la nuestra. Alinear
solo la CAJA (lo que se hizo antes) deja las costuras y la aleta desplazadas,
porque las siluetas son distintas. La solución no es pedirle al modelo que
copie nuestra geometría (probado: no lo hace) sino al revés: medir la suya y
generar el esquema sobre ella.

Cómo mide: el fondo es un degradado suave y el raton esta centrado, asi que para
cada fila se estima el color de fondo interpolando entre el margen izquierdo y
el derecho (que son fondo) y se marca como raton todo lo que se aparte de esa
estimacion. Robusto ante el degradado, que es lo que hunde a un umbral fijo.

    python3 tools/trazar-silueta.py                 # escribe rat9/ui/silueta.json
    python3 tools/trazar-silueta.py --debug         # y una mascara para mirarla
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "rat9" / "ui" / "assets" / "raton-render.png"
OUT = ROOT / "rat9" / "ui" / "silueta.json"

# Los mismos numeros que gen-mouse-svg.py usa para colocar la capa. Si cambian
# alli, hay que cambiarlos aqui: son la conversion entre pixeles de la imagen y
# unidades del viewBox del esquema.
VIEWBOX = (720, 931)
BBOX_ESQUEMA = (44.0, 28.0, 362.0, 556.0)
BBOX_IMAGEN = (134.0, 135.0, 452.0, 658.0)
SX = BBOX_IMAGEN[2] / BBOX_ESQUEMA[2]
SY = BBOX_IMAGEN[3] / BBOX_ESQUEMA[3]
TX = BBOX_IMAGEN[0] - SX * BBOX_ESQUEMA[0]
TY = BBOX_IMAGEN[1] - SY * BBOX_ESQUEMA[1]

N_FILAS = 17          # filas de la tabla de contorno
MARGEN = 0.06         # fraccion de cada lado que se toma como fondo
UMBRAL = 0.055        # diferencia minima (0..1) para considerar "raton"
MIN_RUN = 6           # ancho minimo de una fila para no contar ruido

def mascara(arr: np.ndarray, umbral: float = UMBRAL) -> np.ndarray:
    """Marca el raton comparando cada pixel con el fondo estimado de SU fila."""
    h, w, _ = arr.shape
    gris = arr.mean(axis=2)
    m = np.zeros((h, w), dtype=bool)
    ancho_margen = max(3, int(w * MARGEN))
    for y in range(h):
        fila = gris[y]
        izq = fila[:ancho_margen].mean()
        der = fila[-ancho_margen:].mean()
        fondo = np.linspace(izq, der, w)          # degradado del fondo en esa fila
        m[y] = np.abs(fila - fondo) > umbral
    return m


def contornos(m: np.ndarray, fraccion_min: float = 0.30) -> dict[int, tuple[int, int]]:
    """Para cada fila, el primer y el ultimo pixel de raton.

    Se descartan las filas demasiado estrechas: debajo del raton queda su sombra
    proyectada, que tambien se aparta del fondo, y sin filtrarla la silueta
    medida se alargaba hasta el borde de la imagen.
    """
    crudos = {}
    for y in range(m.shape[0]):
        idx = np.flatnonzero(m[y])
        if idx.size < MIN_RUN:
            continue
        # el run mas largo de la fila: el raton, no un reflejo suelto
        cortes = np.split(idx, np.flatnonzero(np.diff(idx) > 3) + 1)
        mejor = max(cortes, key=len)
        if len(mejor) >= MIN_RUN:
            crudos[y] = (int(mejor[0]), int(mejor[-1]))
    if not crudos:
        return {}
    ancho_max = max(b - a for a, b in crudos.values())
    umbral_ancho = ancho_max * fraccion_min
    return {y: v for y, v in crudos.items() if (v[1] - v[0]) >= umbral_ancho}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", default=str(IMG))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--debug", action="store_true",
                    help="guarda una mascara para comprobarla a ojo")
    ap.add_argument("--umbral", type=float, default=UMBRAL,
                    help="diferencia minima (0..1) para considerar 'raton'. "
                         "Bajarlo si la mascara solo coge los brillos.")
    ap.add_argument("--barrido", action="store_true",
                    help="prueba varios umbrales y dice el ancho que da cada uno")
    a = ap.parse_args()

    arr = np.asarray(Image.open(a.img).convert("RGB"), dtype=np.float32) / 255.0

    if a.barrido:
        esperado = BBOX_IMAGEN[2]
        print(f"ancho esperado del raton: {esperado:.0f} px (de la caja medida)\n")
        for u in (0.01, 0.015, 0.02, 0.03, 0.04):
            mm = mascara(arr, u)
            ff = contornos(mm)
            if not ff:
                print(f"  umbral {u:<6} sin raton")
                continue
            an = [ff[y][1] - ff[y][0] for y in ff]
            print(f"  umbral {u:<6} filas {min(ff)}..{max(ff):<4} "
                  f"ancho max {max(an):>4}  filas {len(ff)}")
        return 0

    m = mascara(arr, a.umbral)
    filas = contornos(m)
    if not filas:
        raise SystemExit("no he encontrado el raton en la imagen: revisa el umbral")

    ys = sorted(filas)
    print(f"raton encontrado: filas {ys[0]}..{ys[-1]} de {arr.shape[0]}")
    anchos = [filas[y][1] - filas[y][0] for y in ys]
    print(f"ancho: min {min(anchos)}  max {max(anchos)}  (en pixeles de imagen)")

    if a.debug:
        dbg = np.zeros(arr.shape[:2], dtype=np.uint8)
        dbg[m] = 255
        Image.fromarray(dbg).save(ROOT / "docs/research/shots/silueta-mascara.png")
        print("  mascara en docs/research/shots/silueta-mascara.png")

    # Se muestrea en ALTURA DEL ESQUEMA (unidades del viewBox), que es donde
    # trabaja el generador, no en pixeles de la imagen.
    y0, y1 = ys[0], ys[-1]
    muestras = np.linspace(y0, y1, N_FILAS)
    left, right = [], []
    for yf in muestras:
        y = int(round(yf))
        # la fila mas cercana que tenga medida
        while y not in filas and y <= y1:
            y += 1
        if y not in filas:
            continue
        x_izq = (filas[y][0] - TX) / SX
        x_der = (filas[y][1] - TX) / SX
        y_svg = (y - TY) / SY
        left.append([round(y_svg, 1), round(x_izq, 1)])
        right.append([round(y_svg, 1), round(x_der, 1)])

    centro = float(np.mean([(l[1] + r[1]) / 2 for l, r in zip(left, right)]))
    datos = {"left": left, "right": right, "cx": round(centro, 1),
             "origen": Path(a.img).name,
             "medido": f"{len(left)} filas"}
    Path(a.out).write_text(json.dumps(datos, indent=2))
    print(f"escrito: {a.out}  ({len(left)} filas, centro x = {centro:.1f})")
    print("  primeras filas (y_svg, x_svg):", left[:3])
    print("  ultimas filas:                 ", left[-3:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
