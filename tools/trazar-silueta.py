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

N_FILAS = 23          # filas de la tabla de contorno
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


def contornos(m: np.ndarray, min_corrida: int = 10,
              cierre: int = 28) -> dict[int, tuple[int, int]]:
    """Borde EXTERIOR del raton en cada fila: donde empieza y donde acaba.

    El truco esta en el CIERRE. En cada fila, el raton no sale como una mancha
    continua: sus propias bandas oscuras se confunden con el fondo y la mascara
    sale agujereada, asi que la fila son varios trozos separados. Y ademas hay
    marcas sueltas por el fondo (brillos, bordes del fotograma).

    Por eso: se juntan los trozos separados por menos de `cierre` px (los
    agujeros de dentro del raton son pequeños) y se toma el bloque MAYOR, que es
    el raton; asi las marcas sueltas del fondo se quedan fuera sin necesidad de
    umbrales finos. Entrar desde fuera hacia dentro trozo a trozo no bastaba:
    el primer trozo podia ser una marca del fondo.
    """
    salida = {}
    alto, ancho = m.shape
    for y in range(alto):
        fila = m[y]
        idx = np.flatnonzero(fila)
        if idx.size < min_corrida:
            continue
        # bloques = trozos con los huecos pequeños ya cerrados
        cortes = np.flatnonzero(np.diff(idx) > cierre)
        inicio = np.concatenate(([0], cortes + 1))
        fin = np.concatenate((cortes, [idx.size - 1]))
        bloques = [(int(idx[a]), int(idx[b])) for a, b in zip(inicio, fin)]
        a, b = max(bloques, key=lambda t: t[1] - t[0])
        if b - a >= min_corrida:
            salida[y] = (a, b)
    return salida


def suavizar(filas: dict[int, tuple[int, int]], ventana: int = 9
             ) -> dict[int, tuple[int, int]]:
    """Mediana por ventana sobre la serie de bordes, para quitar picos sueltos.

    Un solo pixel que salte a una sombra desplaza el contorno entero en esa
    fila; la mediana lo ignora y conserva el borde real.
    """
    if len(filas) < ventana:
        return filas
    ys = sorted(filas)
    izqs = np.array([filas[y][0] for y in ys], dtype=float)
    ders = np.array([filas[y][1] for y in ys], dtype=float)
    mitad = ventana // 2
    out = {}
    for i, y in enumerate(ys):
        a, b = max(0, i - mitad), min(len(ys), i + mitad + 1)
        out[y] = (int(np.median(izqs[a:b])), int(np.median(ders[a:b])))
    return out


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
    filas = suavizar(contornos(m))
    if not filas:
        raise SystemExit("no he encontrado el raton en la imagen: revisa el umbral")

    ys = sorted(filas)
    print(f"raton encontrado: filas {ys[0]}..{ys[-1]} de {arr.shape[0]}")
    anchos = [filas[y][1] - filas[y][0] for y in ys]
    print(f"ancho: min {min(anchos)}  max {max(anchos)}  (en pixeles de imagen)")

    if a.debug:
        # dos comprobaciones distintas: la mascara (que sale agujereada, y da
        # igual) y el CONTORNO medido sobre el render, que es lo que importa
        dbg = np.zeros(arr.shape[:2], dtype=np.uint8)
        dbg[m] = 255
        Image.fromarray(dbg).save(ROOT / "docs/research/shots/silueta-mascara.png")
        from PIL import ImageDraw
        vis = Image.open(a.img).convert("RGB")
        dr = ImageDraw.Draw(vis)
        for y, (x0, x1) in filas.items():
            dr.point((x0, y), fill=(255, 90, 90))
            dr.point((x1, y), fill=(255, 90, 90))
        vis.save(ROOT / "docs/research/shots/silueta-contorno.png")
        print("  mascara y contorno en docs/research/shots/")

    # Se normaliza a la CAJA DEL RATON (0..1 en cada eje), no a la imagen: asi
    # el generador puede reconstruir el contorno en su propio viewBox sin
    # depender del tamano de la imagen ni de donde caiga el raton en ella.
    x0 = min(f[0] for f in filas.values())
    x1 = max(f[1] for f in filas.values())
    y0, y1 = min(filas), max(filas)
    ancho, alto = x1 - x0, y1 - y0
    print(f"caja del contorno: {ancho}x{alto}+{x0}+{y0}")

    left, right = [], []
    # Muestreo NO uniforme: coseno, que aprieta las filas en el morro y en el
    # talon, que es donde la curva gira, y las espacia en el cuerpo, que es casi
    # recto. Con muestreo uniforme el morro salia con dos puntos y el dibujo lo
    # reproducia como una cuna estrecha, dejando los botones fuera del contorno.
    for i in range(N_FILAS):
        v_objetivo = (1 - np.cos(np.pi * i / (N_FILAS - 1))) / 2
        y = int(round(y0 + v_objetivo * alto))
        while y not in filas and y <= y1:
            y += 1
        if y not in filas:
            continue
        v = round((y - y0) / alto, 4)
        left.append([v, round((filas[y][0] - x0) / ancho, 4)])
        right.append([v, round((filas[y][1] - x0) / ancho, 4)])

    datos = {"left": left, "right": right,
             "origen": Path(a.img).name,
             "medido": f"{len(left)} filas",
             "caja_px": [x0, y0, ancho, alto]}
    Path(a.out).write_text(json.dumps(datos, indent=2))
    print(f"escrito: {a.out}  ({len(left)} filas normalizadas)")
    print("  primeras (v, x):", left[:3])
    print("  ultimas:        ", left[-3:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
