# rat9-config

Configurador Linux para el Mad Catz R.A.T.9 (`0738:1709`), construido por ingeniería
inversa del software oficial de Windows (Mad Catz Software 7.0.45.2).

## Estado

| Módulo | Estado |
|---|---|
| `rat9/protocol.py` | ✅ verificado contra hardware (lectura DPI, batería, perfil) |
| `rat9/schema.py` | ✅ esquema oficial + catálogo de macros + constructores |
| `rat9/pr0.py` | ✅ parser y generador del formato `.pr0` (round-trip verificado) |
| `rat9/cli.py` | ✅ `status`, `dpi`, `scan`, `frames`, `send` |
| `rat9/server.py` | ✅ API + servidor de estáticos |
| `rat9/web/` | ✅ editor visual de macros, panel de DPI, vista .pr0 |
| Escribir DPI | ❌ documentado, sin verificar |
| Enviar perfil al ratón | ❌ framing sin respaldo binario (ver abajo) |

## Protocolo (todo verificado contra el ratón)

**Lectura** — control transfer IN, `bmRequestType 0xC0`, `bRequest 0x90`, `wValue 0`:

| wIndex | Devuelve |
|---|---|
| `0x0074` | perfil/modo activo (`byte0 >> 4`) |
| `0x00BA` | batería (el firmware puede dar valores corruptos: validar 0–100) |

Ningún otro índice responde en todo el rango `0x00`–`0xFF`.

**Escritura** — HID `SET_REPORT`: `bmRequestType 0x21`, `bRequest 0x09`,
`wValue 0x0300` (report ID 0). Acepta payloads de 8 a 64 bytes.

⚠️ `detachKernelDriver(0)` es obligatorio antes de `claimInterface(0)`, pero deja
el nodo `hidraw` huérfano y el driver `hid-saitek` no se re-enlaza solo.
**Si el ratón deja de responder: desenchúfalo y enchúfalo.**
El firmware nunca queda alterado: los bloques son de sesión.

**Índices** — los registros están indexados por campos de bits:
```
wIndex = 0x1000 × modo (1-4) + 0x0100 × eje (X/Y) + base
```
con bases `0x73` (DPI), `0x74` (perfil activo), `0xBA` (batería).
`DPI = byte1 × 25 + 25`. Valores de fábrica: 800 / 1600 / 3200 / 6400.

**Formato del perfil** — no es XML. Es texto UTF-16LE con gramática de corchetes
`[tag[=nombre] attr=valor [hijo]]`, atributos uint en hexadecimal de 8 dígitos
(`0xXXXXXXXX`), y los valores por defecto no se escriben.

## Uso

```bash
# solo lectura (seguro)
sudo python3 -m rat9.cli status
sudo python3 -m rat9.cli scan

# empaquetar sin escribir
python3 -m rat9.cli frames --xml '[profile …]'

# ESCRIBIR en el ratón
sudo python3 -m rat9.cli send --file perfiles/mi-perfil.pr0
```

Editor de macros:
```bash
sudo python3 -m rat9.server 8766
# → http://127.0.0.1:8766/editor/editor.html
```
Permite crear macros (teclas, botones, rueda, multimedia), organizarlas en bloques
`press`/`repeat`/`release`, elegir modo abierto o cerrado, y generar el `.pr0`.

## Requisitos

```bash
sudo pacman -S python-libusb1        # API usb1, NO pyusb
```

## Lo que NO funciona (documentado para no perder tiempo)

- **DPI**: no hay ioctl en el driver kernel `hid-saitek` (solo arregla el botón de
  modo). No se puede leer por control transfer. La wiki de MayeulC/Saitek describe
  otro modelo — sus índices `0x73` dan PIPE aquí.
- Los vendor requests OUT (`0x40`/`0x91`) no funcionan.
- No existen feature reports HID (GET_REPORT).

## Procedencia

Ver **[PROVENANCE.md](PROVENANCE.md)** para el detalle completo de qué es nuestro y qué
viene del software original de Mad Catz.

En resumen: el software de Windows se recuperó de Internet Archive (el CDN de Mad Catz
está muerto desde el cierre de la empresa en 2020) y se descompiló con ILSpy — el userland
es .NET 2.0, `Profiler_x64` es C++ nativo. El esquema de perfil es el recurso embebido
`schema_sd.pr0` de `Saitek.Common.dll`.

El conocimiento previo viene de [MayeulC/Saitek](https://github.com/MayeulC/Saitek)
(GPLv3), que documentó el protocolo de los R.A.T. Saitek. Su wiki avisaba que el
`0738:1709` estaba sin confirmar — hemos confirmado que su protocolo de DPI **no aplica**
a este hardware, y que el canal real de escritura es distinto.

## Licencia

GPL-3.0. Ver [LICENSE](LICENSE) y [PROVENANCE.md](PROVENANCE.md).
