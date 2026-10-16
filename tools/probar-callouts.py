#!/usr/bin/env python3
"""Prueba: colocar el raton en el lienzo de la lamina de llamadas del original.

La hipotesis es que el raton llenaba el ALTO del lienzo (las 15 anclas de la
lamina van de y=28 a y=904, o sea todo el alto) y que las cajas de la izquierda
flotaban encima de su flanco. Se recorta el raton con su propia silueta MEDIDA
(no a ojo) y se compone debajo de la lamina para ver si las anclas caen sobre
piezas con sentido.
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ts", ROOT / "tools/trazar-silueta.py")
ts = importlib.util.module_from_spec(spec)
sys.modules["ts"] = ts
spec.loader.exec_module(ts)

alto_lienzo, ancho_lienzo = 1000, 500

img = Image.open(ROOT / "rat9/ui/assets/raton-original.png").convert("RGB")
arr = np.asarray(img).astype(float) / 255.0
m = ts.mascara(arr, 0.02)
filas = ts.contornos(m)
print(f"silueta medida: {len(filas)} filas de {arr.shape[0]}")

# silueta SOLIDA rellenando entre borde izquierdo y derecho de cada fila
solida = np.zeros_like(m)
ys = sorted(filas)
for y in ys:
    a, b = filas[y]
    solida[y, a:b + 1] = True
# cerrar los extremos: extender la primera y la ultima fila medida
y0, y1 = ys[0], ys[-1]
for y in range(y0):
    solida[y, filas[y0][0]:filas[y0][1] + 1] = True
for y in range(y1 + 1, solida.shape[0]):
    solida[y, filas[y1][0]:filas[y1][1] + 1] = True

xs = np.flatnonzero(solida.any(axis=0))
x0, x1 = xs.min(), xs.max()
print(f"caja del raton en la imagen: x {x0}..{x1}  y {y0}..{y1}  "
      f"({x1 - x0 + 1}x{y1 - y0 + 1})")

# recorte + mascara como alpha
recorte = img.crop((int(x0), int(y0), int(x1) + 1, int(y1) + 1))
alfa = Image.fromarray((solida[y0:y1 + 1, x0:x1 + 1] * 255).astype(np.uint8))
recorte.putalpha(alfa)

# escalar a la altura del lienzo y centrar
esc = alto_lienzo / recorte.height
nuevo = (max(1, int(round(recorte.width * esc))), alto_lienzo)
recorte = recorte.resize(nuevo, Image.LANCZOS)
print(f"raton escalado: {nuevo[0]}x{nuevo[1]} sobre un lienzo de {ancho_lienzo}x{alto_lienzo}")

raton = Image.new("RGBA", (ancho_lienzo, alto_lienzo), (0, 0, 0, 0))
raton.alpha_composite(recorte, ((ancho_lienzo - nuevo[0]) // 2, 0))

lamina = Image.open(ROOT / "docs/original-ui/callouts_labels_overlay.png").convert("RGBA")
print(f"lamina: {lamina.size}")

lienzo = Image.new("RGBA", (ancho_lienzo, alto_lienzo), (58, 63, 71, 255))
lienzo.alpha_composite(raton)
lienzo.alpha_composite(lamina)

sal = ROOT / "docs/research/shots/callouts-con-raton.png"
lienzo.convert("RGB").save(sal)
print(f"escrito: {sal}")

# donde caen las anclas dentro del raton, para poder juzgarlo
destino = ROOT / "docs/research/shots/callouts-anclas.txt"
lineas = ["ancla (x,y en el lienzo) -> posicion dentro del raton (0..1)"]
izq = (ancho_lienzo - nuevo[0]) // 2
for ax, ay in [(439, 28), (439, 61), (439, 126), (353, 187), (357, 234), (357, 279),
               (361, 317), (361, 353), (380, 368), (380, 453), (401, 542), (401, 679),
               (455, 842), (455, 877), (455, 904)]:
    u = (ax - izq) / nuevo[0]
    v = (ay - 0) / alto_lienzo
    dentro = 0.0 <= u <= 1.0
    lineas.append(f"  ({ax:>3},{ay:>3}) -> u={u:.2f} v={v:.2f}"
                  + ("" if dentro else "   FUERA del raton"))
destino.write_text("\n".join(lineas))
print("\n".join(lineas))
