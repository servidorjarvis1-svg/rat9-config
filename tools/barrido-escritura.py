#!/usr/bin/env python3
"""Barrido ACOTADO del canal de escritura del raton.

Por que existe: el descriptor HID del aparato (leido con `lsusb -v`) dice que solo
tiene informes de ENTRADA — 13 botones, X, Y y rueda — y **ningun informe de feature
ni de salida**. Por eso el SET_REPORT "se aceptaba" y no pasaba nada: no hay ningun
informe donde escribir. Y el canal de lectura (control IN 0xC0/0x90) es de solo
lectura. El unico camino fisico que queda es un CONTROL TRANSFER de endpoint 0.

Aqui se prueban unas pocas combinaciones de (bmRequestType, bRequest) y se apunta
cuales responde el aparato SIN dar PIPE. La mayoria daran PIPE: eso tambien es
informacion.

DELIBERADAMENTE ACOTADO, y no un barrido de 256 valores, por una razon concreta:
entre los comandos del driver hay uno que GUARDA EN EEPROM (IOCTL 3369). Un barrido a
ciegas podria darle. Aqui se prueban solo los candidatos que salen del analisis:

    0x90  el bRequest de LECTURA (el gemelo de direccion)
    0xB8  el tercer comando del driver, junto al 0x90, en el camino del DPI
    0x91  el de la wiki de MayeulC (ya se probo y da PIPE; se repite por completitud)
    0x09  SET_REPORT de la clase HID
    0x00  control vacio, por si el aparato usa el bRequest como indice

Y en el primer pase se manda **wValue 0, wIndex 0 y SIN datos**: solo interesa cual
ACEPTA el aparato, no escribir nada. Con eso no se cambia ningun ajuste.

    python3 tools/barrido-escritura.py            # solo mira quien acepta
    python3 tools/barrido-escritura.py --dpi 1600 # ya con el valor real
"""
from __future__ import annotations

import argparse
import sys
import time

VID, PID = 0x0738, 0x1709
TIPOS = (0x40, 0x41, 0x01, 0x21)      # vendor/dev, vendor/intf, standard/intf, clase/intf
BREQS = (0x90, 0xB8, 0x91, 0x09, 0x00)


def indice(dpi: int) -> int:
    return max(0, min(255, dpi // 25 - 1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dpi", type=int,
                    help="si se da, manda el valor real en los que acepten")
    a = ap.parse_args()

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
        desenganchado = False
        try:
            h.detachKernelDriver(0)
            desenganchado = True
        except Exception:                                # noqa: BLE001
            pass
        h.claimInterface(0)

        # lectura de control, para saber que el aparato responde ANTES de nada
        try:
            d = h.controlRead(0xC0, 0x90, 0, 0x00BA, 2, timeout=1500)
            print(f"  control de lectura OK (bateria {d[0]}%)")
        except Exception as e:                           # noqa: BLE001
            print(f"  el canal de LECTURA no responde ({e}). Me paro.")
            h.close()
            return 1

        # ── PASE 1: quien ACEPTA (wValue 0, wIndex 0, sin datos) ──────────────
        print("\n  PASE 1 — quien acepta (sin escribir nada):")
        print("    bmReq  bReq  |  resultado")
        aceptan = []
        for tipo in TIPOS:
            for breq in BREQS:
                try:
                    h.controlWrite(tipo, breq, 0, 0, b"", timeout=1500)
                    r = "ACEPTA"
                    aceptan.append((tipo, breq))
                except Exception as e:                   # noqa: BLE001
                    r = str(e).split(":")[-1].strip()
                print(f"    0x{tipo:02X}   0x{breq:02X}  |  {r}")
                time.sleep(0.02)

        if not aceptan:
            print("\n  NINGUNA combinacion acepta. El aparato solo escucha por el")
            print("  canal de lectura y por sus comandos de driver de Windows.")
        elif not a.dpi:
            print(f"\n  aceptan: {[(hex(t), hex(b)) for t, b in aceptan]}")
            print("  (repite con --dpi <valor> para meter el valor de verdad)")
        else:
            # ── PASE 2: con el valor real, solo en las que aceptaron ──────────
            i = indice(a.dpi)
            print(f"\n  PASE 2 — dpi={a.dpi} (indice {i}, 0x{i:02x}) en las que aceptan:")
            for eje, nom in ((0x100, "X"), (0x200, "Y")):
                w = eje | i
                for tipo, breq in aceptan:
                    carga = bytes([0x90, w & 0xFF, (w >> 8) & 0xFF, 0, 0]) + bytes(3)
                    for desc, payload in (("sin datos", b""),
                                          ("con los 5 bytes", carga)):
                        try:
                            h.controlWrite(tipo, breq, w, 0, payload, timeout=1500)
                            print(f"    eje {nom} 0x{tipo:02X}/0x{breq:02X} "
                                  f"wValue=0x{w:04X} {desc} -> OK")
                        except Exception as e:           # noqa: BLE001
                            print(f"    eje {nom} 0x{tipo:02X}/0x{breq:02X} "
                                  f"{desc} -> {e}")
                        time.sleep(0.03)

        try:
            h.releaseInterface(0)
        except Exception:                                # noqa: BLE001
            pass
        if desenganchado:
            try:
                h.attachKernelDriver(0)
                print("\n  driver del kernel reenganchado")
            except Exception as e:                       # noqa: BLE001
                print(f"\n  no he podido reenganchar el driver ({e}): "
                      "desenchufar y volver a enchufar")
        h.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
