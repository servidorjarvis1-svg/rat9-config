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
MODE_BTN = ("mode", 9, 424, 500, 3)              # uso base, y0, y1, cuantos

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


def body_half(y: float) -> float:
    return lerp_profile(PROFILE, y)


def left_edge(y: float) -> float:
    """Borde izquierdo real: el cuerpo, o la aleta si sobresale."""
    body = CX - body_half(y)
    if WING[0][0] <= y <= WING[-1][0]:
        return min(body, lerp_profile(WING, y))
    return body


def right_edge(y: float) -> float:
    return CX + body_half(y)


def flank_inner(y: float) -> float:
    """Borde interior del panel lateral."""
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
  }
  .mouse-diagram .badge text {
    fill: var(--mg-ink); font-family: ui-monospace, monospace;
    font-weight: 600; letter-spacing: .02em;
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


# Llamadas numeradas: el numero es el USO HID, que es lo que reporta el
# firmware. Van DENTRO de la zona cuando cabe, y si no, fuera con linea guia
# hasta el control (como las callouts del software original).
#   (uso, x_marca, y_marca, x_destino, y_destino)  destino None = va dentro
BADGES = [
    (1,  243, 190, None, None),   # boton izquierdo
    (2,  335, 190, None, None),   # boton derecho
    (3,  280, 276, None, None),   # clic de la rueda
    (4,   78, 373, 112, 373),     # atras
    (5,  116, 303, 152, 303),     # adelante
    (6,   70, 424, 100, 424),     # rueda del pulgar, un sentido
    (7,   70, 488, 100, 488),     # rueda del pulgar, otro sentido
    (8,  136, 205, 170, 205),     # precision
    (9,  262, 434, None, None),   # perfil 1
    (10, 262, 462, None, None),   # perfil 2
    (11, 262, 490, None, None),   # perfil 3
]
BADGE_R = 15.0


def svg_badges() -> str:
    out = []
    for uso, bx, by, tx, ty in BADGES:
        guia = ""
        if tx is not None:
            guia = (f'  <line x1="{bx + BADGE_R:.0f}" y1="{by:.0f}" '
                    f'x2="{tx:.0f}" y2="{ty:.0f}" stroke="var(--mg-guide)" '
                    f'stroke-width="1.4"/>\n'
                    f'  <circle cx="{tx:.0f}" cy="{ty:.0f}" r="3.5" '
                    f'fill="var(--mg-guide)"/>\n')
        out.append(
            f'{guia}  <g class="badge">\n'
            f'    <circle cx="{bx:.0f}" cy="{by:.0f}" r="{BADGE_R:.0f}" '
            f'fill="var(--mg-badge-bg)" stroke="var(--mg-badge-edge)" '
            f'stroke-width="1.6"/>\n'
            f'    <text x="{bx:.0f}" y="{by + 5:.0f}" text-anchor="middle" '
            f'font-size="14">{uso:02d}</text>\n'
            f'  </g>')
    return "\n".join(out)


def build_svg() -> str:
    # ── silueta ──────────────────────────────────────────────────────────────
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
        inner = [(CX - 3, y) for y in reversed(ys)] if side == "l" else \
                [(CX + 3, y) for y in reversed(ys)]
        return band_shape(outer, inner)

    # ── panel lateral ────────────────────────────────────────────────────────
    flank_ys = [y for y in ys_right if y >= 96]
    flank = band_shape(
        [(left_edge(y), y) for y in flank_ys],
        [(flank_inner(y), y) for y in reversed(flank_ys)])

    # ── rueda central ────────────────────────────────────────────────────────
    wx0, wx1 = CX - WHEEL_X_HALF, CX + WHEEL_X_HALF
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

    # ── botones de perfil ────────────────────────────────────────────────────
    _mzid, usage_base, my0, my1, n = MODE_BTN
    mh = (my1 - my0) / n
    mode_svg = []
    for i in range(n):
        a, b = my0 + i * mh + 2, my0 + (i + 1) * mh - 2
        x1, w, h = flank_inner(a) + 8, 34.0, b - a
        mode_svg.append(
            f'''  <g class="z" data-zone="mode-{i + 1}" data-usage="{usage_base + i}"
     tabindex="0" role="button" aria-label="Modo {i + 1}">
    <rect class="hit" x="{x1:.1f}" y="{a:.1f}" width="{w:.1f}" height="{h:.1f}"
          rx="6" fill="url(#g-plate)"/>
    <rect x="{x1 + 4:.1f}" y="{a + 2.5:.1f}" width="{w - 8:.1f}" height="3"
          rx="1.5" fill="#3d4a5f" opacity=".65"/>
    <text class="lbl" x="{x1 + w / 2:.1f}" y="{a + h / 2 + 4:.1f}"
          text-anchor="middle" font-size="11">{i + 1}</text>
  </g>''')
    mode_svg = "\n".join(mode_svg)

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
                   f"Q {CX:.0f} {WHEEL_Y0 - 17:.0f} {wx1 + 15:.0f} "
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
</defs>

<!-- casco -->
<path d="{shell}" fill="url(#g-shell)" stroke="#3a4761" stroke-width="1.6"/>

<!-- panel lateral izquierdo: la superficie donde vive el pulgar -->
<path d="{flank}" fill="url(#g-flank)"/>

<!-- reposamanos -->
<path d="{palm}" fill="#1e2632"/>

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
</g>
<g class="z" data-zone="btn-right" data-usage="2" tabindex="0" role="button"
   aria-label="Botón derecho">
  <path class="hit" d="{plate('r')}" fill="url(#g-plate)" stroke="#0b0e14"
        stroke-width="2"/>
</g>

<!-- costuras funcionales: separacion de botones y de reposamanos -->
<g stroke="#2b3543" stroke-width="1">
  <line x1="{CX:.0f}" y1="{PLATE_Y0 + 5:.0f}" x2="{CX:.0f}"
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
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    svg = tokenizar_cuerpo(build_svg())
    out.write_text(svg)
    zones = svg.count('class="z"')
    print(f"escrito: {out}  ({len(svg)} bytes, {zones} zonas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
