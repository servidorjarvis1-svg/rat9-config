#!/usr/bin/env python3
"""Reconstruye el R.A.T.9 por siluetas (visual hull) desde los 48 fotogramas.

De donde sale el material: docs/original-ui/extracted-from-installer/ tiene DOS
rotaciones completas de 24 fotogramas del raton real (series de 275x349 y de
280x341), de un giro de 360 grados con la camara fija. Con el rig conocido (24
pasos = 15 grados por fotograma, elevacion ~10 grados) NO hace falta SfM: se puede
tallar el volumen directamente, que es lo que hace esto.

Por que asi y no con un image-to-3D: se probo. Stable Fast 3D corre en 18 s, pero
con una vista oblicua superior de 280 px de un objeto oscuro y brillante la forma
que saca es malisima (proporciones invertidas). El cuello de botella no es el
motor, es la ENTRADA. El hull, en cambio, extrae geometria REAL del material
(fue el unico metodo que lo consiguio) y IoU de silueta 0,71-0,81.

Lo que este metodo NO puede dar, y hay que decirlo: la base del raton (ninguna
camara la ve), las concavidades (el hull las rellena) y textura nitida (la fuente
son 280 px).

Uso:
    ~/3d-tools/sf3d-venv/bin/python tools/visual-hull.py            # N=160
    ~/3d-tools/sf3d-venv/bin/python tools/visual-hull.py --n 192
    ~/3d-tools/sf3d-venv/bin/python tools/visual-hull.py --sin-limpiar
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
HULL = RAIZ / "3d/hull"
MASCARAS = RAIZ / "3d/masks"
SCRIPTS = RAIZ / "3d/scripts"

# Rig medido por busqueda en rejilla (3d/hull/params.json): mismo valor para las
# dos series, que es lo que tiene sentido si son el mismo aparato con la misma
# camara. Si no hay params.json se puede buscar otra vez con --buscar.
THETA_DEF = {1: 10.0, 2: 10.0}
PHI0_DEF = {1: 3.0, 2: 12.0}


def limpiar_apendice(m: np.ndarray, fino: float = 0.30,
                     grueso: float = 0.60) -> np.ndarray:
    """Corta el apendice fino superior (el "cable") de la silueta.

    En las 48 vistas hay un elemento delgado que GIRA CON EL OBJETO pegado
    encima (no es un adorno de la interfaz). Si no se quita, todas las siluetas
    lo incluyen y el hull hereda un pincho en la parte de arriba.

    Como: desde la primera fila con contenido hacia abajo, se vacian las filas
    cuya anchura no llega al 30% de la maxima, y se para en cuanto una fila pasa
    del 60%, que ya es el cuerpo.
    """
    mm = m.copy()
    an = mm.sum(axis=1)
    ys = np.flatnonzero(an > 0)
    if not len(ys):
        return mm
    wmax = float(an.max())
    if wmax <= 0:
        return mm
    for y in range(int(ys[0]), mm.shape[0]):
        a = an[y]
        if a == 0:
            continue
        if a < fino * wmax:
            mm[y, :] = False
        elif a > grueso * wmax:
            break
    return mm


def cargar_mascaras(limpiar: bool) -> tuple[dict, dict]:
    meta = json.loads((HULL / "masks.json").read_text())
    masc = {}
    for clave, ruta in meta.items():
        s, i = clave.split(":")
        p = MASCARAS / Path(ruta).name          # las copias del repo
        if not p.is_file():
            p = Path(ruta)                       # o las originales del scratch
        m = np.load(p)
        masc[(int(s), int(i))] = limpiar_apendice(m) if limpiar else m
    return masc, meta


def ejes(az: float, th: float):
    d = np.array([np.cos(az) * np.cos(th), np.sin(az) * np.cos(th), np.sin(th)])
    r = np.cross([0, 0, 1.0], d)
    r /= np.linalg.norm(r)
    u = np.cross(d, r)
    return d, r, u


def tallar(masc: dict, th: dict, ph: dict, N: int, vol=None):
    """Deja vivo solo lo que cae dentro de las 48 siluetas: el visual hull."""
    g = np.linspace(-0.55, 0.55, N)
    Z, Y, X = np.meshgrid(g, g, g, indexing="ij")
    pts = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1)
    centro = pts.mean(axis=0)
    pts_c = pts - centro
    S = float(max(m.sum(axis=1).max() for m in masc.values()))
    vivo = np.ones(N * N * N, bool) if vol is None else vol.copy()
    for (serie, i), m in masc.items():
        az = np.radians(ph[serie]) + i * (2 * np.pi / 24)
        th_r = np.radians(th[serie])
        _, r, u = ejes(az, th_r)
        idx_vivos = np.flatnonzero(vivo)
        ur = pts_c[idx_vivos] @ r
        uu = pts_c[idx_vivos] @ u
        ys, xs = np.where(m)
        cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
        px = (ur * S / np.cos(th_r) + cx).astype(int)
        py = (-uu * S / np.cos(th_r) + cy).astype(int)
        ok = (px >= 0) & (px < m.shape[1]) & (py >= 0) & (py < m.shape[0])
        dentro = np.zeros(idx_vivos.size, bool)
        dentro[ok] = m[py[ok], px[ok]]
        nuevo = np.zeros_like(vivo)
        nuevo[idx_vivos[dentro]] = True
        vivo &= nuevo
        if vivo.sum() == 0:
            break
    return vivo, S


def puntuar(masc: dict, th: dict, ph: dict, vivo, N: int) -> float:
    g = np.linspace(-0.55, 0.55, N)
    Z, Y, X = np.meshgrid(g, g, g, indexing="ij")
    pts = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1)
    pts_c = pts - pts.mean(axis=0)
    S = float(max(m.sum(axis=1).max() for m in masc.values()))
    ious = []
    for (serie, i), m in masc.items():
        az = np.radians(ph[serie]) + i * (2 * np.pi / 24)
        th_r = np.radians(th[serie])
        _, r, u = ejes(az, th_r)
        p = pts_c[np.flatnonzero(vivo)]
        ur = p @ r
        uu = p @ u
        ys, xs = np.where(m)
        cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
        H, W = m.shape
        proj = np.zeros_like(m)
        px = np.clip((ur * S / np.cos(th_r) + cx).astype(int), 0, W - 1)
        py = np.clip((-uu * S / np.cos(th_r) + cy).astype(int), 0, H - 1)
        proj[py, px] = True
        inter = (proj & m).sum()
        union = (proj | m).sum()
        ious.append(inter / union if union else 0.0)
    return float(np.mean(ious))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=160, help="resolucion del voxel grid")
    ap.add_argument("--sin-limpiar", action="store_true",
                    help="no cortar el apendice superior (para comparar)")
    ap.add_argument("--refinar", type=int, default=3,
                    help="pasadas extra de tallado sobre el volumen ya tallado")
    ap.add_argument("--glb", default=str(HULL / "rat9_hull_limpio.glb"))
    a = ap.parse_args()

    if not (HULL / "masks.json").is_file():
        print(f"falta {HULL/'masks.json'}; corre antes visual_hull.py")
        return 1

    limpiar = not a.sin_limpiar
    masc, _meta = cargar_mascaras(limpiar)
    print(f"mascaras: {len(masc)}  limpieza del apendice: {'SI' if limpiar else 'NO'}")
    if limpiar:
        antes = sum(int(m.sum()) for m in masc.values())
        # recomputar sobre las ya limpias para reportar cuanto se ha quitado
        masc_orig, _ = cargar_mascaras(False)
        despues_orig = sum(int(m.sum()) for m in masc_orig.values())
        print(f"  pixeles de silueta: {despues_orig} -> {antes} "
              f"({100 * (1 - antes / max(1, despues_orig)):.1f}% recortado)")

    # parametros del rig
    pp = HULL / "params.json"
    th, ph = dict(THETA_DEF), dict(PHI0_DEF)
    if pp.is_file():
        d = json.loads(pp.read_text())
        th = {1: d.get("theta1", 10.0), 2: d.get("theta2", 10.0)}
        ph = {1: d.get("phi0_1", 3.0), 2: d.get("phi0_2", 12.0)}
        print(f"rig leido de params.json: theta={th} phi0={ph}")

    vivo, _S = tallar(masc, th, ph, a.n)
    print(f"N={a.n}: voxeles vivos tras el primer tallado: {vivo.sum():,}")
    for k in range(a.refinar):
        vivo, _ = tallar(masc, th, ph, a.n, vol=vivo)
        print(f"  refinado {k + 1}/{a.refinar}: {vivo.sum():,} voxeles")
    iou = puntuar(masc, th, ph, vivo, a.n)
    print(f"COMBINADO: IoU medio de silueta = {iou:.3f}")

    vol = vivo.reshape(a.n, a.n, a.n).astype(np.float32)
    np.save(HULL / "volume_limpio.npy", vol)

    # ── malla ────────────────────────────────────────────────────────────────
    from skimage import measure
    import trimesh
    import trimesh.smoothing

    pad = np.pad(vol, 1)
    vi, caras, _n, _v = measure.marching_cubes(pad, level=0.5)
    vi = vi - 1.0
    g0, g1 = -0.55, 0.55
    # ojo con el orden de ejes: el grid se construyo con indexing="ij" y luego
    # se apilo (X, Y, Z) = (g[k], g[j], g[i]); marching_cubes devuelve (i, j, k)
    vx = g0 + (vi[:, 2] / (a.n - 1)) * (g1 - g0)
    vy = g0 + (vi[:, 1] / (a.n - 1)) * (g1 - g0)
    vz = g0 + (vi[:, 0] / (a.n - 1)) * (g1 - g0)
    malla = trimesh.Trimesh(vertices=np.stack([vx, vy, vz], axis=1),
                             faces=caras, process=True)
    trimesh.smoothing.filter_taubin(malla, lamb=0.55, nu=-0.55, iterations=14)
    malla.export(a.glb)
    print(f"malla: {len(malla.vertices):,} vertices, {len(malla.faces):,} caras")
    print(f"  dimensiones: {np.round(malla.extents, 2)}  proporciones "
          f"L:A:H = {malla.extents[0] / malla.extents[2]:.2f}:"
          f"{malla.extents[1] / malla.extents[2]:.2f}:1")
    (HULL / "params_limpio.json").write_text(json.dumps(
        dict(n=a.n, theta=th, phi0=ph, iou=iou, limpiado=a.sin_limpiar is False,
             glb=a.glb, vertices=len(malla.vertices), caras=len(malla.faces)),
        indent=2))
    print(f"escrito: {a.glb}")

    # ── vistas para MIRARLO ───────────────────────────────────────────────────
    sal = HULL / "vistas_limpio"
    sal.mkdir(exist_ok=True)
    subprocess.run([sys.executable, str(SCRIPTS / "render_glb_trimesh.py"),
                    a.glb, str(sal)], check=False)
    print(f"vistas en {sal}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
