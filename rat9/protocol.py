"""
rat9.protocol — capa de bajo nivel del protocolo USB del Mad Catz R.A.T.9.

Todo verificado contra hardware (0738:1709) el 2026-10-13.

ARQUITECTURA DE REGISTROS
=========================
    bRequest 0x90 (144) = LEER registro     (bmRequestType 0xC0)
    bRequest 0x91 (145) = ESCRIBIR registro  (bmRequestType 0x40)
    wIndex = direccion del registro, construida con CAMPOS DE BITS:

        wIndex = 0x1000 * modo      (1..4, los cuatro perfiles del RAT9)
               + 0x0100 * eje       (1 = X, 2 = Y)
               + base

    Bases de registro conocidas:
        0x0073  valor DPI      2 bytes, DPI = byte1 * 25 + 25
        0x0074  perfil activo  byte0 >> 4
        0x00BA  bateria        byte0

    Valores DPI por defecto de fabrica (verificados):
        perfil 1 = 800    perfil 2 = 1600
        perfil 3 = 3200   perfil 4 = 6400

ESCRITURA
=========
El driver de Windows (hid.sys, offsets 0x14d44 / 0x1FC34) despacha la escritura
como mensajes de 5 bytes {cmd, w1:u16, w2:u16} dentro de un URB propietario
propio {Length=0x88, Function=0x17}, que un filtro USB inferior (SaiUsb) los
convierte en el transporte fisico. Por eso el vendor OUT directo (0x40) da PIPE:
no es la via que usa el raton para esto.

Parametros reconstruidos del driver (NO verificados en hardware):
    escribir DPI por modo:  bRequest 0x91, wValue = 0x1000*m + 0x0100*eje + raw,
                            wIndex = 0x0073
    guardar en EEPROM:      bRequest 0x91, wValue = 0x0051, wIndex = 0x0070
    reset a fabrica:        bRequest 0x91, wValue = 0x0000, wIndex = 0x0073
    cambiar de perfil:      bRequest 0x91, wValue = modo << 12, wIndex = 0x0070

Una hipotesis alternativa del analisis estatico (wValue = 0x100|raw, wIndex 0x90)
se probo y NO responde en lectura, asi que se descarto.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import usb1

VID = 0x0738
PID = 0x1709

REQ_READ = 0x90    # bRequest 144
REQ_WRITE = 0x91   # bRequest 145

REG_DPI = 0x0073
REG_MODE = 0x0074
REG_BATTERY = 0x00BA

MODE_BITS = 0x1000
AXIS_BITS = 0x0100
AXIS_X, AXIS_Y = 1, 2
N_MODES = 4
# Pasos de 25 y minimo 25: confirmado con el software original, que ajustaba el
# DPI en multiplos de 25 y arrancaba en 25. Antes poniamos 100, que era inventado.
DPI_MIN, DPI_MAX = 25, 6400

# Escritura (del driver de Windows; NO verificada en hardware).
# Nota: el raton rechaza el vendor OUT directo (0x40) con PIPE, asi que
# set_dpi() probablemente no funcione tal cual. Ver docstring.
W_IDX_SAVE = 0x0070
W_VAL_SAVE = 0x0051

PROFILE_HEADER = bytes([0, 0, 0, 1, 0xFF, 0xFF, 0xFF, 0xFF, 0, 0])
REPORT_SIZE = 16

FACTORY_DPI = {1: 800, 2: 1600, 3: 3200, 4: 6400}


class Rat9Error(RuntimeError):
    pass


def reg(mode: int = 0, axis: int = 0, base: int = REG_DPI) -> int:
    """Construye la direccion de registro: 0x1000*modo + 0x100*eje + base."""
    return MODE_BITS * mode + AXIS_BITS * axis + base


def dpi_encode(dpi: int) -> int:
    """Inversa de DPI = raw*25 + 25."""
    return (dpi - 25) // 25


def dpi_decode(raw: int) -> int:
    return raw * 25 + 25


@dataclass
class Status:
    mode: int | None = None
    battery: int | None = None


@dataclass
class DpiSetting:
    mode: int
    axis: int
    dpi: int | None

    @property
    def axis_name(self) -> str:
        return {AXIS_X: "X", AXIS_Y: "Y"}.get(self.axis, "?")


class Rat9:
    """Sesion sobre el raton. Requiere root para los control transfers."""

    def __init__(self, claim: bool = True):
        self.ctx = usb1.USBContext()
        try:
            self.dev = self.ctx.openByVendorIDAndProductID(VID, PID)
        except usb1.USBError as e:
            raise Rat9Error(
                f"No encuentro {VID:04X}:{PID:04X} o sin permiso ({e.value}). "
                "Se necesita root para los control transfers."
            ) from e
        self._claimed = False
        if claim:
            self.claim()

    # -- ciclo de vida ------------------------------------------------------

    def claim(self) -> None:
        """Reclama la interfaz HID. REQUIERE detachKernelDriver antes.

        IMPORTANTE: deja el nodo hidraw huerfano y el driver hid-saitek del
        kernel no se re-enlaza solo. Si el raton deja de responder,
        desconectalo y reconectalo. El firmware NO queda alterado.
        """
        if self._claimed:
            return
        try:
            self.dev.detachKernelDriver(0)
        except usb1.USBError:
            pass
        try:
            self.dev.claimInterface(0)
        except usb1.USBError as e:
            raise Rat9Error(
                f"No se pudo reclamar la interfaz ({e.value}). "
                "Si es BUSY(-6), el driver hid-saitek tiene la interfaz: "
                "desenchufa y enchufa el raton."
            ) from e
        self._claimed = True

    def release(self) -> None:
        if not self._claimed:
            return
        try:
            self.dev.releaseInterface(0)
        except usb1.USBError:
            pass
        self._claimed = False

    def close(self) -> None:
        self.release()
        for fn in (lambda: self.dev.close(), lambda: self.ctx.close()):
            try:
                fn()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- lectura ------------------------------------------------------------

    def _read(self, index: int, length: int = 4) -> bytes | None:
        try:
            return bytes(self.dev.controlRead(
                0xC0, REQ_READ, 0, index, length, timeout=1000))
        except usb1.USBError:
            return None

    def battery(self) -> int | None:
        """Porcentaje de bateria. None si el firmware devuelve basura."""
        r = self._read(REG_BATTERY, 2)
        return r[0] if r and r[0] <= 100 else None

    def mode(self) -> int | None:
        """Perfil/modo activo (1..4)."""
        r = self._read(REG_MODE, 2)
        return (r[0] >> 4) or None if r else None

    def status(self) -> Status:
        return Status(mode=self.mode(), battery=self.battery())

    def read_dpi(self, mode: int, axis: int) -> int | None:
        """DPI configurado para (modo, eje). Se lee del byte 1."""
        r = self._read(reg(mode, axis, REG_DPI), 4)
        return dpi_decode(r[1]) if r and len(r) > 1 else None

    def all_dpi(self) -> list[DpiSetting]:
        return [DpiSetting(m, a, self.read_dpi(m, a))
                for m in range(1, N_MODES + 1)
                for a in (AXIS_X, AXIS_Y)]

    # -- escritura ----------------------------------------------------------

    def _write(self, request: int, value: int, index: int) -> int:
        try:
            return self.dev.controlWrite(
                0x40, request, value, index, b"\x00" * 8, timeout=2000)
        except usb1.USBError as e:
            raise Rat9Error(
                f"Escritura fallo (req={request:#04x} val={value:#06x} "
                f"idx={index:#06x}): {e.value}") from e

    def set_dpi(self, mode: int, axis: int, dpi: int, commit: bool = True):
        """Cambia el DPI de un (modo, eje).

        ADVERTENCIA: los parametros salen del driver de Windows y aun no se
        han verificado contra hardware. Commitea solo si se verifica.
        """
        if not (DPI_MIN <= dpi <= DPI_MAX):
            raise Rat9Error(f"DPI fuera de rango: {dpi} (valido {DPI_MIN}-{DPI_MAX})")
        value = MODE_BITS * mode + AXIS_BITS * axis + dpi_encode(dpi)
        self._write(REQ_WRITE, value, REG_DPI)
        if commit:
            self._write(REQ_WRITE, W_VAL_SAVE, W_IDX_SAVE)

    def save(self) -> None:
        """Persiste la configuracion en la memoria del raton."""
        self._write(REQ_WRITE, W_VAL_SAVE, W_IDX_SAVE)

    def write_report(self, data: bytes) -> int:
        """SET_REPORT HID, report ID 0. Devuelve bytes enviados."""
        data = bytes(data)
        try:
            return self.dev.controlWrite(
                0x21, 0x09, 0x0300, 0x0000, data, timeout=2000)
        except usb1.USBError as e:
            raise Rat9Error(f"SET_REPORT fallo: {e.value}") from e

    def write_profile(self, xml: str, dry: bool = False):
        """Empaqueta un perfil XML y lo envia en bloques de REPORT_SIZE.

        Buffer = cabecera de 10 bytes + XML en UTF-16LE (TorontoDevice.SetProfile).
        dry=True devuelve los bloques sin escribir nada.
        """
        payload = PROFILE_HEADER + xml.encode("utf-16-le")
        frames = [payload[i:i + REPORT_SIZE]
                  for i in range(0, len(payload), REPORT_SIZE)]
        if dry:
            return frames
        for f in frames:
            self.write_report(f + bytes(REPORT_SIZE - len(f)))
            time.sleep(0.02)
        return frames
