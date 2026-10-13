#!/usr/bin/env python3
"""CLI de rat9-config. Requiere root para control transfers."""
import argparse
import sys
import time

from rat9.protocol import (Rat9, Rat9Error, REPORT_SIZE, AXIS_X, AXIS_Y,
                            N_MODES, FACTORY_DPI)
from rat9.schema import MINIMAL_PROFILE


def cmd_status(m):
    with Rat9(claim=False) as r:
        s = r.status()
        print(f"  Perfil activo : {s.mode}")
        print(f"  Bateria       : {s.battery if s.battery is not None else '?'}%")


def cmd_dpi(m):
    with Rat9(claim=False) as r:
        print(f"  {'Perfil':>7} {'Eje':>4} {'DPI':>7}   (fabrica: {FACTORY_DPI.get(int(m.mode), '?') if m.mode else '-'})")
        for d in r.all_dpi():
            mark = ""
            if m.mode and d.mode == int(m.mode):
                mark = "  <- activo"
            print(f"  {d.mode:>7} {d.axis_name:>4} "
                  f"{str(d.dpi) if d.dpi else '?':>7}{mark}")


def cmd_frames(m):
    xml = m.xml if m.xml else MINIMAL_PROFILE
    with Rat9(claim=False) as r:
        frames = r.write_profile(xml, dry=True)
    print(f"Perfil: {len(xml)} chars -> {len(xml)*2} bytes UTF-16 + 10 cabecera")
    print(f"Bloques de {REPORT_SIZE} bytes: {len(frames)}\n")
    for i, f in enumerate(frames):
        pad = f + bytes(REPORT_SIZE - len(f))
        print(f"  {i:3} util={len(f):2}  {pad.hex(' ')}")


def cmd_send(m):
    xml = m.file and open(m.file).read() or MINIMAL_PROFILE
    if not xml.startswith("["):
        print("El perfil debe empezar por '[' (formato pr0)", file=sys.stderr)
        sys.exit(2)
    print(f"Enviando perfil ({len(xml)} chars)...\n"
          "AVISO: escribe en el raton. Si se cuelga el raton, "
          "desenchufa y enchufa.")
    with Rat9() as r:
        before = r.status()
        print(f"  antes : perfil={before.mode} bateria={before.battery}")
        n = len(r.write_profile(xml))
        print(f"  enviado: {n} bloques de {REPORT_SIZE} bytes")
        time.sleep(0.5)
        after = r.status()
        print(f"  despues: perfil={after.mode} bateria={after.battery}")
    print("\nSi el raton no responde, desconectalo y reconectalo.")
    print("El firmware no queda alterado: los bloques son de sesion.")


def cmd_scan(m):
    """Solo lectura: rastrea que indices responden."""
    from rat9.protocol import REQ_READ
    with Rat9(claim=False) as r:
        hits = []
        for idx in range(0x00, 0x100):
            if r._read(idx, 2) is not None:
                hits.append(idx)
        print(f"Indices que responden con bRequest {REQ_READ:#04x}:")
        for i in hits:
            v = r._read(i, 4)
            print(f"  {i:#06x} -> {v.hex(' ') if v else '-'}")
        if not hits:
            print("  ninguno")


def main():
    ap = argparse.ArgumentParser(description="rat9-config")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="perfil y bateria").set_defaults(fn=cmd_status)
    sub.add_parser("scan", help="indices que responden (solo lectura)").set_defaults(fn=cmd_scan)

    dp = sub.add_parser("dpi", help="DPI de los 4 perfiles (solo lectura)")
    dp.add_argument("--mode", type=int, choices=range(1, N_MODES + 1),
                    help="resalta el perfil activo")
    dp.set_defaults(fn=cmd_dpi)

    f = sub.add_parser("frames", help="empaqueta un perfil sin escribir")
    f.add_argument("--xml", help="perfil en formato pr0")
    f.set_defaults(fn=cmd_frames)

    s = sub.add_parser("send", help="ESCRIBE un perfil en el raton")
    s.add_argument("--file", help="fichero .pr0")
    s.set_defaults(fn=cmd_send)

    m = ap.parse_args()
    try:
        m.fn(m)
    except Rat9Error as e:
        sys.exit(f"ERROR: {e}")


if __name__ == "__main__":
    main()
