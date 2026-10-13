"""
rat9.protocol — capa de bajo nivel del protocolo USB del Mad Catz R.A.T.9.

Todo lo de aquí está VERIFICADO contra hardware (0738:1709) el 2026-10-13.
Ver ~/.hermes/notes/rat9-protocol-verified-2026-10-13.md

Canales:
  LECTURA   control transfer IN, bmRequestType 0xC0, bRequest 0x90
  ESCRITURA HID SET_REPORT, bmRequestType 0x21, bRequest 0x09, report ID 0
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import usb1

VID = 0x0738
PID = 0x1709

# --- índices de lectura descubiertos ---------------------------------------
IDX_PROFILE = 0x0074   # byte 0 >> 4 = perfil/modo activo (0x10 = modo 1)
IDX_BATTERY = 0x00BA   # byte 0 = porcentaje de batería

REQ_READ = 0x90         # bRequest 144

# --- cabecera del perfil (TorontoDevice.SetProfile) ------------------------
PROFILE_HEADER = bytes([0, 0, 0, 1, 0xFF, 0xFF, 0xFF, 0xFF, 0, 0])

REPORT_SIZE = 16        # bytes útiles por SET_REPORT (verificado: acepta 8..64)


class Rat9Error(RuntimeError):
    pass


@dataclass
class Status:
    profile: int | None
    battery: int | None


class Rat9:
    """Sesion sobre el raton. Requiere root para control transfers."""

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

        IMPORTANTE: si haces esto, el nodo hidraw puede quedar huerfano y el
        driver hid-saitek del kernel no se re-enlaza solo. Llama a release()
        al terminar, o deja que el usuario desconecte/reconecte el raton.
        """
        if self._claimed:
            return
        try:
            self.dev.detachKernelDriver(0)
        except usb1.USBError:
            pass  # ya estaba suelto, o no hay driver
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
        """Suelta la interfaz. Intenta que el kernel recupere el raton."""
        if not self._claimed:
            return
        try:
            self.dev.releaseInterface(0)
        except usb1.USBError:
            pass
        self._claimed = False

    def close(self) -> None:
        self.release()
        try:
            self.dev.close()
        except Exception:
            pass
        try:
            self.ctx.close()
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
        r = self._read(IDX_BATTERY, 2)
        return r[0] if r else None

    def profile(self) -> int | None:
        """Perfil/modo activo (1..N)."""
        r = self._read(IDX_PROFILE, 2)
        return (r[0] >> 4) or None if r else None

    def status(self) -> Status:
        return Status(profile=self.profile(), battery=self.battery())

    # -- escritura ----------------------------------------------------------

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
        for i, f in enumerate(frames):
            self.write_report(f + bytes(REPORT_SIZE - len(f)))
            time.sleep(0.02)
        return frames
