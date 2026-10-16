#!/usr/bin/env python3
"""Recorta el elemento fino superior (cable/mecanismo) de un cutout RGBA:
cero alpha en filas superiores cuya anchura sea <30% de la maxima hasta que
la anchura supere 60%. Luego 4x upscale (remacri) no necesario: SF3D recibe
el cutout y hace resize_foreground. Saca el cutout limpio a un PNG.
"""
import sys

import numpy as np
from PIL import Image

src, dst = sys.argv[1], sys.argv[2]
img = Image.open(src).convert("RGBA")
a = np.asarray(img).copy()
mask = a[..., 3] > 128
W = a.shape[1]
widths = mask.sum(axis=1)
ys, xs = np.where(mask)
y0 = ys.min()
wmax = widths.max()
cut = False
for y in range(y0, a.shape[0]):
    w = widths[y]
    if w < 0.3 * wmax:
        pass
    elif w > 0.6 * wmax:
        break
    a[y, :, 3] = 0
    a[y, :, :3] = 0
    cut = True
print("neck cortado:", cut, "desde y=", y0)
ys2, xs2 = np.where(a[..., 3] > 128)
if len(xs2):
    pad = 8
    box = (max(xs2.min() - pad, 0), max(ys2.min() - pad, 0),
           min(xs2.max() + pad, a.shape[1]), min(ys2.max() + pad, a.shape[0]))
    img2 = Image.fromarray(a).crop(box)
else:
    img2 = Image.fromarray(a)
w2, h2 = img2.size
print("bbox post-cut:", w2, "x", h2, "aspect 1:", round(w2 / h2, 3), "aspect 2:", round(h2 / w2, 3))
img2.save(dst)