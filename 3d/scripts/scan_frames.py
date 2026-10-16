#!/usr/bin/env python3
"""Escanea los 48 fotogramas de rotacion del R.A.T.9, recorta con rembg
y puntua la silueta para elegir los mejores candidatos a image-to-3D.

Criterios (medidos, no esteticos):
  - aspecto bbox (w/h): quiero ~0.9-1.3 (un raton real es ~1.1-1.2 largo/alto)
  - 1 sola componente alpha grande (sin fragmentos sueltos)
  - area de silueta grande (mas px de objeto = mas resolucion real)

Salida: JSON con puntuaciones ordenadas + PNGs del recorte del top-8.
"""
import glob
import json
import os
import sys

import numpy as np
from PIL import Image
from rembg import remove, new_session

SRC = "~/rat9-config/docs/original-ui/extracted-from-installer"
OUT = "~/.hermes/cache/scratch/rat9/cutouts"
os.makedirs(OUT, exist_ok=True)

session = new_session("u2net", providers=["CPUExecutionProvider"])
frames = sorted(glob.glob(os.path.join(SRC, "*275x349.png"))) + sorted(glob.glob(os.path.join(SRC, "*280x341.png")))

rows = []
for i, f in enumerate(frames):
    img = Image.open(f).convert("RGBA")
    cut = remove(img, session=session)
    a = np.asarray(cut)[..., 3]
    ys, xs = np.where(a > 128)
    if len(xs) < 50:
        continue
    w, h = xs.max() - xs.min(), ys.max() - ys.min()
    # componentes alpha grandes
    from scipy import ndimage
    mask = a > 128
    lab, n = ndimage.label(mask)
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    big = (sizes > 200).sum()
    area_frac = mask.mean()
    rows.append(dict(idx=i, w=int(w), h=int(h), aspect=round(w / h, 3), comps=int(big),
                     area=round(float(area_frac), 3), file=os.path.basename(f)))

rows.sort(key=lambda r: -(min(r["aspect"], 1.25) * r["area"] * (1 if r["comps"] == 1 else 0.3)))
json.dump(rows, open(os.path.join(OUT, "scan.json"), "w"), indent=1)
for r in rows[:8]:
    print(r)
top = rows[:8]
for r in top:
    img = Image.open(os.path.join(SRC, r["file"])).convert("RGBA")
    remove(img, session=session).save(os.path.join(OUT, f"cut_{r['idx']:02d}.png"))
print("TOP:", [r["idx"] for r in top])