#!/usr/bin/env python3
"""Lee el DESCRIPTOR HID del raton para saber de que tamano son sus informes.

Por que: el "aceptado" del intento anterior no demuestra nada — el aparato puede
tragarse un feature report de 8 bytes y no hacerle caso. Lo que manda el descriptor
que el propio raton declara: cuantos bytes tiene cada informe y con que ID. Sin ese
dato se esta adivinando el tamano.

Es una LECTURA estandar (GET_DESCRIPTOR / HID), no toca el estado del aparato.
"""
from __future__ import annotations

import sys

VID, PID = 0x0738, 0x1709
TIPO_HID, DESC_REPORT = 0x22, 0x2200


def main() -> int:
    try:
        import usb1
    except ImportError:
        print("falta python-libusb1", file=sys.stderr)
        return 2

    with usb1.USBContext() as ctx:
        dev = next((d for d in ctx.getDeviceList(skip_on_error=True)
                    if d.getVendorID() == VID and d.getProductID() == PID), None)
        if dev is None:
            print("no encuentro el raton 0738:1709")
            return 1
        h = dev.open()

        # el descriptor de configuracion dice en que interfaz esta la clase HID
        interfaces = []
        try:
            for cfg in dev.iterConfigurations():
                for it in cfg:
                    if it.getClass() == 3:             # HID
                        interfaces.append(it.getNumber())
        except Exception as e:                          # noqa: BLE001
            print(f"  (no he podido leer la configuracion: {e})")
        print(f"  interfaces HID: {interfaces}")

        for num in interfaces:
            try:
                h.claimInterface(num)
            except Exception as e:                      # noqa: BLE001
                print(f"  interfaz {num}: no la puedo reclamar ({e})")
                continue
            for idx in (0, 1, 2):
                try:
                    d = h.controlRead(0x81, 0x06, DESC_REPORT | idx, num, 4096,
                                      timeout=2000)
                except Exception:                       # noqa: BLE001
                    continue
                print(f"\n  === descriptor de informes de la interfaz {num}, "
                      f"indice {idx}: {len(d)} bytes ===")
                analizar(d)
            h.releaseInterface(num)
        h.close()
    return 0


def analizar(d: bytes) -> None:
    """Recorre el descriptor y saca los informes de FEATURE (los que nos importan)."""
    i = 0
    tam = {0: {"in": 0, "out": 0, "feat": 0}}
    id_actual = 0
    usos = []
    while i < len(d):
        b = d[i]
        if b == 0xFE:                                  # long item
            i += 3 + (d[i + 1] if i + 1 < len(d) else 0)
            continue
        tag, tipo = (b >> 4) & 0x0F, (b >> 2) & 0x03
        ln = b & 0x03
        ln = 4 if ln == 3 else ln
        datos = d[i + 1:i + 1 + ln]
        val = int.from_bytes(datos, "little") if datos else 0
        if tipo == 1 and tag == 8:                     # Report ID
            id_actual = val
            tam.setdefault(id_actual, {"in": 0, "out": 0, "feat": 0})
        elif tipo == 0 and tag == 8:                   # Input
            tam.setdefault(id_actual, {"in": 0, "out": 0, "feat": 0})["in"] += val
        elif tipo == 2 and tag == 8:                   # Output
            tam.setdefault(id_actual, {"in": 0, "out": 0, "feat": 0})["out"] += val
        elif tipo == 3 and tag == 8:                   # Feature
            tam.setdefault(id_actual, {"in": 0, "out": 0, "feat": 0})["feat"] += val
        elif tipo == 0 and tag == 4:                   # Usage
            usos.append(val)
        i += 1 + ln
    print("    ID de informe | in | out | FEATURE (bits)")
    for rid in sorted(tam):
        t = tam[rid]
        marca = "  <-- FEATURE" if t["feat"] else ""
        print(f"      {rid:>3}       | {t['in']:>3} | {t['out']:>3} | {t['feat']:>4}"
              f"  ({t['feat'] // 8} bytes){marca}")
    if usos:
        print(f"    usos vistos (primeros 12): {usos[:12]}")


if __name__ == "__main__":
    raise SystemExit(main())
