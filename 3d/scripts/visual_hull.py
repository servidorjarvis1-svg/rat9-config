#!/usr/bin/env python3
"""Visual hull del R.A.T.9 desde los 2 giros de 24 fotogramas, SIN SfM.

Supuestos mesurados del rig (orthografico):
  - giro del objeto: 24 pasos = 15 deg/frame, offset phi0 desconocido (se busca)
  - camara a altura fija por serie: elevacion theta desconocida (se busca)
  - escala global: la vista mas ancha de todas mapea al diametro 1.0 del monde

Carve + score IoU (silueta reproyectada vs silueta real) y malla final
marching-cubes -> GLB. Tambien guarda el mejor plano de corte como npy.

Uso: sf3d-venv/bin/python visual_hull.py [N=112]
"""
import glob
import json
import os
import sys

import numpy as np
from PIL import Image
from rembg import remove, new_session

SRC = "~/rat9-config/docs/original-ui/extracted-from-installer"
OUT = "~/.hermes/cache/scratch/rat9/hull"
os.makedirs(OUT, exist_ok=True)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 112

MASKS = {}
if os.path.exists(os.path.join(OUT, "masks.json")):
    META = json.load(open(os.path.join(OUT, "masks.json")))
    MASKS = {int(k): (np.load(v),) for k, v in META.items()}
if not MASKS:
    session = new_session("u2net", providers=["CPUExecutionProvider"])
    MASKS = {}
    META = {}
    idx = 0
    for serie, pat in [(1, "275x349"), (2, "280x341")]:
        fs = sorted(f for f in os.listdir(SRC) if pat in f)
        for f in fs:
            img = Image.open(os.path.join(SRC, f)).convert("RGBA")
            cut = remove(img, session=session)
            m = np.asarray(cut)[..., 3] > 128
            MASKS[(serie, idx)] = m
            p = os.path.join(OUT, f"mask_s{serie}_{idx:02d}.npy")
            np.save(p, m)
            META[f"{serie}:{idx}"] = p
            idx += 1
    json.dump(META, open(os.path.join(OUT, "masks.json"), "w"))

# escala global: anchura max de silueta en px <-> diametro mundo 1.0
all_w = [m.sum(axis=1).max() for m in MASKS.values()]
all_h = [m.sum(axis=0).max() for m in MASKS.values()]
S = float(max(all_w))  # px por unidad de mundo


def axes(az, th):
    d = np.array([np.cos(az) * np.cos(th), np.sin(az) * np.cos(th), np.sin(th)])
    r = np.cross([0, 0, 1.0], d); r /= np.linalg.norm(r)
    u = np.cross(d, r)
    return d, r, u


def project(pts, az, th):
    d, r, u = axes(az, th)
    # centro: bbox de proyecciones relativo al centroide del grid
    ur = pts @ r; uu = pts @ u; ud = pts @ d
    return ur, uu, ud


def carve(masks, theta, phi0, vol=None, N=N):
    # voxels del grid [-0.55, 0.55]
    g = np.linspace(-0.55, 0.55, N)
    Z, Y, X = np.meshgrid(g, g, g, indexing="ij")
    pts = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1)
    center = pts.mean(axis=0)
    pts_c = pts - center
    if vol is None:
        vol = np.ones(N * N * N, bool)
    alive = vol.copy()
    for (serie, i), m in masks.items():
        az = phi0[serie] + i * (2 * np.pi / 24)
        ur, uu, _ = project(pts_c[alive], az, theta[serie])
        # mapa a px: silueta centro bbox -> origen mundo
        ys, xs = np.where(m)
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        px = (ur * S / np.cos(theta[serie]) + cx).astype(int)
        py = (-uu * S / np.cos(theta[serie]) + cy).astype(int)
        ok = (px >= 0) & (px < m.shape[1]) & (py >= 0) & (py < m.shape[0])
        keep = np.zeros_like(alive[alive])
        keep[ok] = m[py[ok], px[ok]]
        idxs = np.where(alive)[0]
        newalive = np.zeros_like(alive)
        newalive[idxs[keep]] = True
        alive = alive & newalive
        if alive.sum() == 0:
            break
    return alive


def score(masks, theta, phi0, alive, N=N):
    # IoU de silueta reproyectada (del volumen) vs silueta real
    g = np.linspace(-0.55, 0.55, N)
    Z, Y, X = np.meshgrid(g, g, g, indexing="ij")
    pts = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1)
    center = pts.mean(axis=0)
    pts_c = pts[alive] - center
    ious = []
    for (serie, i), m in masks.items():
        az = phi0[serie] + i * (2 * np.pi / 24)
        ur, uu, _ = project(pts_c, az, theta[serie])
        ys, xs = np.where(m)
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        H, W = m.shape
        proj = np.zeros_like(m)
        px = np.clip((ur * S / np.cos(theta[serie]) + cx).astype(int), 0, W - 1)
        py = np.clip((-uu * S / np.cos(theta[serie]) + cy).astype(int), 0, H - 1)
        proj[py, px] = True
        inter = (proj & m).sum(); union = (proj | m).sum()
        ious.append(inter / union if union else 0)
    return float(np.mean(ious))


serie_masks = {1: {k: m for k, m in MASKS.items() if k[0] == 1},
               2: {k: m for k, m in MASKS.items() if k[0] == 2}}

# busqueda por serie: theta x phi0 (mod 15deg)
results = {}
thetas = np.radians([10, 15, 20, 25, 30, 35, 40])
phis = np.radians(np.arange(0, 15, 3))
for serie in (1, 2):
    best = None
    for th in thetas:
        for ph in phis:
            alive = carve(serie_masks[serie], {serie: th}, {serie: ph})
            if alive.sum() < 1000:
                continue
            s = score(serie_masks[serie], {serie: th}, {serie: ph}, alive)
            if best is None or s > best[0]:
                best = (s, float(th), float(ph), alive)
    results[serie] = best
    print(f"serie {serie}: best IoU={best[0]:.3f} theta={np.degrees(best[1]):.0f}deg phi0={np.degrees(best[2]):.0f}deg voxels={best[3].sum()}")

# carve combinado con los mejores parametros
th = {1: results[1][1], 2: results[2][1]}
ph = {1: results[1][2], 2: results[2][2]}
alive = carve(MASKS, th, ph)
# 2 pasadas mas de refinado
for _ in range(2):
    alive = carve(MASKS, th, ph, vol=alive)
iou = score(MASKS, th, ph, alive)
print(f"COMBINADO: IoU medio={iou:.3f} voxels={alive.sum()}")
np.save(os.path.join(OUT, "volume.npy"), alive.reshape(N, N, N))
json.dump(dict(theta1=np.degrees(th[1]), theta2=np.degrees(th[2]), phi0_1=np.degrees(ph[1]),
               phi0_2=np.degrees(ph[2]), iou=iou, N=N), open(os.path.join(OUT, "params.json"), "w"))
print("guardado volume.npy")