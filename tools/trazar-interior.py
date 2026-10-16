#!/usr/bin/env python3
"""Mide los detalles INTERNOS del ratón en el render y los deja en interior.json.

Por qué existe: tools/trazar-silueta.py mide el CONTORNO exterior y el generador
ya lo traza sobre esa medida, pero el interior (costuras de los botones, rueda y
su ranura, panel lateral) sigue saliendo de constantes escritas a mano. El
resultado era un contorno clavado al render y un interior desplazado. Esto mide
el interior sobre la misma imagen y lo entrega en las mismas unidades, para que
el esquema se trace sobre la imagen también por dentro.

Cómo mide (todo con numpy, umbrales sacados de la imagen, no a ojo):
  - Costura central: en el morro la separación de los dos botones son dos líneas
    de contraste vertical (borde interior de cada tapa). Se toma el pico de
    |d/dx| por fila en una ventana alrededor del eje y se hace la mediana.
  - Rueda: la zona de estrías del centro delantero. El criterio no es la
    luminancia (la rueda es casi tan clara como el casco, 0.27-0.31 frente a
    0.30), sino la OSCILACIÓN vertical: |d/dy| medio por fila se dispara donde
    hay estrías y se apaga en el casco liso.
  - Ranura: las dos guías brillantes (bordes biselados del alojamiento, x 381-389
    y 443-451) acotan el rectángulo; abajo, el pozo oscuro termina por sí solo
    contra la carcasa; arriba, la banda brillante (el labio de la Ranura) se
    mide aparte porque es la única pieza CLARA de la zona.
  - Panel lateral: para cada fila se busca el "valle" oscuro (luminancia suavizada
    < 0.20) con mayor área dentro de la banda del flanco; su centro es el borde
    interior del panel. Es robusto a los mandos y a la bisagra: los picos de
    brillo aislados no crean valles.

Unidades: FRACCIONES de la caja de registro (0..1 por eje), la misma convención
que silueta.json. La caja NO es la silueta caja_px (0,119,699,964) sino
capa.json/bbox_imagen (10,124,685,954): es la caja que la CAPA usa para
transformar esquema->imagen, y con ella el mapeo normalizado->píxel es exacto
(x = 10 + u*685). Normalizar contra la caja de la silueta introduciría un
estiramiento del 2% heredado del glow que la silueta arrastró al medir.

    python3 tools/trazar-interior.py            # escribe rat9/ui/interior.json
    python3 tools/trazar-interior.py --debug    # marcas de color sobre el render
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "rat9" / "ui" / "assets" / "raton-original.png"
CAPA = ROOT / "rat9" / "ui" / "capa.json"
SILUETA = ROOT / "rat9" / "ui" / "silueta.json"
OUT = ROOT / "rat9" / "ui" / "interior.json"
SHOTS = ROOT / "docs" / "research" / "shots"

# ── constantes de medida ─────────────────────────────────────────────────────
# Ventana del morro donde se miden las dos líneas de la costura (u = fracción de
# la caja): el borde interior de la tapa izquierda cae hacia x=370 (u=.526) y el
# de la derecha hacia x=461 (u=.658). Una ventana GENEROSA y |d/dx| pico por
# fila vale más que fijar la posición de antemano.
COSTURA_WIN_IZQ = (0.455, 0.585)
COSTURA_WIN_DER = (0.60, 0.72)
DER_BAJO = (0.235, 0.40)     # tramo bajo donde la ranura derecha sigue visible
PICO_MIN = 0.10              # |d/dx| mínimo para dar la fila por buena

# Zona de búsqueda de la rueda: mitad delantera central. Amplia a propósito;
# la que acota de verdad es la energía de estrías y las guías.
RUEDA_V = (0.045, 0.27)
RUEDA_U = (0.50, 0.68)
OSCURA_MAX = 0.36            # luminancia media de fila para contar como rueda
# La rueda estría |d/dy| por fila; el casco liso se queda en 0.01-0.03. El
# umbral se ancla a una fracción del máximo de la ventana (ver _rueda).
ESTRIA_FRAC = 0.30
ESTRIA_MIN = 0.025

FLANCO_V = (0.265, 0.78)     # filas donde se busca el borde del panel: el panel
                             # existe en la imagen de ~y380 a ~y860; fuera de ese
                             # tramo el buscador encuentra valles falsos (el
                             # brillo del talón) y los omitimos por diseño
FLANCO_WIN = (118, 285)      # ventana absoluta donde puede caer el valle oscuro
VALLE_LUM = 0.20             # un valle es luminancia suavizada por debajo
VALLE_AREA = 0.9             # área mínima (px*0..1) para no tragarse ruido
INSET_LUM = 0.30             # a la IZQUIERDA del valle del panel hay panel
                             # (oscuro); a la izquierda del valle del bisel del
                             # casco hay un brillo alto. Discrimina los dos.
PASO_FILAS = 9

def suavizar(v: np.ndarray, n: int) -> np.ndarray:
    """Media móvil con reflejo en los bordes."""
    if len(v) < 3:
        return v
    k = np.ones(n) / n
    return np.convolve(np.pad(v, n // 2, mode="edge"), k, mode="same")[n // 2:][: len(v)]


def caja_registro() -> tuple[int, int, int, int]:
    """Caja (x, y, w, h) del ratón en la imagen, para normalizar.

    capa.json es la fuente: sus números los midió tools/encajar-capa.py sobre la
    MISMA imagen y son los que la capa usa para superponerse. Si no existe,
    caemos a la caja que silueta.json dejó anotada (2% de error de registro,
    tolerable pero no ideal)."""
    if CAPA.is_file():
        cap = json.loads(CAPA.read_text())
        bx, by, bw, bh = (float(v) for v in cap["bbox_imagen"])
        return int(round(bx)), int(round(by)), int(round(bw)), int(round(bh))
    if SILUETA.is_file():
        sil = json.loads(SILUETA.read_text())
        x, y, w, h = (int(v) for v in sil["caja_px"])
        return x, y, w, h
    raise SystemExit("ni capa.json ni silueta.json: no hay caja de registro")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", default=str(IMG))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--debug", action="store_true",
                    help="marca lo medido sobre el render en docs/research/shots/")
    a = ap.parse_args()

    img = Image.open(a.img).convert("RGB")
    g = np.asarray(img, dtype=np.float32).mean(axis=2) / 255.0
    x0, y0, wp, hp = caja_registro()
    X = lambda u: x0 + u * wp          # u normalizado -> columna de imagen
    Y = lambda v: y0 + v * hp          # v normalizado -> fila de imagen

    dx = np.abs(np.gradient(g, axis=1))
    dy = np.abs(np.gradient(g, axis=0))

    medidas: dict = {"origen": Path(a.img).name,
                     "unidades": "fracciones 0..1 de la caja (x, y por eje)",
                     "caja_px": [x0, y0, wp, hp]}

    # ── costura central: las DOS líneas que separan las tapas ────────────────
    # En el morro las tapas se separan en dos bordes verticales claros (el
    # interior de cada tapa). Se mide cada línea con el pico de |d/dx| por fila
    # y se hace la MEDIANA: un solo pico falso no puede desplazar el resultado.
    def linea_vertical(win_u: tuple[float, float], filas: list[int]) -> dict | None:
        i0, i1 = int(X(win_u[0])), int(X(win_u[1]))
        us = []
        for y in filas:
            s = suavizar(dx[y, i0:i1], 5)
            if len(s) < 3:
                continue
            pk = int(np.argmax(s))
            if pk in (0, len(s) - 1) or s[pk] < PICO_MIN:
                continue        # pico en el borde de la ventana: no es línea
            us.append((i0 + pk - x0) / wp)
        if len(us) < 5:
            return None
        us = np.array(us)
        med = float(np.median(us))
        # descarta picos muy alejados de la mediana y recalcula
        buenos = us[np.abs(us - med) < 0.012]
        if len(buenos) < 5:
            return None
        return {"u": round(float(np.median(buenos)), 4), "filas": len(buenos)}

    # filas del morro donde la separación es visible: desde el borde superior
    # hasta donde el labio de la ranura la tapa (~v 0.035)...
    morro = list(range(y0 + 2, int(Y(0.035))))
    izq = linea_vertical(COSTURA_WIN_IZQ, morro)
    # ... la línea DERECHA también asoma bajo la rueda (ranura oscura x 458-464,
    # filas 350-500): dos tramos independentes, la mediana los funde.
    der = linea_vertical(COSTURA_WIN_DER,
                         morro + list(range(int(Y(DER_BAJO[0])), int(Y(DER_BAJO[1])))))
    if not izq:
        raise SystemExit("no se encontró la costura izquierda del morro")

    # arranque de la costura: primera fila con pico = primer píxel del cuerpo
    # con separación visible; en la práctica el morro del ratón.
    v0 = None
    for y in range(y0 + 1, y0 + int(0.05 * hp)):
        s = suavizar(dx[y, int(X(COSTURA_WIN_IZQ[0])):int(X(COSTURA_WIN_IZQ[1]))], 5)
        if len(s) > 3 and np.argmax(s) not in (0, len(s) - 1) and np.max(s) >= PICO_MIN:
            v0 = (y - y0) / hp
            break

    # fin de la costura: en la columna del eje la ranura oscura aguanta hasta
    # que la carcasa la corta (~y 560). Se mide con la propia columna, no a ojo.
    col = int(round(X(izq["u"])))
    v1 = None
    suave_col = suavizar(g[:, col], 9)
    y_busca = int(Y(0.30))
    for y in range(y_busca, int(Y(0.62))):
        if suave_col[y] > 0.24 and suave_col[y:y + 20].mean() > 0.26:
            v1 = (y - y0) / hp
            break
    if v1 is None:
        v1 = 0.46    # valor de respaldo; no ha hecho falta hasta ahora

    medidas["costura_central"] = {
        "u_izq": izq["u"],
        "u_der": der["u"] if der else None,
        "y0_v": round(v0, 4) if v0 is not None else None,
        "y1_v": round(v1, 4),
        "metodo": "pico de |d/dx| por fila en el morro (izq) y en el morro+tramo "
                  "bajo la rueda (der), mediana de filas; y1 = subida sostenida "
                  "de la columna del eje bajo la ranura; y0 = primera fila con "
                  f"pico ({izq['filas']} filas válidas)",
    }
    print(f"costura: izq u={izq['u']:.4f} der u={der['u'] if der else '?'} "
          f"entre v={v0:.4f} y v={v1:.4f}")

    # ── rueda y ranura ────────────────────────────────────────────────────────
    # No se puede aislar la rueda por luminancia (su estría ronda 0.27-0.31,
    # casi lo mismo que la carcasa) ni por energía de estrías a secas (las guías
    # brillantes la saturan). Orden de anclaje, de mayor a menor contraste:
    #   1) las GUÍAS (bordes biselados del alojamiento, luminancia 0.7-0.97 por
    #      columna) dan el x de la ranura y acotan la rueda entre ellas;
    #   2) el paso labio claro -> rueda oscura da el y superior;
    #   3) bajo la rueda la banda se OSCURECE (el pozo, 0.07-0.18) y luego la
    #      carcasa la corta (0.25+): dos tramos con umbrales distintos.
    ya, yb = int(Y(RUEDA_V[0])), int(Y(RUEDA_V[1]))
    xa, xb = int(X(RUEDA_U[0])), int(X(RUEDA_U[1]))
    banda_estr = slice(int(X(0.535)), int(X(0.645)))
    ribe = dy[ya:yb, banda_estr].mean(axis=1)
    franja = g[:, banda_estr].mean(axis=1)         # media de la franja central
    suave_f = suavizar(franja, 5)

    # 1) guías: brillantes por columna en el tramo donde son visibles
    percol = g[int(Y(0.10)):int(Y(0.24)), xa:xb].mean(axis=0)
    brillantes = percol > 0.55
    runs, ini = [], None
    for i, b in enumerate(brillantes):
        if b and ini is None:
            ini = i
        elif not b and ini is not None:
            runs.append((ini, i - 1))
            ini = None
    if ini is not None:
        runs.append((ini, len(brillantes) - 1))
    runs = [(xa + r0, xa + r1) for r0, r1 in runs if r1 - r0 >= 3]
    if len(runs) >= 2:
        r_izq, r_der = runs[0], runs[-1]
        wx0, wx1 = r_izq[1] + 1, r_der[0] - 1          # rueda entre guías
        sx0, sx1 = r_izq[0], r_der[1]                  # ranura = de guía a guía
        met = (f"guías brillantes {r_izq} y {r_der}, rueda entre ellas")
    else:
        raise SystemExit(f"se esperaban 2 guías del alojamiento, hay {len(runs)}: {runs}")

    # 2) y superior: el labio es la banda clara; la rueda empieza donde cae
    strip = g[:, wx0 + 2:wx1 - 2].mean(axis=1)         # franja de la RUEDA sola
    suave_s = suavizar(strip, 5)
    ry0b = None
    for y in range(ya, int(Y(0.20))):
        if suave_s[y] < 0.34 and suave_s[y:y + 10].mean() < 0.34:
            ry0b = y
            break
    if ry0b is None:
        raise SystemExit("no se ve el paso labio->rueda")

    # 3) borde inferior de la rueda: último tramo estríado antes de que la
    #    banda se hunda (pozo) y el paso de vuelta a la carcasa (fondo del pozo)
    ribe_full = dy[:, banda_estr].mean(axis=1)
    ry1 = ry0b + 30
    tramo = [y for y in range(ry0b + 30, int(Y(0.29)))]
    for y in tramo:
        if suave_s[y] < 0.18 and suave_s[y:y + 8].mean() < 0.18:
            ry1 = y            # la banda cae al pozo: ahí acaba la rueda
            break
    else:
        ry1 = tramo[-1]
    sy1 = ry1
    for y in range(ry1 + 2, int(Y(0.32))):
        if suave_s[y] > 0.24 and suave_s[y:y + 8].mean() > 0.24:
            sy1 = y            # la carcasa corta el pozo
            break
    # control de cordura: la rueda estría más que el pozo liso; si no, aviso
    ribe_rueda = float(ribe_full[ry0b + 20:ry1].mean())
    ribe_pozo = float(ribe_full[ry1 + 5:sy1].mean()) if sy1 > ry1 + 5 else 0.0
    if ribe_rueda < 1.5 * max(ribe_pozo, 1e-9):
        print(f"  aviso: estrías poco marcadas (rueda {ribe_rueda:.4f} vs pozo "
              f"{ribe_pozo:.4f}); el borde inferior pudo comerse el pozo")
    print(f"rueda: x {wx0}..{wx1} y {ry0b}..{ry1}   ranura: x {sx0}..{sx1} "
          f"y hasta {sy1}   estrías rueda/pozo {ribe_rueda:.4f}/{ribe_pozo:.4f}")

    # labio: banda CLARA sobre la rueda (la única pieza clara de la zona)
    lip_filas = [y for y in range(y0, ry0b) if suave_f[y] > 0.42]
    lip_y0 = None
    lip_x0 = lip_x1 = None
    if lip_filas:
        for y in range(lip_filas[0], ry0b):
            if suave_f[y] < 0.34:
                lip_y0 = y - 2
                break
        percol_lip = g[lip_filas[0] + 4:ry0b - 4, xa:xb].mean(axis=0)
        lis = np.flatnonzero(percol_lip > 0.40)
        if len(lis) and lis[-1] - lis[0] > 20:
            lip_x0, lip_x1 = xa + int(lis[0]), xa + int(lis[-1])
        else:
            lip_x0, lip_x1 = sx0, sx1
    met_rueda = (f"columnas = {met}; filas = labio->oscuro por arriba "
                 f"(x>{wx0}) y caída al pozo (lum<0.18) por abajo")
    medidas["rueda"] = {
        "x0_u": round((wx0 - x0) / wp, 4), "x1_u": round((wx1 - x0) / wp, 4),
        "y0_v": round((ry0b - y0) / hp, 4), "y1_v": round((ry1 - y0) / hp, 4),
        "metodo": met_rueda,
    }
    medidas["ranura"] = {
        "x0_u": round((sx0 - x0) / wp, 4), "x1_u": round((sx1 - x0) / wp, 4),
        "y0_v": medidas["rueda"]["y0_v"],   # el pozo arranca donde la rueda
        "y1_v": round((sy1 - y0) / hp, 4),
        "metodo": "de guía a guía en x; y0 = tope de la rueda; y1 = paso pozo->"
                  "carcasa en la franja central",
    }
    if lip_filas and lip_x0 is not None and lip_x1 is not None:
        medidas["ranura"]["lip_x0_u"] = round((lip_x0 - x0) / wp, 4)
        medidas["ranura"]["lip_x1_u"] = round((lip_x1 - x0) / wp, 4)
        medidas["ranura"]["lip_y0_v"] = round(((lip_y0 or y0) - y0) / hp, 4)
        medidas["ranura"]["metodo"] += (
            f"; labio medido por banda clara ({lip_x0}-{lip_x1}, "
            f"y {(lip_y0 or y0)}..{ry0b})")
    print(f"ranura: x {sx0}..{sx1} y {ry0b}..{sy1}  "
          f"labio: x {lip_x0}..{lip_x1}")

    # ── panel lateral: borde interior fila a fila ────────────────────────────
    # Estructura de una fila tipo: [panel oscuro][bevel/mango brillante suelto]
    # [SOMBRA del canto del panel: el valle] [carcasa 0.28-0.31]. El valle del
    # PANEL queda confundido a veces con el valle de un bisel del casco (la
    # imagen es oblicua y hay sombras por todas partes). Discriminante: si a la
    # IZQUIERDA del valle el brillo medio es bajo, el valle pertenece al panel;
    # si a la izquierda hay brillo (>0.30), es el bisel de otra pieza y se
    # sigue buscando hacia la izquierda.
    filas_tabla = []
    descartadas = []
    ya_f, yb_f = int(Y(FLANCO_V[0])), int(Y(FLANCO_V[1]))
    for y in range(ya_f, yb_f, PASO_FILAS):
        w0, w1 = FLANCO_WIN
        prof = suavizar(g[y, w0:w1], 9)
        bajos = prof < VALLE_LUM
        if not bajos.any():
            descartadas.append((y, "sin valle"))
            continue
        runs, ini = [], None
        for i, b in enumerate(bajos):
            if b and ini is None:
                ini = i
            elif not b and ini is not None:
                runs.append((ini, i))
                ini = None
        if ini is not None:
            runs.append((ini, len(bajos)))
        # clasifica por área (el valle del panel es ancho y profundo)
        candidatos = []
        for r0, r1 in runs:
            area = float((VALLE_LUM - prof[r0:r1]).clip(0).sum())
            if area >= VALLE_AREA:
                candidatos.append((area, r0, r1))
        if not candidatos:
            descartadas.append((y, "valle débil"))
            continue
        candidatos.sort(reverse=True)
        elegido = None
        for area, r0, r1 in candidatos[:3]:
            if r0 >= 25:
                izquierda = float(prof[max(0, r0 - 25):r0].mean())
            else:
                izquierda = 1.0
            if izquierda <= INSET_LUM:
                elegido = (r0, r1)
                break
        if elegido is None:
            # todos los valles tienen brillo a la izquierda: el de más área es
            # lo mejor que hay en esta fila (pasa justo donde el mando del
            # pulgar toca el canto); se anota para no olvidarlo
            elegido = (candidatos[0][1], candidatos[0][2])
        centro = w0 + int(np.argmin(prof[elegido[0]:elegido[1]]))
        filas_tabla.append(((y - y0) / hp, (centro - x0) / wp, 1.0))
    # mediana de 3 sobre la serie de bordes: el mando del pulgar deja valles
    # falsos un poco más a la izquierda en alguna fila; la mediana los absorbe
    us = np.array([u for _, u, _ in filas_tabla])
    if len(us) >= 3:
        us_s = np.array([np.median(us[max(0, i - 1):i + 2]) for i in range(len(us))])
        filas_tabla = [(v, u, area)
                       for (v, _, area), u in zip(filas_tabla, us_s)]
    medidas["panel_lateral_izq"] = [[round(v, 4), round(u, 4)]
                                    for v, u, _ in filas_tabla]
    medidas["panel_lateral_izq_metodo"] = (
        "centro del valle oscuro (suavizado 9, umbral 0.20) de mayor área en la "
        "banda del flanco, por fila cada 9 px, mediana de 3; "
        f"{len(filas_tabla)} filas, descartadas: {len(descartadas)}")
    print(f"panel: {len(filas_tabla)} filas "
          f"(v {filas_tabla[0][0]:.3f}..{filas_tabla[-1][0]:.3f}), "
          f"{len(descartadas)} descartadas")

    # ── lo que NO se pudo medir de forma fiable ──────────────────────────────
    # La costura del reposamanos es diagonal y su contraste cae por debajo del
    # ruido del render (picos sueltos de |d/dy| 0.1-0.3 sin continuidad entre
    # columnas contiguas); PLATE_Y0 en el talón no existe como línea horizontal.
    medidas["no_medido"] = [
        "PALM_Y0 (costura del reposamanos): línea diagonal con contraste "
        "insuficiente y sin continuidad de fila a fila; se queda como constante",
        "borde inferior de las tapas en los flancos: en la imagen es diagonal "
        "(~y477 en el flanco izq, ~y562 en el eje, ~y629 a la derecha); la "
        "y1_v medida es la del EJE, donde la costura es nítida",
        "posición de los mandos laterales (precisión, adelante/atrás, rueda del "
        "pulgar, perfiles): quedan como constantes del generador",
    ]

    Path(a.out).write_text(json.dumps(medidas, indent=2, ensure_ascii=False))
    print(f"escrito: {a.out}")

    if a.debug:
        marca_debug(medidas, img, (x0, y0, wp, hp))
    return 0


def _poligono(puntos):
    return [(float(x), float(y)) for x, y in puntos]


def marca_debug(m: dict, img: Image.Image, caja) -> None:
    """Dibuja lo medido sobre el renderpara comprobarlo a ojo."""
    x0, y0, wp, hp = caja
    vis = img.copy()
    dr = ImageDraw.Draw(vis)

    def xpix(u):
        return x0 + u * wp
    def ypix(v):
        return y0 + v * hp

    c = m["costura_central"]
    r = m["rueda"]
    s = m["ranura"]
    # costuras: rojo = eje/tapa izq, naranja = tapa der; límites en amarillo
    dr.line([(xpix(c["u_izq"]), ypix(c["y0_v"])),
             (xpix(c["u_izq"]), ypix(c["y1_v"]))], fill=(255, 60, 60), width=2)
    if c["u_der"]:
        dr.line([(xpix(c["u_der"]), ypix(c["y0_v"])),
                 (xpix(c["u_der"]), ypix(c["y1_v"]))], fill=(255, 150, 40), width=2)
    dr.line([(x0 + 40, ypix(c["y0_v"])), (x0 + wp - 40, ypix(c["y0_v"]))],
            fill=(255, 220, 60), width=1)
    dr.line([(x0 + 40, ypix(c["y1_v"])), (x0 + wp - 40, ypix(c["y1_v"]))],
            fill=(255, 220, 60), width=1)
    # rueda: cian; ranura: magenta; labio: amarillo fino
    dr.rectangle([xpix(r["x0_u"]), ypix(r["y0_v"]),
                  xpix(r["x1_u"]), ypix(r["y1_v"])], outline=(0, 220, 255), width=2)
    dr.rectangle([xpix(s["x0_u"]), ypix(s["y0_v"]),
                  xpix(s["x1_u"]), ypix(s["y1_v"])], outline=(255, 0, 200), width=1)
    if "lip_x0_u" in s:
        dr.rectangle([xpix(s["lip_x0_u"]), ypix(s["lip_y0_v"]),
                      xpix(s["lip_x1_u"]), ypix(r["y0_v"])],
                     outline=(255, 255, 0), width=1)
    # panel: puntos verde lima en cada borde medido, unidos
    pts = [(xpix(u), ypix(v)) for v, u in m["panel_lateral_izq"]]
    dr.line(pts, fill=(120, 255, 90), width=1)
    for px, py in pts:
        dr.ellipse([px - 2, py - 2, px + 2, py + 2], fill=(120, 255, 90))
    SHOTS.mkdir(parents=True, exist_ok=True)
    sal = SHOTS / "interior-marcas.png"
    vis.save(sal)
    print(f"debug: {sal}")


if __name__ == "__main__":
    raise SystemExit(main())