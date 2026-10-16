#!/usr/bin/env python3
"""Visual hull del R.A.T.9 con el rig CORRECTO: giro sobre el EJE LARGO.

POR QUE EXISTE ESTE FICHERO (el error que corrige)
---------------------------------------------------
La primera reconstruccion (3d/scripts/visual_hull.py) modelo el rig como un giro
de la camara alrededor del objeto sobre un EJE VERTICAL, tipo peana de producto. Con
eso el tallado daba IoU 0,79 y una malla que no se leia como un raton, y se concluyo
que el material no daba para mas.

Esa conclusion era FALSA, y el fallo estaba en el rig. Comprobado mirando los
fotogramas: en el fotograma 12 se ve LA BASE DEL RATON -- sensor, tornillos y
patines. Con la camara dando vueltas sobre un eje vertical y el objeto siempre
derecho, la cara inferior NO PUEDE verse nunca. Verla significa que lo que gira es
el OBJETO sobre su EJE LARGO: arriba -> lado -> abajo -> lado opuesto.

Es decir, el material SI cubre todo alrededor, incluida la base, que era justo lo
que el informe daba por irrecuperable. Con el rig bien puesto hay informacion de
sobra; lo que estaba mal era la geometria con la que se tallaba.

EL RIG, bien formulado
----------------------
  - eje largo del raton = X (asi la malla sale con el largo en X)
  - la camara NO se mueve; el objeto rueda sobre X
  - por tanto la direccion de vista de cada fotograma vive en el plano YZ:
        d_i = [0, cos(beta_i), sin(beta_i)],  beta_i = beta0 + signo * i * 15 grados
  - y los ejes de imagen son:
        r = [-1, 0, 0]                  (horizontal de la imagen = LARGO del raton)
        u = [0, -sin(beta), cos(beta)] (vertical de la imagen = seccion transversal)

Propiedad clave que hace que esto funcione: la coordenada HORIZONTAL de la imagen
depende SOLO de x. Por eso cada silueta acota el largo, y las 24 siluetas acotan la
seccion transversal desde 24 angulos. Sin el factor 1/cos(theta) que necesitaba el
rig vertical: aqui r y u son ortonormales y no hay compresion.

Uso:
    ~/3d-tools/sf3d-venv/bin/python tools/visual-hull-ejelargo.py --buscar
    ~/3d-tools/sf3d-venv/bin/python tools/visual-hull-ejelargo.py --n 160
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
HULL = RAIZ / "3d/hull"
MASCARAS = RAIZ / "3d/masks"
PASO = 2 * np.pi / 24          # 15 grados por fotograma
LARGO = 1.52                   # largo / ancho del raton, MEDIDO (340 px / 224 px)


def limpiar_apendice(m: np.ndarray, fino: float = 0.30,
                     grueso: float = 0.60) -> np.ndarray:
    mm = m.copy()
    an = mm.sum(axis=1)
    ys = np.flatnonzero(an > 0)
    if not len(ys):
        return mm
    wmax = float(an.max())
    for y in range(int(ys[0]), mm.shape[0]):
        a = an[y]
        if a == 0:
            continue
        if a < fino * wmax:
            mm[y, :] = False
        elif a > grueso * wmax:
            break
    return mm


def cargar(limpiar: bool = True) -> dict:
    meta = json.loads((HULL / "masks.json").read_text())
    masc = {}
    for clave, ruta in meta.items():
        s, i = clave.split(":")
        p = MASCARAS / Path(ruta).name
        if not p.is_file():
            p = Path(ruta)
        m = np.load(p)
        masc[(int(s), int(i))] = limpiar_apendice(m) if limpiar else m
    return masc


def ejes(beta: float):
    """Ejes de imagen del rig de EJE LARGO.

    OJO con cual es cual, que aqui me equivoque la primera vez: los fotogramas son
    VERTICALES (275x349, 280x341) y el raton va con el LARGO en la VERTICAL de la
    imagen. Por tanto:
        u (vertical de la imagen) = el LARGO del raton = X
        r (horizontal de la imagen) = la seccion transversal, dentro del plano YZ
    Con los dos cambiados el IoU se hundia a 0,15: el tallado pedia que el raton
    cupiera en la silueta girado 90 grados, y no cabe.
    """
    d = np.array([0.0, np.cos(beta), np.sin(beta)])   # direccion de vista
    u = np.array([-1.0, 0.0, 0.0])                     # vertical imagen = LARGO
    r = np.array([0.0, -np.sin(beta), np.cos(beta)])  # horizontal imagen = seccion
    return d, r, u


def rejilla(N: int):
    """Rejilla NO cubica: el raton no cabe en un cubo.

    Medido sobre las 48 mascaras: la silueta mide ~340 px de largo (que es la
    VERTICAL de la imagen, invariante al girar) por ~224 px de ancho. O sea que el
    raton mide 340/224 = 1,52 veces mas de largo que de ancho. Con una rejilla
    cubica de lado 1,1 (que era lo que habia) el objeto NO CABE: 1,1 x 224 = 246 px
    de largo disponible contra 340 px que mide. El tallado no podia converger, y ese
    era el fallo de la version anterior de este mismo fichero.
    """
    gx = np.linspace(-LARGO / 2, LARGO / 2, N)      # eje X = largo del raton
    g = np.linspace(-0.5, 0.5, N)
    Z, Y, X = np.meshgrid(g, g, gx, indexing="ij")
    pts = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1)
    return pts, pts - pts.mean(axis=0)


def tallar(masc: dict, rig: dict, N: int):
    pts, pts_c = rejilla(N)
    S = float(max(m.sum(axis=1).max() for m in masc.values()))
    vivo = np.ones(pts.shape[0], bool)
    for (serie, i), m in masc.items():
        beta = rig["beta0"][serie] + rig["signo"] * i * PASO
        _d, r, u = ejes(beta)
        idx = np.flatnonzero(vivo)
        ur = pts_c[idx] @ r
        uu = pts_c[idx] @ u
        ys, xs = np.where(m)
        cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
        px = (ur * S + cx).astype(int)
        py = (-uu * S + cy).astype(int)
        ok = (px >= 0) & (px < m.shape[1]) & (py >= 0) & (py < m.shape[0])
        dentro = np.zeros(idx.size, bool)
        dentro[ok] = m[py[ok], px[ok]]
        nuevo = np.zeros_like(vivo)
        nuevo[idx[dentro]] = True
        vivo &= nuevo
        if vivo.sum() == 0:
            break
    return vivo, S


def puntuar(masc: dict, rig: dict, vivo, N: int) -> float:
    pts, pts_c = rejilla(N)
    S = float(max(m.sum(axis=1).max() for m in masc.values()))
    ious = []
    p = pts_c[np.flatnonzero(vivo)]
    for (serie, i), m in masc.items():
        beta = rig["beta0"][serie] + rig["signo"] * i * PASO
        _d, r, u = ejes(beta)
        ur = p @ r
        uu = p @ u
        ys, xs = np.where(m)
        cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
        H, W = m.shape
        proj = np.zeros_like(m)
        px = np.clip((ur * S + cx).astype(int), 0, W - 1)
        py = np.clip((-uu * S + cy).astype(int), 0, H - 1)
        proj[py, px] = True
        inter = (proj & m).sum()
        union = (proj | m).sum()
        ious.append(inter / union if union else 0.0)
    return float(np.mean(ious))


def buscar(masc: dict, N: int = 64) -> dict:
    """Busca signo de giro y fase beta0 por serie, con el rig de eje largo."""
    mejor = {}
    serie_m = {1: {k: v for k, v in masc.items() if k[0] == 1},
               2: {k: v for k, v in masc.items() if k[0] == 2}}
    for serie in (1, 2):
        b = None
        for signo in (1, -1):
            for b0 in np.radians(np.arange(0, 15, 2.5)):
                rig = {"beta0": {serie: float(b0)}, "signo": signo}
                vivo, _ = tallar(serie_m[serie], rig, N)
                if vivo.sum() < 200:
                    continue
                s = puntuar(serie_m[serie], rig, vivo, N)
                if b is None or s > b[0]:
                    b = (s, signo, float(b0), int(vivo.sum()))
        mejor[serie] = b
        print(f"  serie {serie}: IoU={b[0]:.3f}  signo={b[1]:+d}  "
              f"beta0={np.degrees(b[2]):.1f}deg  voxeles={b[3]:,}")
    return {"signo": mejor[1][1], "beta0": {1: mejor[1][2], 2: mejor[2][2]},
            "iou_serie": {1: mejor[1][0], 2: mejor[2][0]}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=160)
    ap.add_argument("--buscar", action="store_true",
                    help="busca signo y fase del giro antes de tallar")
    ap.add_argument("--glb", default=str(HULL / "rat9_hull_ejelargo.glb"))
    a = ap.parse_args()

    masc = cargar(True)
    print(f"mascaras: {len(masc)} (apendice limpiado)")

    rig = None
    pr = HULL / "rig_ejelargo.json"
    if a.buscar or not pr.is_file():
        print("buscando el rig (signo del giro y fase):")
        rig = buscar(masc)
        pr.write_text(json.dumps(rig, indent=2))
        print(f"  guardado {pr}")
    else:
        rig = json.loads(pr.read_text())
        rig["beta0"] = {int(k): v for k, v in rig["beta0"].items()}
        print(f"rig leido: {rig}")

    vivo, _S = tallar(masc, rig, a.n)
    print(f"N={a.n}: {vivo.sum():,} voxeles")
    iou = puntuar(masc, rig, vivo, a.n)
    print(f"COMBINADO (rig de eje largo): IoU = {iou:.3f}")

    vol = vivo.reshape(a.n, a.n, a.n).astype(np.float32)
    from skimage import measure
    import trimesh
    import trimesh.smoothing

    vi, caras, _n, _v = measure.marching_cubes(np.pad(vol, 1), level=0.5)
    vi = vi - 1.0
    # el grid es anisotropo: X va a [-LARGO/2, LARGO/2] y Y,Z a [-0.5, 0.5]
    vx = -LARGO / 2 + (vi[:, 2] / (a.n - 1)) * LARGO
    vy = -0.5 + (vi[:, 1] / (a.n - 1)) * 1.0
    vz = -0.5 + (vi[:, 0] / (a.n - 1)) * 1.0
    malla = trimesh.Trimesh(vertices=np.stack([vx, vy, vz], axis=1),
                             faces=caras, process=True)
    trimesh.smoothing.filter_taubin(malla, lamb=0.55, nu=-0.55, iterations=14)
    malla.export(a.glb)
    e = malla.extents
    print(f"malla: {len(malla.vertices):,} verts, {len(malla.faces):,} caras")
    print(f"  dimensiones X(largo)/Y/Z = {np.round(e, 3)}")
    print(f"  largo : ancho : alto = {e[0] / e[2]:.2f} : {e[1] / e[2]:.2f} : 1")
    (HULL / "params_ejelargo.json").write_text(json.dumps(
        dict(n=a.n, rig=rig, iou=iou, verts=len(malla.vertices),
             caras=len(malla.faces), extents=[float(x) for x in e]), indent=2))
    print(f"escrito: {a.glb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
