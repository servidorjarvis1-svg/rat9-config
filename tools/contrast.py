#!/usr/bin/env python3
"""Comprueba el contraste WCAG de los tokens de color de rat9-config.

Existe porque en la hoja de tokens se afirma que los cuatro niveles de texto
pasan AA. Una afirmacion asi, sin comprobarla, es exactamente el tipo de cosa
que se cuela y luego resulta falsa. Esto la comprueba.

Lee los tokens oklch() de rat9/ui/css/tokens.css, los pasa a sRGB con las
matrices oficiales de OKLab (Bjorn Ottosson), calcula la luminancia relativa de
la WCAG y saca el ratio de cada texto sobre cada superficie.

    python3 tools/contrast.py                 # matriz completa
    python3 tools/contrast.py --text AA       # solo lo que debe pasar AA
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENS = ROOT / "rat9" / "ui" / "css" / "tokens.css"

OKLCH_RE = re.compile(
    r"(--[a-z0-9-]+)\s*:\s*oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\)\s*;",
    re.IGNORECASE)

# umbrales WCAG 2.2
AA_NORMAL = 4.5
AA_LARGE = 3.0      # tambien: bordes e iconos que comunican estado (1.4.11)


def oklch_to_srgb(L: float, C: float, H: float) -> tuple[float, float, float]:
    """OKLCH -> sRGB (0..1), con las matrices de Ottosson."""
    h = math.radians(H)
    a, b = C * math.cos(h), C * math.sin(h)

    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b

    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3

    r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s

    def gamma(x: float) -> float:
        x = max(0.0, min(1.0, x))
        return 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055

    return gamma(r), gamma(g), gamma(bb)


def luminance(L: float, C: float, H: float) -> float:
    """Luminancia relativa WCAG de un color oklch."""
    r, g, b = oklch_to_srgb(L, C, H)

    def lin(x: float) -> float:
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def ratio(c1, c2) -> float:
    a, b = luminance(*c1), luminance(*c2)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def hex_of(c) -> str:
    return "#" + "".join(f"{round(v * 255):02X}" for v in oklch_to_srgb(*c))


def load_tokens(path: Path) -> dict[str, tuple[float, float, float]]:
    txt = path.read_text()
    out = {}
    for name, L, C, H in OKLCH_RE.findall(txt):
        out[name] = (float(L), float(C), float(H))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokens", default=str(TOKENS))
    ap.add_argument("--only", choices=["AA", "none"], default="none",
                    help="AA: solo la matriz texto x superficie")
    a = ap.parse_args()

    tok = load_tokens(Path(a.tokens))
    if not tok:
        sys.exit("no he podido leer ningun token oklch()")

    surfaces = [k for k in tok if k.startswith("--bg-")]
    texts = [k for k in tok if k.startswith("--text-") or
             k in ("--accent-400", "--accent-500", "--ok", "--warn", "--danger")]
    surfaces.sort()
    texts.sort(key=lambda k: -luminance(*tok[k]))

    print(f"tokens oklch leidos: {len(tok)}  ({len(surfaces)} superficies, "
          f"{len(texts)} colores de texto)\n")

    print("── texto x superficie (AA normal = 4.5, texto grande = 3.0) ──")
    head = "  ".join(f"{s.replace('--', ''):>8}" for s in surfaces)
    print(f"{'':<14}{head}")
    fallos = []
    for t in texts:
        cells = []
        for s in surfaces:
            r = ratio(tok[t], tok[s])
            mark = "ok" if r >= AA_NORMAL else ("gr" if r >= AA_LARGE else "XX")
            cells.append(f"{r:5.2f}{mark:>3}")
            if r < AA_NORMAL and s == "--bg-1":
                fallos.append((t, s, r))
        print(f"{t:<14}" + "  ".join(f"{c:>8}" for c in cells))

    print("\n  ok = pasa AA normal   gr = solo AA para texto grande (>=18.7px "
          "negrita / 24px)   XX = no pasa ninguno")

    print("\n── valores en hexadecimal, para comprobarlos en otra herramienta ──")
    for k in surfaces + ["--accent-500", "--accent-600"]:
        print(f"  {k:<16} {hex_of(tok[k])}")

    print()
    if fallos:
        print("FALLO: estos colores de texto no pasan AA normal sobre --bg-1:")
        for t, s, r in fallos:
            print(f"  {t} sobre {s}: {r:.2f}")
        return 1
    print("VEREDICTO: los cuatro niveles de texto pasan AA normal sobre --bg-1.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
