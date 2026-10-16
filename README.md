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
| `rat9/app.py` + `rat9/ui/` | ✅ app de escritorio (GTK4 + WebKit) con cuatro vistas del aparato |
| `rat9/web/` | ✅ editor visual de macros, panel de DPI, vista .pr0 |
| Escribir DPI | ❌ documentado, sin verificar |
| Enviar perfil al ratón | ❌ framing sin respaldo binario (ver abajo) |
| Modelo 3D del aparato | ❌ **cerrado**: el material no da (ver `docs/research/informe-3d.md`) |

## Protocolo (todo verificado contra el ratón)

**Lectura** — control transfer IN, `bmRequestType 0xC0`, `bRequest 0x90`, `wValue 0`:

| wIndex | Devuelve |
|---|---|
| `0x0074` | perfil/modo activo (`byte0 >> 4`) |
| `0x00BA` | batería (el firmware puede dar valores corruptos: validar 0–100) |
| `0x000B` | `0x0001` — **sin identificar**. Solo responde a longitud 2, y falla si se le ponen los bits de modo/eje. |

Ningún otro índice responde en todo el rango `0x00`–`0xFF` (verificado con `cli.py scan`).

La batería es fiable de verdad, pero el firmware suelta basura de forma
intermitente: ocho lecturas seguidas dan 96 % y una aislada puede dar un valor
inválido. `battery()` ya descarta lo que se sale de 0–100, así que la interfaz
nunca debe mostrar un número crudo.

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

**No hace falta root.** Las reglas udev (`99-rat9.rules`, en este repo) dan los
nodos USB, hidraw y de entrada del ratón al grupo `rat9`. Para instalarlas:

```bash
sudo install -m 644 99-rat9.rules /etc/udev/rules.d/99-rat9.rules
sudo udevadm control --reload && sudo udevadm trigger
```

```bash
# solo lectura (seguro)
python3 -m rat9.cli status
python3 -m rat9.cli scan
python3 -m rat9.cli dpi --mode 1

# empaquetar sin escribir
python3 -m rat9.cli frames --xml '[profile …]'

# ESCRIBIR en el ratón (todavía sin verificar)
python3 -m rat9.cli send --file perfiles/mi-perfil.pr0
```

Editor de macros:
```bash
python3 -m rat9.server 8766
# → http://127.0.0.1:8766/editor/editor.html
```
Permite crear macros (teclas, botones, rueda, multimedia), organizarlas en bloques
`press`/`repeat`/`release`, elegir modo abierto o cerrado, y generar el `.pr0`.

### La app de escritorio

```bash
/usr/bin/python3 -m rat9.app                  # ventana GTK4 + WebKit
/usr/bin/python3 -m rat9.app --vista giro     # abrir en una vista concreta
```

El banco de la izquierda tiene **cuatro vistas** del aparato:

- **Esquema** — dibujo vectorial generado, con las zonas clicables. No está puesto
  a ojo: el contorno y las costuras se **miden sobre el render original**
  (`tools/trazar-silueta.py`, `tools/trazar-interior.py`) y el generador traza
  sobre esas medidas.
- **Producto** — el render cenital del software original.
- **Las dos capas** — el plano superpuesto a la fotografía.
- **Giro** — los 24 fotogramas reales del aparato, arrastrables: el ratón gira de
  verdad. Es lo mismo que hacía el software de Mad Catz, que tampoco era 3D sino
  una ruleta de sprites. Los fotogramas no van en el repositorio (son material
  gráfico ajeno): se sacan del instalador con `tools/preparar-giro.sh`, y si no
  están el botón simplemente no se ofrece.

Un apunte de método: `?medir=1` en la URL hace que la página escriba los tamaños
reales de los elementos en pantalla. Existe porque un modelo de visión no mide y el
navegador no avisa de un elemento que sale diminuto — lo pinta pequeño y calla.

## Las llamadas del esquema

Las nueve llamadas siguen el lenguaje del software original: caja achaflanada,
línea con codo y punto de anclaje sobre la pieza. Tres detalles que no son
decoración:

- Van **ordenadas por la altura de su anclaje**, no por número: si no, una llamada
  alta baja hasta una pieza baja y cruza por delante de todas las de abajo.
- Las cajas y las líneas van **por detrás del cuerpo** y solo el punto de anclaje
  por delante. Dibujadas encima tapaban justo lo que señalan.
- Una **rueda** no se dibuja como un botón ni se señala con un punto: su cuerpo es
  una cápsula con degradado transversal (oscuro en los cantos, claro en la cresta)
  y su marca es un arco con punta, porque gira en dos sentidos.

## Requisitos

```bash
sudo pacman -S python-libusb1        # API usb1, NO pyusb
```

Para la app de escritorio (ventana nativa con la interfaz dentro):

```bash
sudo pacman -S gtk4 libadwaita webkitgtk-6.0
```

## Acceso al ratón sin root

`99-rat9.rules` da los tres nodos del ratón al grupo `rat9`:

```
SUBSYSTEM=="usb",    ATTR{idVendor}=="0738", ATTR{idProduct}=="1709", MODE="0660", GROUP="rat9"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="0738", ATTRS{idProduct}=="1709", MODE="0660", GROUP="rat9"
SUBSYSTEM=="input",  ATTRS{idVendor}=="0738", ATTRS{idProduct}=="1709", MODE="0660", GROUP="rat9"
```

Dos trampas que costaron una sesión de depuración, y que hay que respetar si se
reescriben:

- El nodo `/dev/bus/usb/BBB/DDD` lo crea el dispositivo udev `usb_device`, cuyo
  `KERNEL` es la ruta bus-puerto (`1-1`), **nunca** `"usb"`. Una regla con
  `KERNEL=="usb"` no coincide jamás: hay que filtrar por `SUBSYSTEM`.
- En hidraw el `KERNEL` lleva sufijo numérico (`hidraw4`), así que
  `KERNEL=="hidraw"` tampoco coincide: va `hidraw*`.

Y la distinción `ATTR` (atributo del propio dispositivo USB) frente a `ATTRS`
(recorre hacia el padre): en el nodo USB van los `idVendor`/`idProduct` del
dispositivo, pero en hidraw e input son del padre USB.

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
