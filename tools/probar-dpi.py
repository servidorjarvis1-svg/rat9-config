#!/usr/bin/env python3
"""Prueba del comando de ESCRITURA del DPI, sacado del driver.

De donde sale el comando: del desensamblado de `_hid_0738_1709.sys`, en la funcion
que aplica el DPI al aparato (0x2a61c). Alli se ve, literalmente:

    mov    $0x100,%r8d        ; eje X
    mov    $0x90,%edx         ; bRequest
    or     %ax,%r8w           ; wValue = 0x100 | indice
    call   0x148f4            ; se envia

    mov    $0x200,%r8d        ; eje Y
    mov    $0x90,%edx
    or     %ax,%r8w           ; wValue = 0x200 | indice

con `indice = (dpi - minimo) / paso`. Con el minimo y el paso que ya estaban en el
README (`DPI = byte1 * 25 + 25`), sale `indice = dpi / 25 - 1`.

O sea: bRequest 0x90 — EL MISMO QUE EL DE LECTURA — y el eje codificado en los bits
altos del wValue. Eso explica por que fallaron las pruebas anteriores: se probo el
vendor OUT con bRequest 0x91 y daba PIPE. Nunca se probo 0x40 con 0x90.

SEGURIDAD, y esto no es retorica:
  - El `SetDpi` normal es DE SESION. Guardar en EEPROM es otra llamada (IOCTL 3369) y
    NO se manda aqui. Si esto funciona, al desenchufar el raton vuelve a lo suyo.
  - Hay que hacer detachKernelDriver(0) antes de claimInterface(0). Eso puede dejar el
    nodo hidraw huerfano hasta reconectar el raton. Si el raton deja de responder:
    desenchufar y volver a enchufar. Al final se intenta reenganchar el driver solo.

    python3 tools/probar-dpi.py                 # SOLO LEE (seguro, por defecto)
    python3 tools/probar-dpi.py --escribir 1600 # escribe el DPI (prueba real)
"""
from __future__ import annotations

import argparse
import sys
import time

VID, PID = 0x0738, 0x1709
BM_READ = 0xC0          # vendor, host->device IN
BM_WRITE = 0x40         # vendor, host->device OUT
BREQ = 0x90             # el MISMO bRequest para leer y para escribir
EJE_X, EJE_Y = 0x100, 0x200


def indice(dpi: int) -> int:
    """El driver normaliza (dpi - minimo) / paso; con el README da dpi/25 - 1."""
    return max(0, min(255, dpi // 25 - 1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--escribir", type=int, metavar="DPI",
                    help="escribe este DPI en los dos ejes (si no, solo lee)")
    ap.add_argument("--tiempo", type=float, default=1500, help="timeout en ms")
    ap.add_argument("--metodo", choices=("informe", "control"), default="informe",
                    help="informe = feature report (0x21/0x09/0x0300), el canal "
                         "confirmado en este raton; control = vendor OUT 0x40")
    a = ap.parse_args()

    try:
        import usb1
    except ImportError:
        print("falta python-libusb1:  sudo pacman -S python-libusb1", file=sys.stderr)
        return 2

    with usb1.USBContext() as ctx:
        dev = None
        for d in ctx.getDeviceList(skip_on_error=True):
            if d.getVendorID() == VID and d.getProductID() == PID:
                dev = d
                break
        if dev is None:
            print("no encuentro el raton 0738:1709. Esta enchufado?")
            return 1
        print(f"  dispositivo: {dev.getVendorID():04x}:{dev.getProductID():04x} "
              f"bus {dev.getBusNumber()} dir {dev.getDeviceAddress()}")

        h = dev.open()
        desenganchado = False
        try:
            h.detachKernelDriver(0)
            desenganchado = True
        except Exception as e:                       # noqa: BLE001
            print(f"  (detachKernelDriver no hizo falta o fallo: {e})")
        h.claimInterface(0)
        print("  interfaz 0 reclamada")

        # ── LECTURA, para confirmar que el canal responde antes de tocar nada ──
        for nom, idx in (("bateria", 0x00BA), ("perfil", 0x0074)):
            try:
                d = h.controlRead(BM_READ, BREQ, 0, idx, 2, timeout=a.tiempo)
                print(f"  lectura {nom:8s} (wIndex 0x{idx:04X}): {list(d)}")
            except Exception as e:                   # noqa: BLE001
                print(f"  lectura {nom:8s}: FALLO {e}")

        if not a.escribir:
            print("\n  (solo lectura: no se ha enviado nada). "
                  "Para probar la escritura: --escribir <dpi>")
        else:
            i = indice(a.escribir)
            print(f"\n  ESCRIBIENDO dpi={a.escribir} -> indice={i} (0x{i:02x})")

            if a.metodo == "control":
                # Primer intento: control transfer OUT con el mismo bRequest que lee.
                # RESULTADO REAL: PIPE (-9) en los dos ejes. El aparato NO lo acepta.
                for eje, nom in ((EJE_X, "X"), (EJE_Y, "Y")):
                    w = eje | i
                    try:
                        h.controlWrite(BM_WRITE, BREQ, w, 0, b"", timeout=a.tiempo)
                        print(f"    eje {nom}: control OUT wValue=0x{w:04X} -> OK")
                    except Exception as e:           # noqa: BLE001
                        print(f"    eje {nom}: control OUT FALLO ({e})")
                    time.sleep(0.05)
            else:
                # Segundo intento, y el que tiene sentido: el MENSAJE DE 5 BYTES del
                # driver {cmd:u8, w1:u16, w2:u16} metido DENTRO del feature report, que
                # es el canal que este ratón SÍ acepta (0x21 / 0x09 / wValue 0x0300).
                # cmd = bRequest (0x90), w1 = wValue (eje|indice), w2 = wIndex (0).
                for eje, nom in ((EJE_X, "X"), (EJE_Y, "Y")):
                    w = eje | i
                    carga = bytes([BREQ, w & 0xFF, (w >> 8) & 0xFF,
                                   0x00, 0x00]) + bytes(3)      # 8 bytes
                    try:
                        h.controlWrite(0x21, 0x09, 0x0300, 0, carga, timeout=a.tiempo)
                        print(f"    eje {nom}: feature {list(carga)} -> Aceptado")
                    except Exception as e:           # noqa: BLE001
                        print(f"    eje {nom}: feature FALLO ({e})")
                    time.sleep(0.05)

            # ── LA COMPROBACION QUE MANDA: leer el perfil otra vez ──
            print("\n  comprobando si el aparato lo acepta...")
            try:
                d = h.controlRead(BM_READ, BREQ, 0, 0x0074, 2, timeout=a.tiempo)
                print(f"    perfil tras escribir: {list(d)}")
            except Exception as e:                   # noqa: BLE001
                print(f"    no he podido releer: {e}")

        # OJO con el ORDEN: hay que SOLTAR la interfaz antes de reenganchar el driver
        # del kernel. Al revés da LIBUSB_ERROR_BUSY(-6) y el nodo hidraw se queda
        # huérfano (síntoma: el ratón "desaparece" hasta reconectarlo).
        try:
            h.releaseInterface(0)
        except Exception:                            # noqa: BLE001
            pass
        if desenganchado:
            try:
                h.attachKernelDriver(0)
                print("\n  driver del kernel reenganchado")
            except Exception as e:                   # noqa: BLE001
                print(f"\n  OJO: no he podido reenganchar el driver ({e}).")
                print("  Si el raton no responde: desenchufar y volver a enchufar.")
        h.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
