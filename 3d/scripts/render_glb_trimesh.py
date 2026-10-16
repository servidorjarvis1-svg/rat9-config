#!/usr/bin/env python3
"""V2: carga GLB con trimesh aplicando transforms de escena y renderiza 4 vistas.
    python render_glb_trimesh.py <glb> <dir_salida>
"""
import os
import sys

import numpy as np
import trimesh
from PIL import Image, ImageDraw

glb, outdir = sys.argv[1], sys.argv[2]
os.makedirs(outdir, exist_ok=True)
scene = trimesh.load(glb)
m = scene.dump(concatenate=True)
pos = np.asarray(m.vertices, dtype=float)
idx = np.asarray(m.faces)
uv = np.asarray (m.visual.uv) if hasattr(m.visual, "uv") and m.visual.uv is not None else None
tex = None
if uv is not None and hasattr(m.visual, "material"):
    try:
        img = m.visual.material.baseColorTexture
        tex = np.asarray(img.convert("RGB").resize((1024, 1024)))
    except Exception:
        tex = None
print("verts", len(pos), "faces", len(idx), "uv", uv is not None, "tex", tex is not None)
print("dims:", np.round(pos.max(0) - pos.min(0), 4))

W = 560
def render(az_deg, out, elev_deg=12):
    az, el = np.radians(az_deg), np.radians(elev_deg)
    c, s = np.cos(az), np.sin(az)
    Rz = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])
    ce, se = np.cos(el), np.sin(el)
    Rx = np.array([[1, 0, 0], [0, ce, -se], [0, se, ce]])
    P = (Rx @ Rz @ pos.T).T
    lo, hi = P.min(0), P.max(0)
    scale = 0.85 * W / (hi - lo).max()
    X = (P[:, 0] - (lo[0] + hi[0]) / 2) * scale + W / 2
    Y = W / 2 - ((P[:, 1] - (lo[1] + hi[1]) / 2) * scale)
    Z = P[:, 2]
    img = Image.new("RGB", (W, W), (200, 200, 205))
    dr = ImageDraw.Draw(img)
    tris = idx
    zc = Z[tris].mean(1)
    order = np.argsort(zc)
    n = np.cross(P[tris[:, 1]] - P[tris[:, 0]], P[tris[:, 2]] - P[tris[:, 0]])
    nn = np.linalg.norm(n, axis=1) + 1e-12
    n_ = n / nn[:, None]
    cam_dir = np.array([np.sin(az) * np.cos(el), np.sin(el), np.cos(az) * np.cos(el)])
    light = (np.array([-0.35, 0.5, 0.79]) + cam_dir) / 2
    lam = np.clip(np.abs(n_ @ light), 0.25, 1.0)
    if uv is not None and tex is not None:
        uvc = np.clip((uv[tris].mean(1) * 1024), 0, 1023).astype(int)
        col = tex[uvc[:, 1], uvc[:, 0]]
    else:
        col = np.full((len(tris), 3), 165)
    coln = (col * lam[:, None]).clip(0, 255).astype(np.uint8)
    for t in order:
        a, b, c3 = tris[t]
        dr.polygon([(X[a], Y[a]), (X[b], Y[b]), (X[c3], Y[c3])], fill=tuple(coln[t]))
    img.save(out)

for i, az in enumerate([0, 90, 180, 270]):
    render(az, os.path.join(outdir, f"v_{i}.png"))
print("OK 4 vistas en", outdir)