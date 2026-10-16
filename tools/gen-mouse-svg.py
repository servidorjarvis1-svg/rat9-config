#!/usr/bin/env python3
"""Genera el diagrama SVG del R.A.T.9 a partir de un perfil de anchura.

Por qué un generador y no un SVG escrito a mano: la primera version a mano
acabo con trapecios solapados y controles fuera de su panel, porque cada
coordenada estaba calculada a ojo y una correccion rompia la de al lado. Aqui el
cuerpo se define como un PERFIL DE ANCHURA por altura, la aleta del pulgar como
una desviacion de ese perfil, y el panel lateral se DERIVA de los dos. Los
controles se colocan sobre la linea central de ese panel, asi que es imposible
que se salgan o se pisen: se mueven solos cuando se mueve la silueta.

    python3 tools/gen-mouse-svg.py                      # escribe rat9/ui/diagram-mouse.svg
    python3 tools/gen-mouse-svg.py --out /tmp/prueba.svg
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# ─── parametros de la silueta ────────────────────────────────────────────────
CX = 280.0                       # eje longitudinal del cuerpo
Y_NOSE, Y_HEEL = 60.0, 700.0     # principio y fin del raton

# Perfil: (y, semianchura del cuerpo simetrico). Interpolado linealmente.
PROFILE = [
    (60, 58), (85, 70), (115, 84), (155, 98), (205, 110), (265, 118),
    (325, 122), (390, 124), (450, 124), (510, 122), (560, 118), (600, 112),
    (640, 100), (670, 84), (700, 58),
]

# Aleta del pulgar: (y, x del borde izquierdo). Solo existe en su tramo.
WING = [(300, 152), (345, 124), (390, 104), (440, 98), (490, 110), (540, 136),
        (580, 172)]

# Panel lateral izquierdo: anchura del borde del cuerpo hacia dentro.
FLANK_W = [
    (100, 30), (160, 34), (240, 40), (300, 48), (360, 62), (410, 80),
    (450, 92), (500, 88), (550, 78), (600, 64), (645, 52),
]

# Controles del panel lateral: (id, etiqueta, uso, y0, y1)
SIDE_CONTROLS = [
    ("btn-precision", "Botón de precisión",  8, 152, 258),
    ("btn-forward",   "Adelante",            5, 276, 330),
    ("btn-back",      "Atrás",               4, 346, 400),
]
THUMB_WHEEL = ("thumb", 6, 7, 398, 516)          # y0, y1; uso 6 = CW, 7 = CCW
MODE_BTN = ("mode", 9, 424, 500, 3)              # uso, y0, y1 (los y se recalculan)
MODE_BTN_HW = 24.0                              # ancho del boton de modos

# Rueda central
WHEEL_X_HALF, WHEEL_Y0, WHEEL_Y1 = 21.0, 100.0, 252.0
PLATE_Y0, PLATE_Y1 = 64.0, 300.0                 # botones principales
PALM_Y0 = 302.0                                  # reposamanos


def lerp_profile(table, y, clamp=True):
    """Interpola una tabla (y, valor)."""
    if y <= table[0][0]:
        return table[0][1]
    if y >= table[-1][0]:
        return table[-1][1]
    for (y0, v0), (y1, v1) in zip(table, table[1:]):
        if y0 <= y <= y1:
            t = (y - y0) / (y1 - y0)
            # suavizado (smoothstep) para curvas mas naturales
            t = t * t * (3 - 2 * t)
            return v0 + (v1 - v0) * t
    return table[-1][1]


# ─── contorno MEDIDO sobre el render (opcional) ──────────────────────────────
# Si existe rat9/ui/silueta.json (lo escribe tools/trazar-silueta.py midiendo el
# render), el dibujo se traza SOBRE ESA SILUETA en vez de usar el perfil
# inventado de aqui abajo. Es lo que hace que las dos capas coincidan: no se
# ajusta el dibujo a la imagen a ojo, se mide la imagen y el dibujo sale de ella.
#
# El contorno viene normalizado a la caja del raton (0..1 en cada eje), y aqui se
# proyecta sobre la caja del viewBox del esquema.
SIL_X0, SIL_Y0, SIL_W, SIL_H = 44.0, 60.0, 362.0, 640.0
_CONTORNO: dict | None = None
_EJE = 280.0            # eje del cuerpo (CX); con contorno medido se recalcula


def _eje_medido(cont: dict) -> float:
    """Eje del cuerpo medido en la parte DELANTERA, donde aun no hay aleta.

    No vale tomar el centro de la caja: la aleta desplaza ese centro hacia la
    izquierda y el eje saldria torcido. En el morro todavia no hay aleta, asi que
    ahi el punto medio izquierda-derecha ES el eje.
    """
    delanteras = [(l + r) / 2 for (v, l), (_, r)
                  in zip(cont["left"], cont["right"]) if v < 0.30]
    if not delanteras:
        return CX
    return SIL_X0 + (sum(delanteras) / len(delanteras)) * SIL_W


def _interp(tabla, v: float) -> float:
    if v <= tabla[0][0]:
        return tabla[0][1]
    if v >= tabla[-1][0]:
        return tabla[-1][1]
    for (v0, x0), (v1, x1) in zip(tabla, tabla[1:]):
        if v0 <= v <= v1:
            return x0 + (x1 - x0) * (v - v0) / (v1 - v0)
    return tabla[-1][1]


def _v(y: float) -> float:
    """Altura normalizada (0 = morro, 1 = talon)."""
    return (y - Y_NOSE) / (Y_HEEL - Y_NOSE)


def body_half(y: float) -> float:
    return lerp_profile(PROFILE, y)


def left_edge(y: float) -> float:
    """Borde izquierdo: la aleta si sobresale, o el cuerpo."""
    if _CONTORNO is not None:
        return SIL_X0 + _interp(_CONTORNO["left"], _v(y)) * SIL_W
    body = CX - body_half(y)
    if WING[0][0] <= y <= WING[-1][0]:
        return min(body, lerp_profile(WING, y))
    return body


def right_edge(y: float) -> float:
    if _CONTORNO is not None:
        return SIL_X0 + _interp(_CONTORNO["right"], _v(y)) * SIL_W
    return CX + body_half(y)


def flank_inner(y: float) -> float:
    """Borde interior del panel lateral."""
    if _CONTORNO is not None:
        # una fraccion del ancho local: asi el panel sigue la forma medida en
        # vez de arrastrar las anchuras fijas del perfil inventado
        return left_edge(y) + 0.20 * (right_edge(y) - left_edge(y))
    return left_edge(y) + lerp_profile(FLANK_W, y)


def _bezier_segments(pts) -> list[str]:
    """Segmentos C para una lista de puntos. Se duplican los extremos para dar
    la tangente en los bordes."""
    segs = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        segs.append(f"C {c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} "
                    f"{p2[0]:.1f} {p2[1]:.1f}")
    return segs


def _xy(points) -> list[tuple[float, float]]:
    return [(float(x), float(y)) for x, y in points]


def smooth_path(points, closed: bool = False) -> str:
    """Curva suave que pasa por todos los puntos."""
    if len(points) < 2:
        return ""
    pts = _xy(points)
    if closed:
        pts = [pts[-1]] + pts + [pts[0], pts[1]]
        return (f"M {pts[1][0]:.1f} {pts[1][1]:.1f} "
                + " ".join(_bezier_segments(pts)) + " Z")
    pts = [pts[0]] + pts + [pts[-1]]
    return (f"M {pts[1][0]:.1f} {pts[1][1]:.1f} "
            + " ".join(_bezier_segments(pts)))


def band_shape(outer, inner) -> str:
    """Forma cerrada con dos bordes curvos unidos por RECTAS.

    Es lo que necesitan los botones, el reposamanos y el panel lateral: el borde
    exterior se curva, pero donde la pieza topa con una costura hay una esquina.
    Con un Catmull-Rom cerrado esas esquinas se redondeaban de mas y el redondeo
    se salia del contorno del raton (una lengueta en el borde derecho).
    `inner` viene ya recorrido en sentido contrario para que el contorno sea
    continuo.
    """
    o, i = _xy(outer), _xy(inner)
    if len(o) < 2 or len(i) < 2:
        return ""
    parts = [f"M {o[0][0]:.1f} {o[0][1]:.1f}"]
    parts += _bezier_segments([o[0]] + o + [o[-1]])
    parts.append(f"L {i[0][0]:.1f} {i[0][1]:.1f}")
    parts += _bezier_segments([i[0]] + i + [i[-1]])
    parts.append("Z")
    return " ".join(parts)


def sample(a: float, b: float, n: int) -> list[float]:
    return [a + (b - a) * i / (n - 1) for i in range(n)]


def rect_on_flank(y0, y1, inset=6.0) -> str:
    """Control dentro del panel lateral, siguiendo su contorno.

    La primera version calculaba un trapecio de 4 puntos y se salia del panel en
    cuanto el borde se curvaba. Ahora se recorren los dos bordes del panel en
    vertical y se cierra el contorno, asi que el control queda SIEMPRE dentro,
    aunque el panel se ensanche y se estreche a lo largo de su altura.
    """
    ys = sample(y0, y1, 12)
    left = [(left_edge(y) + inset, y) for y in ys]
    right = [(flank_inner(y) - inset, y) for y in ys]
    # si en algun punto el panel es demasiado estrecho, se avisa por stdout
    narrow = min(r - l for (l, _), (r, _) in zip(left, right))
    if narrow < 8:
        print(f"  aviso: control {y0:.0f}-{y1:.0f} tiene solo {narrow:.1f} px "
              f"de ancho util en el panel")
    pts = left + list(reversed(right))
    return (f"M {pts[0][0]:.1f} {pts[0][1]:.1f} "
            + " ".join(f"L {x:.1f} {y:.1f}" for x, y in pts[1:]) + " Z")


# El bloque <style> del SVG, como cadena NORMAL y no dentro del f-string: asi
# las llaves del CSS no hay que escaparlas ({{ }}) y no se puede volver a
# romper el generador por escribir un selector.
SVG_STYLE = """<style>
  /* Valores por defecto del propio dibujo, para que el SVG se pueda
     previsualizar suelto (tools/svg-render.py). La app le QUITA este bloque y
     pone los suyos a traves de las variables --mg-*: asi el raton no acaba
     siendo un dibujo aparte con su propia paleta. */
  .mouse-diagram {
    --mg-shell:      #171d28;
    --mg-shell-hi:   #232c3c;
    --mg-edge:       #3a4761;
    --mg-plate:      #1e2632;
    --mg-plate-hi:   #2b3543;
    --mg-palm:       #1e2632;
    --mg-recess:     #080a0f;
    --mg-control:    #252f3d;
    --mg-control-hi: #3b4859;
    --mg-seam:       #2b3543;
    --mg-ridge:      #39465a;
    --mg-gap:        #0b0e14;
    --mg-ink:        #93a7c3;
    --mg-guide:      #5c7691;
    --mg-badge-bg:   #0b0e14;
    --mg-badge-edge: #93a7c3;
    --mg-luz:        #ffffff;
    /* Llamadas al estilo del software original: caja achaflanada + linea con
       codo + punto de anclaje. El acento va en cian electrico, no en el naranja
       del original: misma forma, distinto color (el naranja no es de la casa). */
    --mg-box-a:      #16283f;
    --mg-box-b:      #101f31;
    --mg-accent:     #38bdf8;
  }
  .mouse-diagram .badge text {
    fill: var(--mg-ink); font-family: ui-monospace, monospace;
    font-weight: 600; letter-spacing: .02em;
  }
  .mouse-diagram .cal-n {
    fill: var(--mg-accent); font-family: ui-monospace, monospace;
    font-weight: 700; letter-spacing: .02em;
  }
  .mouse-diagram .cal-t {
    fill: var(--mg-ink); font-family: ui-monospace, monospace;
    letter-spacing: .05em;
  }
  .mouse-diagram .z { cursor: pointer; }
  .mouse-diagram .z .hit { transition: fill .16s ease, stroke .16s ease; }
  .mouse-diagram .z:hover .hit { fill: var(--mg-control-hi); stroke: var(--mg-edge); }
  .mouse-diagram .z:focus-visible { outline: none; }
  .mouse-diagram .z:focus-visible .hit { stroke: var(--mg-edge); stroke-width: 2.6; }
  .mouse-diagram .z.sel .hit { stroke: var(--mg-edge); stroke-width: 2.6; }
  .mouse-diagram.sel-mode .z:not(.sel) .hit { opacity: .55; }
  .mouse-diagram .lbl { fill: var(--mg-ink); font: 10px ui-monospace, monospace; }
</style>"""


# La paleta del dibujo, en tokens. El cuerpo del SVG se genera con hex sueltos
# y al final se reescriben aqui: asi se ve de un vistazo QUE colores usa el
# dibujo y no se cuela ninguno nuevo sin pasar por aqui.
FILL_MAP = {
    "#171d28": "var(--mg-shell)",
    "#232c3c": "var(--mg-shell-hi)",
    "#2b3543": "var(--mg-plate-hi)",
    "#242e3c": "var(--mg-plate)",
    "#1e2632": "var(--mg-plate)",
    "#3a4657": "var(--mg-plate-hi)",
    "#3a4761": "var(--mg-edge)",
    "#3d4a5f": "var(--mg-edge)",
    "#1e2632": "var(--mg-plate)",
    "#080a0f": "var(--mg-recess)",
    "#151a23": "var(--mg-recess)",
    "#141a24": "var(--mg-gap)",
    "#1b2330": "var(--mg-recess)",
    "#252f3d": "var(--mg-control)",
    "#3b4859": "var(--mg-control-hi)",
    "#0b0e14": "var(--mg-gap)",
    "#39465a": "var(--mg-ridge)",
    "#2f3a4c": "var(--mg-seam)",
    "#93a7c3": "var(--mg-ink)",
    "#16283f": "var(--mg-box-a)",
    "#101f31": "var(--mg-box-b)",
    "#38bdf8": "var(--mg-accent)",
    "#ffffff": "var(--mg-luz)",
}


def tokenizar_cuerpo(svg: str) -> str:
    """Reescribe la paleta suelta del cuerpo por variables --mg-*.

    Se aplica SOLO a lo que va despues de </defs>: el bloque <style> de delante
    define los valores por defecto en hex y tiene que quedarse en hex (si se
    tokenizara, quedaria un var() que se apunta a si mismo).
    """
    head, sep, tail = svg.partition("</defs>")
    for hexv, token in FILL_MAP.items():
        tail = tail.replace(f'"{hexv}"', f'"{token}"')
    sueltos = re.findall(r'"(#[0-9a-fA-F]{6})"', tail)
    if sueltos:
        print(f"  aviso: quedan colores sin tokenizar en el cuerpo: "
              f"{sorted(set(sueltos))}")
    return head + sep + tail


# Llamadas: el lenguaje del software original (caja achaflanada -> linea con codo
# -> punto de anclaje sobre el control), pero alimentado con NUESTRA geometria
# medida, no con una lamina ajena. Asi registra por construccion.
#
# Se probo a superponer la lamina de llamadas original (callouts_labels_overlay)
# sobre el render: sus 15 anclas caen en zonas arbitrarias y sus cajas tapan el
# raton, porque se dibujaron para OTRA vista del aparato. Se adopta la forma, no
# la lamina.
#
# Los anclajes NO son numeros escritos a mano: se calculan con la misma geometria
# que dibuja el raton. Si el contorno se remide sobre la imagen y la forma cambia,
# los puntos se mueven con ella en vez de quedarse senalando al aire.
CAJA_X0, CAJA_W, CAJA_H = 414.0, 138.0, 24.0
CAJA_Y0, CAJA_PASO = 76.0, 52.0
CHAFLAN = 7.0
# El viewBox del esquema suelto es 560x800 (el de la capa superpuesta es otro,
# 700x1090, porque tiene que casar con la imagen). Las cajas tienen que caber en
# 560: con 236 de ancho se salian y el render las cortaba por la derecha.


def anclajes() -> list[tuple[int, str, float, float]]:
    """Punto de anclaje de cada llamada, calculado sobre la geometria del dibujo."""
    ym = (PLATE_Y0 + PLATE_Y1) / 2
    centro_fl = lambda y: (left_edge(y) + flank_inner(y)) / 2      # noqa: E731
    y_modo = [MODE_BTN[2] + (MODE_BTN[3] - MODE_BTN[2]) * (i + 0.5) / MODE_BTN[4]
              for i in range(MODE_BTN[4])]
    t0, t1 = THUMB_WHEEL[3], THUMB_WHEEL[4]
    tm = (t0 + t1) / 2
    cy = {u: (y0 + y1) / 2 for _z, _l, u, y0, y1 in SIDE_CONTROLS}
    my = (PLATE_Y0 + 26 + PLATE_Y0 + 152) / 2
    return [
        (1,  "IZQ.",     (_EJE + left_edge(ym)) / 2,   ym),
        (2,  "DER.",     (_EJE + right_edge(ym)) / 2,  ym),
        (3,  "RUEDA",    _EJE,                         (WHEEL_Y0 + WHEEL_Y1) / 2),
        (4,  "ATRAS",    centro_fl(cy[4]),             cy[4]),
        (5,  "ADEL.",    centro_fl(cy[5]),             cy[5]),
        (6,  "PULG CW",  centro_fl((t0 + tm) / 2),     (t0 + tm) / 2),
        (7,  "PULG CCW", centro_fl((tm + t1) / 2),     (tm + t1) / 2),
        (8,  "PRECIS.",  centro_fl(cy[8]),             cy[8]),
        (9,  "MODOS",    left_edge(my) + 3 + MODE_BTN_HW / 2, my),
    ]


def caja_llamada(x: float, y: float, w: float, h: float) -> str:
    """Rectangulo con las esquinas derechas achaflanadas, como el original."""
    c = CHAFLAN
    return (f"M {x:.0f} {y + h:.0f} L {x:.0f} {y:.0f} "
            f"L {x + w - c:.0f} {y:.0f} L {x + w:.0f} {y + c:.0f} "
            f"L {x + w:.0f} {y + h - c:.0f} L {x + w - c:.0f} {y + h:.0f} Z")


def svg_badges() -> str:
    """Cajas en columna + linea con codo + punto de anclaje.

    Las llamadas se ORDENAN por la altura de su anclaje, no por numero de uso.
    Si no, la linea de la llamada 4 sale de una caja alta y baja hasta un control
    bajo, y cruza por delante de las de abajo: con once lineas aquello parecia
    una marana. Ordenadas por altura, salen abanico y no se pisan.
    """
    out = []
    for i, (uso, nombre, ax, ay) in enumerate(sorted(anclajes(), key=lambda t: t[3])):
        by = CAJA_Y0 + i * CAJA_PASO
        cy = by + CAJA_H / 2
        relleno = "var(--mg-box-a)" if i % 2 == 0 else "var(--mg-box-b)"
        # el codo: sale recto del borde izquierdo de la caja y luego entra en
        # diagonal al anclaje. El tramo recto es lo que le da el aire de lamina
        # tecnica; en diagonal directa parecia otra cosa.
        mx = max(ax + 26, 250.0)
        out.append(
            f'  <path d="M {CAJA_X0:.0f} {cy:.0f} L {mx:.0f} {cy:.0f} '
            f'L {ax + 9:.0f} {ay:.0f}" fill="none" stroke="var(--mg-accent)" '
            f'stroke-width="1.3" stroke-linejoin="miter"/>\n'
            f'  <circle cx="{ax:.0f}" cy="{ay:.0f}" r="4" '
            f'fill="var(--mg-accent)"/>\n'
            f'  <path d="{caja_llamada(CAJA_X0, by, CAJA_W, CAJA_H)}" '
            f'fill="{relleno}" stroke="var(--mg-accent)" stroke-width="1.3"/>\n'
            f'  <text class="cal-n" x="{CAJA_X0 + 10:.0f}" y="{cy + 4:.0f}" '
            f'font-size="11.5">{uso:02d}</text>\n'
            f'  <text class="cal-t" x="{CAJA_X0 + 27:.0f}" y="{cy + 4:.0f}" '
            f'font-size="10">{nombre}</text>')
    return "\n".join(out)


# ─── capa para superponer al render ───────────────────────────────────────────
# La imagen realista y el esquema son dos siluetas distintas: alinear solo la
# CAJA deja las costuras desplazadas. Los numeros del encaje NO se escriben a
# mano aqui: los mide tools/encajar-capa.py sobre la imagen y los deja en
# rat9/ui/capa.json. Si cambia la imagen de base, se vuelve a correr y listo;
# escritos a mano se desincronizarian en silencio.
CAPA_JSON = None


def cargar_encaje(here: Path) -> dict:
    """Encaje medido sobre la imagen base. Si no hay, se usan los del render
    generado, que es el que habia cuando se escribio esto."""
    ruta = here / "rat9/ui/capa.json"
    if ruta.is_file():
        return json.loads(ruta.read_text())
    return {
        "viewbox": [720, 931],
        "bbox_imagen": [134.0, 135.0, 452.0, 658.0],
        # ojo: la caja es la que el DIBUJO ocupa de verdad, no la del viewBox.
        # El cuerpo se genera sobre el perfil PROFILE, que va de y=60 a y=700.
        "bbox_esquema": [44.0, 60.0, 362.0, 640.0],
    }


def envolver_para_imagen(svg: str, encaje: dict) -> str:
    """Deja el dibujo listo para ir ENCIMA de la imagen, como segunda capa.

    Mismo tamano que la imagen y la geometria transformada a la caja donde ha
    caido el raton en ella. Asi las dos capas se superponen en el navegador con
    un simple width:100% en ambas, sin calculos en CSS (que es donde se
    desincronizarian sin que nadie se enterase).
    """
    vw, vh = encaje["viewbox"]
    ex, ey, ew, eh = encaje["bbox_esquema"]
    ix, iy, iw, ih = encaje["bbox_imagen"]
    sx, sy = iw / ew, ih / eh
    tx, ty = ix - sx * ex, iy - sy * ey

    svg = svg.replace('viewBox="0 0 560 800"', f'viewBox="0 0 {vw} {vh}"')
    svg = svg.replace('class="mouse-diagram"',
                      'class="mouse-diagram capa-render"')
    # El <g> va DESPUES de </defs> y envuelve solo el dibujo: si se mete tras
    # </title> (que fue el primer intento) el elemento cae DENTRO del texto del
    # titulo y el SVG deja de ser XML valido.
    abre = svg.index("</defs>") + len("</defs>")
    transform = (f'\n<g transform="translate({tx:.2f} {ty:.2f}) '
                 f'scale({sx:.5f} {sy:.5f})">')
    return svg[:abre] + transform + svg[abre:].replace("</svg>", "</g>\n</svg>")


def build_svg() -> str:
    # ── silueta ──────────────────────────────────────────────────────────────
    # Si hay contorno medido sobre la imagen, manda el. Si no, se usa el perfil
    # de aqui arriba, que es el que habia antes de poder medir.
    eje = _EJE
    ys_right = [p[0] for p in PROFILE]
    right_pts = [(right_edge(y), y) for y in ys_right]
    left_pts = [(left_edge(y), y) for y in reversed(ys_right)]
    shell = smooth_path(right_pts + left_pts, closed=True)

    # ── reposamanos ──────────────────────────────────────────────────────────
    # Comparte borde con el casco (derecha) y con el panel lateral (izquierda)
    # para que no aparezcan contornos paralelos que parezcan otra chapa.
    palm_ys = [PALM_Y0] + [y for y in ys_right if PALM_Y0 < y < Y_HEEL] + [Y_HEEL]
    palm = band_shape(
        [(right_edge(y), y) for y in palm_ys],
        [(flank_inner(y), y) for y in reversed(palm_ys)])

    # ── botones principales ──────────────────────────────────────────────────
    def plate(side: str) -> str:
        ys = [PLATE_Y0] + [y for y in ys_right if PLATE_Y0 < y < PLATE_Y1] \
            + [PLATE_Y1]
        outer = ([(flank_inner(y) + 2.5, y) for y in ys] if side == "l"
                 else [(right_edge(y) - 3.5, y) for y in ys])
        inner = [(eje - 3, y) for y in reversed(ys)] if side == "l" else \
                [(eje + 3, y) for y in reversed(ys)]
        return band_shape(outer, inner)

    def filo_placa(side: str) -> str:
        """Filo iluminado a lo largo del borde exterior de la tapa: es el canto
        achaflanado cogiendo la luz. Se queda corto hacia atras a proposito, que
        el brillo se apague solo."""
        ys = [PLATE_Y0 + 4] + [y for y in ys_right
                               if PLATE_Y0 + 4 < y < PLATE_Y1 - 24] \
            + [PLATE_Y1 - 24]
        off = 4.5 if side == "l" else -4.5
        pts = ([(flank_inner(y) + 2.5 + off, y) for y in ys] if side == "l"
               else [(right_edge(y) - 3.5 + off, y) for y in ys])
        return smooth_path(pts)

    # ── panel lateral ────────────────────────────────────────────────────────
    flank_ys = [y for y in ys_right if y >= 96]
    flank = band_shape(
        [(left_edge(y), y) for y in flank_ys],
        [(flank_inner(y), y) for y in reversed(flank_ys)])

    # ── rueda central ────────────────────────────────────────────────────────
    wx0, wx1 = eje - WHEEL_X_HALF, eje + WHEEL_X_HALF
    channel = (f"M {wx0 - 8:.0f} {WHEEL_Y0 - 10:.0f} L {wx1 + 8:.0f} "
               f"{WHEEL_Y0 - 10:.0f} Q {wx1 + 12:.0f} {WHEEL_Y0 - 10:.0f} "
               f"{wx1 + 12:.0f} {WHEEL_Y0 - 4:.0f} L {wx1 + 12:.0f} "
               f"{WHEEL_Y1 + 6:.0f} Q {wx1 + 12:.0f} {WHEEL_Y1 + 12:.0f} "
               f"{wx1 + 8:.0f} {WHEEL_Y1 + 12:.0f} L {wx0 - 8:.0f} "
               f"{WHEEL_Y1 + 12:.0f} Q {wx0 - 12:.0f} {WHEEL_Y1 + 12:.0f} "
               f"{wx0 - 12:.0f} {WHEEL_Y1 + 6:.0f} L {wx0 - 12:.0f} "
               f"{WHEEL_Y0 - 4:.0f} Q {wx0 - 12:.0f} {WHEEL_Y0 - 10:.0f} "
               f"{wx0 - 8:.0f} {WHEEL_Y0 - 10:.0f} Z")

    # ── controles laterales ──────────────────────────────────────────────────
    side_svg = "\n".join(
        f'''  <g class="z" data-zone="{zid}" data-usage="{usage}" tabindex="0"
     role="button" aria-label="{label}">
    <path class="hit" d="{rect_on_flank(y0, y1)}" fill="#252f3d"
          stroke="#0b0e14" stroke-width="2" stroke-linejoin="round"/>
  </g>''' for zid, label, usage, y0, y1 in SIDE_CONTROLS)

    # ── rueda del pulgar (dos mitades, un sentido cada una) ──────────────────
    _zid, u_cw, u_ccw, ty0, ty1 = THUMB_WHEEL
    mid = (ty0 + ty1) / 2
    tw = rect_on_flank(ty0, ty1, inset=9)
    tw_top = rect_on_flank(ty0, mid, inset=9)
    tw_bot = rect_on_flank(mid, ty1, inset=9)
    ridges = []
    for y in sample(ty0 + 14, ty1 - 14, 7):
        x1 = left_edge(y) + 12
        x2 = flank_inner(y) - 12
        ridges.append(f'    <line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" '
                      f'y2="{y:.1f}"/>')
    ridges = "\n".join(ridges)

    # ── boton de MODOS, junto al clic izquierdo ───────────────────────────────
    # Aqui habia tres "botones de perfil" apilados en el flanco, y estaban mal por
    # dos motivos. Primero, de sitio: el raton tiene UN boton de modos y va al lado
    # del clic izquierdo, largo y estriado, separado del boton por una junta.
    # Segundo, de concepto: el informe del software original lista los controles
    # programables del R.A.T.9 y son SEIS (scroll click, precision aim, forwards,
    # backwards, thumb CCW, thumb CW). Los "tres modos" eran botones de la VENTANA
    # del software (el selector rojo/azul/purpura), no piezas del raton: pintarlos
    # sobre el aparato era inventarselos. Y como caian encima de la rueda del
    # pulgar (ambos ocupaban y 398-516), las cinco llamadas se apelotonaban.
    _mzid, usage_modo, _my0, _my1, _n = MODE_BTN
    my0, my1 = PLATE_Y0 + 26, PLATE_Y0 + 152
    ys_modo = sample(my0, my1, 9)
    modo_d = band_shape([(left_edge(y) + 3, y) for y in ys_modo],
                        [(left_edge(y) + 3 + MODE_BTN_HW, y) for y in reversed(ys_modo)])
    modo_estr = "\n".join(
        f'    <line x1="{left_edge(y) + 6:.1f}" y1="{y:.1f}" '
        f'x2="{left_edge(y) + MODE_BTN_HW:.1f}" y2="{y:.1f}" '
        f'stroke="#3a4761" stroke-width="1"/>'
        for y in sample(my0 + 12, my1 - 12, 7))
    mode_svg = f'''  <g class="z" data-zone="mode" data-usage="{usage_modo}"
     tabindex="0" role="button" aria-label="Botón de modos">
    <path class="hit" d="{modo_d}" fill="#252f3d" stroke="#0b0e14"
          stroke-width="2" stroke-linejoin="round"/>
    {modo_estr}
  </g>'''

    # ── detalles: junta del reposamanos, escala de ajuste, labio de la ranura
    seam_y = PALM_Y0 + 96
    palm_seam = (f"M {flank_inner(seam_y) + 10:.0f} {seam_y:.0f} "
                 f"Q {CX:.0f} {seam_y + 12:.0f} "
                 f"{right_edge(seam_y) - 16:.0f} {seam_y - 6:.0f}")
    scale_y = PALM_Y0 + 214
    sx0, sx1 = flank_inner(scale_y) + 78, right_edge(scale_y) - 48
    ticks = "\n".join(
        f'  <line x1="{x:.1f}" y1="{scale_y - (12 if i % 5 == 0 else 7):.1f}" '
        f'x2="{x:.1f}" y2="{scale_y:.1f}"/>'
        for i, x in enumerate(sample(sx0, sx1, 11)))
    scale_line = (f'  <line x1="{sx0:.1f}" y1="{scale_y:.1f}" '
                  f'x2="{sx1:.1f}" y2="{scale_y:.1f}"/>')
    channel_lip = (f"M {wx0 - 15:.0f} {WHEEL_Y0 - 8:.0f} "
                   f"Q {eje:.0f} {WHEEL_Y0 - 17:.0f} {wx1 + 15:.0f} "
                   f"{WHEEL_Y0 - 8:.0f}")
    wheel_ridges = "\n".join(
        f'    <line x1="{wx0 + 14:.0f}" y1="{y:.1f}" x2="{wx1 - 4:.0f}" '
        f'y2="{y:.1f}"/>'
        for y in sample(WHEEL_Y0 + 18, WHEEL_Y1 - 18, 5))

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 800"
     class="mouse-diagram" role="img"
     aria-label="Diagrama del Mad Catz R.A.T.9, vista superior esquemática">
<title>R.A.T.9 — controles</title>
{SVG_STYLE}

<defs>
  <linearGradient id="g-shell" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="var(--mg-shell-hi)"/>
    <stop offset="60%" stop-color="var(--mg-shell)"/>
  </linearGradient>
  <linearGradient id="g-plate" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="var(--mg-plate-hi)"/>
    <stop offset="100%" stop-color="var(--mg-plate)"/>
  </linearGradient>
  <linearGradient id="g-flank" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="var(--mg-gap)"/>
    <stop offset="100%" stop-color="var(--mg-recess)"/>
  </linearGradient>

  <!-- Banda de luz diagonal: da volumen al cuerpo sin fingir un 3D.
       Los valores estan SUBIDOS a proposito: la primera version iba al 8% de
       opacidad y sobre un fondo oscuro no se veia nada. -->
  <linearGradient id="g-luz" x1="0.12" y1="0" x2="0.88" y2="1">
    <stop offset="0%"   stop-color="#ffffff" stop-opacity="0"/>
    <stop offset="36%"  stop-color="#ffffff" stop-opacity=".17"/>
    <stop offset="52%"  stop-color="#ffffff" stop-opacity=".075"/>
    <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
  </linearGradient>

  <!-- Filo iluminado: de claro arriba a nada. Es el canto achaflanado de una
       pieza cogiendo la luz, y es lo que separa "esquema" de "ilustracion". -->
  <linearGradient id="g-filo" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%"   stop-color="#ffffff" stop-opacity=".5"/>
    <stop offset="24%"  stop-color="#ffffff" stop-opacity=".26"/>
    <stop offset="70%"  stop-color="#ffffff" stop-opacity="0"/>
  </linearGradient>

  <!-- Oclusion: oscurece los bordes de una pieza, que es como se lee el volumen -->
  <radialGradient id="g-oclusion" cx="0.5" cy="0.45" r="0.62">
    <stop offset="50%"  stop-color="#000000" stop-opacity="0"/>
    <stop offset="100%" stop-color="#000000" stop-opacity=".68"/>
  </radialGradient>
</defs>

<!-- casco -->
<path d="{shell}" fill="url(#g-shell)" stroke="#3a4761" stroke-width="1.6"/>
<!-- banda de luz: el cuerpo deja de ser una silueta plana -->
<path d="{shell}" fill="url(#g-luz)"/>

<!-- panel lateral izquierdo: la superficie donde vive el pulgar.
     Sin textura de cepillado: probada, competia con los controles y a este
     tamano parecia una trama grafica, no un acabado. -->
<path d="{flank}" fill="url(#g-flank)"/>

<!-- reposamanos: la oclusion en los bordes es lo que le da forma -->
<path d="{palm}" fill="#1e2632"/>
<path d="{palm}" fill="url(#g-oclusion)"/>
<!-- estructura del reposamanos: junta de ajuste y escala grabada -->
<g stroke="#2b3543" stroke-width="1" fill="none">
  <path d="{palm_seam}"/>
  {scale_line}
{ticks}
</g>

<!-- botones principales -->
<g class="z" data-zone="btn-left" data-usage="1" tabindex="0" role="button"
   aria-label="Botón izquierdo">
  <path class="hit" d="{plate('l')}" fill="url(#g-plate)" stroke="#0b0e14"
        stroke-width="2"/>
  <path d="{filo_placa('l')}" fill="none" stroke="url(#g-filo)"
        stroke-width="1.8"/>
</g>
<g class="z" data-zone="btn-right" data-usage="2" tabindex="0" role="button"
   aria-label="Botón derecho">
  <path class="hit" d="{plate('r')}" fill="url(#g-plate)" stroke="#0b0e14"
        stroke-width="2"/>
  <path d="{filo_placa('r')}" fill="none" stroke="url(#g-filo)"
        stroke-width="1.8"/>
</g>

<!-- costuras funcionales: separacion de botones y de reposamanos -->
<g stroke="#2b3543" stroke-width="1">
  <line x1="{eje:.0f}" y1="{PLATE_Y0 + 5:.0f}" x2="{eje:.0f}"
        y2="{PLATE_Y1 - 8:.0f}"/>
  <line x1="{flank_inner(PALM_Y0) + 3:.0f}" y1="{PALM_Y0:.0f}"
        x2="{right_edge(PALM_Y0) - 3:.0f}" y2="{PALM_Y0:.0f}"/>
</g>

<!-- canal y rueda central -->
<path d="{channel}" fill="#080a0f"/>
<path d="{channel_lip}" fill="none" stroke="#3d4a5f" stroke-width="1.3"/>
<g class="z" data-zone="btn-scroll" data-usage="3" tabindex="0" role="button"
   aria-label="Clic de la rueda">
  <rect class="hit" x="{wx0:.0f}" y="{WHEEL_Y0:.0f}"
        width="{2 * WHEEL_X_HALF:.0f}" height="{WHEEL_Y1 - WHEEL_Y0:.0f}" rx="14"
        fill="#151a23" stroke="#0b0e14" stroke-width="1.6"/>
  <!-- luz lateral: es lo que hace que se lea como un cilindro y no como una rejilla -->
  <rect x="{wx0 + 3:.0f}" y="{WHEEL_Y0 + 5:.0f}" width="7"
        height="{WHEEL_Y1 - WHEEL_Y0 - 10:.0f}" rx="3.5" fill="#39465a"
        opacity=".7"/>
  <!-- reflejo especular arriba: el brillo de una superficie cilindrica -->
  <ellipse cx="{(wx0 + wx1) / 2:.0f}" cy="{WHEEL_Y0 + 18:.0f}"
           rx="{WHEEL_X_HALF - 7:.0f}" ry="7" fill="#ffffff" opacity=".32"/>
  <g stroke="#2f3a4c" stroke-width="1.2" opacity=".9">
{wheel_ridges}
  </g>
</g>

<!-- controles del panel lateral -->
{side_svg}

<!-- rueda del pulgar -->
<path d="{tw}" fill="var(--recess)" stroke="#3a4761" stroke-width="1.3"/>
<g class="z" data-zone="thumb-cw" data-usage="{u_cw}" tabindex="0" role="button"
   aria-label="Rueda del pulgar · horaria">
  <path class="hit" d="{tw_top}" fill="#252f3d" stroke="#0b0e14"
        stroke-width="1.6"/>
</g>
<g class="z" data-zone="thumb-ccw" data-usage="{u_ccw}" tabindex="0"
   role="button" aria-label="Rueda del pulgar · antihoraria">
  <path class="hit" d="{tw_bot}" fill="#252f3d" stroke="#0b0e14"
        stroke-width="1.6"/>
</g>
<g stroke="#39465a" stroke-width="1" opacity=".4">
{ridges}
</g>

<!-- botones de perfil -->
{mode_svg}
<!-- llamadas numeradas: el numero es el uso HID que reporta el firmware -->
<g id="badges">
{svg_badges()}
</g>
</svg>
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    here = Path(__file__).resolve().parent.parent
    ap.add_argument("--out", default=str(here / "rat9/ui/diagram-mouse.svg"))
    ap.add_argument("--out-capa",
                    default=str(here / "rat9/ui/diagram-overlay.svg"),
                    help="segunda capa, ya ajustada al render")
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    # El contorno medido sobre la imagen, si existe, manda sobre el perfil
    # inventado: es lo que hace que el dibujo y la imagen encajen.
    global _CONTORNO, _EJE
    ruta_sil = here / "rat9/ui/silueta.json"
    if ruta_sil.is_file():
        cont = json.loads(ruta_sil.read_text())
        _CONTORNO = cont
        _EJE = _eje_medido(cont)
        print(f"contorno medido de {cont['origen']} ({cont['medido']}): "
              f"eje del cuerpo x = {_EJE:.0f}")

    svg = tokenizar_cuerpo(build_svg())
    out.write_text(svg)
    zones = svg.count('class="z"')
    print(f"escrito: {out}  ({len(svg)} bytes, {zones} zonas)")
    # la capa para el render sale del MISMO dibujo: si se cambia uno, cambian
    # los dos, y no pueden desincronizarse
    if a.out_capa:
        capa = Path(a.out_capa)
        encaje = cargar_encaje(here)
        capa.write_text(envolver_para_imagen(svg, encaje))
        print(f"escrito: {capa}  (capa para {encaje.get('imagen', 'el render')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
