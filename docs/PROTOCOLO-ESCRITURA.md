# Protocolo de ESCRITURA — extraído del software original

Todo lo de este documento sale de **descompilar el software oficial** (Mad Catz
7.0.45.2, userland .NET 2.0). Se marca en cada punto si está **verificado contra el
hardware de esta unidad** o si solo está **extraído del código** (sin probar).

Ficheros de origen, extraídos de `Software_x64_fre_7_0_45_2.cab`:
`Saitek.Devices.dll` (la capa HID/USB), `Saitek.Common.dll` (esquema y perfiles) y
el plugin del dispositivo `Controllers_c9e4beb7…_x64_dll` (`CyborgMouse_V5`).

## 1. El canal físico — VERIFICADO

- **Escritura**: `HID SET_REPORT`, `bmRequestType 0x21`, `bRequest 0x09`,
  `wValue 0x0300` (report type 3 = Feature, report ID 0), `wIndex 0`.
  En .NET es `HidDevice.SetFeature()` → `HidD_SetFeature()`.
  La unidad lo acepta con payloads de 8 a 64 bytes. Report IDs 1 y 2 → PIPE.
- **Lectura**: control transfer IN `0xC0` / `bRequest 0x90` / `wValue 0`.
  `wIndex 0x00BA` = batería; `0x0074` = perfil activo (`byte0 >> 4`).
- **Los vendor requests OUT (0x40 / 0x91) NO funcionan** en esta unidad: PIPE.
- **No existen feature reports de lectura** (`GET_REPORT 0xA1`): los 12 report IDs
  probados fallan. Por eso todo lo de "leer" va por el canal de vendor requests.

## 2. La trama de un feature report — EXTRAÍDO DEL CÓDIGO

`Saitek.Devices`, clase `GroupedDevice` (y `SaitekDevice`):

```csharp
byte[] BuildPacket(FeatureId id) {
    var a = new byte[device.Capabilities.FeatureReportByteLength];
    a[0] = (byte)id;                       // byte 0: QUÉ se manda
    return a;
}

int SendGroupCommand(HidDevice device, Instruction instruction, Command command, byte[] data) {
    var a = BuildPacket(device, FeatureId.GroupCommands);
    a[1] = (byte)instruction;              // byte 1: instrucción
    a[2] = (byte)command;                  // byte 2: comando
    if (data != null) Array.Copy(data, 0, a, 3, data.Length);   // del 3 en adelante
    return device.SetFeature(a);
}
```

O sea: **`[0]=FeatureId · [1]=instrucción · [2]=comando · [3..]=datos`**.

## 3. Los identificadores — EXTRAÍDOS DEL CÓDIGO

```csharp
public enum FeatureId : byte {
    CommandSetFeature = 1,  BatteryLevel  = 2,  MouseDpiByte    = 3,
    MouseDpiMode      = 4,  MouseSetDpiLock = 5, LedTimeout      = 6,
    AcButtonMapping   = 7,  DeviceGroup   = 8,  GroupCommands   = 9,
    DeadBanding       = 10, AxisResponseCurve = 11, Brightness  = 12,
    ProfileSelect     = 13, MouseDpiUShort = 14, MousePrecisionAim = 15,
    PowerSavingMode   = 16, AxisSensivity = 17, MouseDpiRecord  = 18,
    SleepTimeout      = 19, FirmwareRevision = 21, PollRate     = 22,
    AngleSnap         = 23, MouseSensitivity = 24
}

public enum Instruction : byte { SetValue = 0, BroadcastValue = 1, GetValue = 2 }

public enum CommandSetFeatureCommands : byte {
    Save = 1, SendHidReport = 2, DeviceProfileProgramming = 3,
    FirmwareUpdateMode = 4, ButtonMapping = 5, FeatureMapping = 6
}
```

`DeviceProfileProgramming` es el candidato natural a ser el envío de perfil por USB
(los nombres son los del propio fabricante).

## 4. El DPI — EXTRAÍDO DEL CÓDIGO (interfaz de Windows)

En Windows el DPI **no** va por feature report: va por `DeviceIoControl` al driver.

| función | IOCTL (`CtlCode(n)`) | entrada | salida |
|---|---|---|---|
| leer nivel DPI | 3362 (`GetDpi`) | `[índice u32]` (4 B) | `[X u32][Y u32]` (8 B) |
| **escribir nivel DPI** | **3363** (`SetDpi`) | `[índice u32][X u32][Y u32]` (12 B) | — |
| leer/escribir ratón DPI | 3366 / 3367 | — | — |
| restablecer | 3368 | — | — |
| **guardar en EEPROM** | **3369** | — | — |
| precisión (X) | 3597 / 3598 | `[48,0,1,0]` + `[valor u32]` (8 B) | `[valor u32]` |
| precisión (Y) | 3597 / 3598 | `[49,0,1,0]` + `[valor u32]` (8 B) | `[valor u32]` |

Detalle que importa: los cuatro niveles de DPI se direccionan por `índice` (0..3) y
el valor va como **u32 en little-endian, X e Y por separado**. Y hay una llamada
**aparte** para escribir en EEPROM — es decir, el `SetDpi` normal es de sesión.

## 5. El perfil — EXTRAÍDO DEL CÓDIGO

`TorontoDevice.SetProfile(string)` (IOCTL `CtlCode(2560)`, `GetProfile` = 2561,
`ClearProfile` = 2562, `Activate` = 2563, `IsProfileActive` = 2570):

```
[0..3]   00 00 00 01        slot
[4..7]   FF FF FF FF        GUID / máscara universal
[8..9]   00 00
[10..]   XML del perfil en UTF-16LE
```

## 6. El driver: el mensaje de 5 bytes, CONFIRMADO en el código

Se desensambló `_hid_0738_1709.sys` (180.928 bytes, kernel x64, KMDF) y se siguió el
camino real de escritura. Lo que apareció es mejor de lo que se esperaba.

**La fórmula de los IOCTL** sale del propio userland:

```csharp
static uint CtlCode(uint code) => CtlCode(code, 34u, 0u, 0u);
static uint CtlCode(uint code, uint device, uint method, uint access)
    => (device << 16) | (access << 14) | (code << 2) | method;
```

Con eso, el código exacto de cada operación (útil para seguir el rastro en el driver):

| operación | code | IOCTL |
|---|---|---|
| `SetProfile` | 2560 | `0x00222800` |
| `GetProfile` | 2561 | `0x00222804` |
| `ClearProfile` / `Activate` | 2562 / 2563 | `0x00222808` / `0x0022280C` |
| `IsProfileActive` | 2570 | `0x00222828` |
| **`WriteVendorCommand`** | 2800 | `0x00222BC0` |
| `ReadVendorCommand` | 2801 | `0x00222BC4` |
| **`VendorInCommand`** | 2802 | `0x00222BC8` |
| `GetDpi` / `SetDpi` | 3362 / 3363 | `0x00223488` / `0x0022348C` |
| `ResetToDefaults` / `SaveDPIModesToEEPROM` | 3368 / 3369 | `0x002234A0` / `0x002234A4` |
| `Get/SetPrecisionPercent` | 3597 / 3598 | `0x00223834` / `0x00223838` |

El dispatcher del driver resta el IOCTL recibido y salta (`sub $0x222800,%r8d; je …`),
así que cada operación tiene su rama localizable.

### El hallazgo: `VendorInCommand` construye el mensaje de 5 bytes

En `0x14b60`, el manejador de `VendorInCommand` (el que manda un comando en crudo al
aparato) hace esto:

```asm
14b97: cmp    $0x5,%eax          ; exige tamaño EXACTAMENTE 5
14ba0: mov    (%r9),%al          ; byte 0    -> variable
14ba3: mov    %al,0x20(%rsp)
14ba7: movzwl 0x1(%r9),%eax      ; bytes 1-2 -> u16
14bac: mov    %ax,0x21(%rsp)
14bb1: movzwl 0x3(%r9),%eax      ; bytes 3-4 -> u16
14bb6: mov    %ax,0x23(%rsp)
```

Es decir: **`{cmd:u8, w1:u16, w2:u16}` — 5 bytes, little-endian, y exactamente 5, ni más
ni menos.** Lo que en sesiones anteriores era una sospecha sacada de los strings del
driver, aquí está confirmado en el código que habla con el aparato.

### El manejador de `SetProfile`

`0x1f0ee` → `0x1fc34`. Comprueba que el búfer tenga al menos 12 bytes, y luego:

- `(%r9)` → primer u32 = **slot**
- `0x4(%r12)` → segundo u32 = **máscara/GUID**
- `cmpw $0x1,0x8(%r12)` → u16 en el offset 8
- `lea 0xa(%r12),%r9` → **el XML empieza en el offset 10**

Eso **confirma la estructura del perfil** que se dedujo del .NET: `[slot u32][máscara
u32][2 bytes][XML UTF-16LE]`.

### Cómo se encadena con lo confirmado contra el hardware

El canal de escritura **verificado en la unidad** es `SET_REPORT` de feature report
(`0x21` / `0x09` / `wValue 0x0300`, report ID 0), que acepta de 8 a 64 bytes. El
mensaje del driver son 5 bytes: encaja en ese mismo report. O sea que las dos piezas
—el canal de transporte (verificado en hardware) y el contenido (confirmado en el
driver)— son compatibles.

## 7. El perfil NO se envía como bloque — y eso cambia el plan

Siguiendo el camino completo dentro del driver se llega a una conclusión que explica
por qué no aparecía por ningún lado un "envío del perfil":

- **`SetProfile`** (`0x1f0ee` → `0x1fc34`): comprueba el búfer, lee el slot y la
  máscara, y **parsea el XML**. Guarda el resultado. **No envía nada.**
- **`Activate`** (`0x1f042` → `0x1fea4` → `0x20038`): cambia una bandera del objeto
  (`0xa0`/`0xa1`/`0xa2`) y llama a una rutina de **contadores de referencias**. Tampoco
  envía nada al aparato.

Y el motivo se ve en los nombres de los módulos del driver: `Module_DPI_EE` (el DPI en
EEPROM), `Module_ReportModifier` (los bloques de macro), `Module_Programming`. **El
driver interpreta el perfil y programa el aparato ajuste a ajuste**: cada nivel de DPI,
cada mapeo de botón, cada macro, por separado. El perfil de 5 KB es una estructura del
host; al aparato solo le llegan los ajustes ya digeridos.

**Consecuencia práctica, y es buena**: para escribir desde Linux no hay que enviar
ningún perfil troceado. Hay que enviar **los ajustes sueltos**, que son comandos
pequeños — uno por feature report. Eso está al alcance, y encaja con el enum de
`FeatureId` que ya estaba sacado del .NET (`MouseDpiByte=3`, `MouseDpiUShort=14`,
`ProfileSelect=13`, `ButtonMapping=5`…).

## 8. El emisor y sus argumentos

El envío al aparato pasa por `0x201d8`: empaqueta una petición con **cuatro valores**
(offsets `0x8`, `0xc`, `0x10`, `0x14` del objeto) y la encola en WDF. Tiene cuatro
sitios que lo llaman, y tres de ellos pasan la **misma terna**:

```asm
mov  $0x2,%edx            ; arg2 = 2
mov  $0x300031,%r8d       ; arg3 = 0x300031
lea  -0x1(%rdx),%r9d      ; arg4 = 1
...  value en la pila      ; arg5 = el valor
call 0x201d8
```

`0x30` y `0x31` son **48 y 49**, que son exactamente los códigos de precisión X e Y
que ya estaban identificados en el .NET (`PrecisionX` usa el byte 48, `PrecisionY` el
49). O sea que el análisis estático y el descompilado **coinciden en el mismo número**,
que es la mejor señal de que la lectura es correcta.

## 9. Lo que queda exactamente

1. **Los comandos de ajuste sueltos**: el DPI (por nivel), el mapeo de botones, la
   selección de perfil y la luminosidad. Cada uno es un comando pequeño.
2. **Cómo van montados en el feature report**: el `Capabilities.FeatureReportByteLength`
   del aparato lo dice y se lee sin escribir nada.
3. Entonces sí: **probar contra el ratón**, empezando por algo visible y reversible
   (la luminosidad o un nivel de DPI), y **nunca** la orden de guardar en EEPROM hasta
   tener todo verificado.

## 10. El comando de escritura del DPI — ENCONTRADO

Se localizó el dispatcher del grupo DPI (`0x29d64`, `sub $0x223480`) y de ahí el
manejador de `SetDpi` (`0x22348C` → `0x2a30c`) y el de "aplicar al aparato"
(`0x2a61c`). **Aquí está el comando**, en ensamblador:

```asm
; ── EJE X ─────────────────────────────────────────────────────────────
2a65f: movzwl 0x4(%rdi),%eax     ; el DPI de X del registro (u16)
2a667: sub    0x30(%rbx),%ecx    ; resta el MÍNIMO
2a67d: divl   0x38(%rbx)         ; divide por el PASO  -> índice normalizado
2a684: mov    $0x100,%r8d        ; wValue alto = 0x100  (eje X)
2a68a: mov    $0x90,%edx         ; bRequest = 0x90
2a68f: or     %ax,%r8w           ; wValue = 0x100 | índice
2a693: call   0x148f4            ; ← SE ENVÍA

; ── EJE Y ─────────────────────────────────────────────────────────────
2a6c0: mov    $0x200,%r8d        ; wValue alto = 0x200  (eje Y)
2a6c6: mov    $0x90,%edx         ; bRequest = 0x90
2a6cb: or     %ax,%r8w           ; wValue = 0x200 | índice
2a6cf: call   0x148f4            ; ← SE ENVÍA

; ── un tercero ────────────────────────────────────────────────────────
2a6d4: movzwl 0x8(%rdi),%r8d     ; el campo +8 del registro
2a6dd: mov    $0xb8,%edx         ; bRequest = 0xB8
2a6e2: call   0x148f4            ; ← SE ENVÍA
```

Y `0x148f4` confirma que los dos argumentos son de 16 bits
(`movzwl %r8w,%esi` y `movzwl %dx,%ebp`) antes de montar la petición: o sea,
**wValue y bRequest**.

### Lo que dice esto

| operación | bmRequestType | bRequest | wValue |
|---|---|---|---|
| **fijar DPI, eje X** | (envío) | **`0x90`** | `0x100 \| índice` |
| **fijar DPI, eje Y** | (envío) | **`0x90`** | `0x200 \| índice` |
| campo +8 del registro | (envío) | `0xB8` | el valor |

donde `índice = (dpi − mínimo) / paso`, con el mínimo y el paso guardados en el objeto
del driver (`0x30` y `0x38`). Esa normalización encaja con el `DPI = byte1 × 25 + 25`
que ya estaba en el README.

**Y el dato gordo**: el `bRequest` **es el mismo `0x90` que el de lectura**. Lo único
que cambia es la dirección. Eso explica por qué en su día fallaron las pruebas de
escritura: se probó el vendor OUT con `bRequest 0x91` (el de la wiki de MayeulC) y
daba PIPE — **nunca se probó `0x40` con `bRequest 0x90`**, que es justo el gemelo de
dirección del que sí lee.

## 11. Lo que se midió contra el aparato — y la puerta que NO existe

Aquí se acaba el análisis estático y empiezan los hechos medidos. Cada uno es una
prueba contra el ratón conectado, y hay uno que **corrige** lo que se creía antes.

### El aparato no declara ningún informe de escritura

`lsusb -v` da el descriptor HID del ratón, y es de una claridad incómoda:

```
Report Descriptor: (length is 64)
  13 botones (13 bits) + 3 de relleno
  Direction-X, Direction-Y (16 bits cada uno)
  Wheel (8 bits)
  → TODO son informes de ENTRADA (Input)
bNumInterfaces 1 · bNumEndpoints 1 · Endpoint 0x81 IN (interrupción)
```

**Cero informes de feature. Cero informes de salida. Un solo endpoint, y es de
entrada.** No hay ningún sitio declarado donde meterle un ajuste al aparato.

### Corrección: "SET_REPORT es el canal de escritura" era FALSO

En su día se concluyó que el canal real de escritura era `SET_REPORT` (0x21 / 0x09 /
wValue 0x0300) porque el aparato **no devolvía PIPE**. Eso era leer mal la señal: el
aparato **acepta el transfer** y no hace nada con él, porque **no tiene ningún informe
de feature donde escribirlo**. Aceptar el sobre no es tener buzón.

Medición de hoy: el mismo `SET_REPORT` con `wValue 0` da PIPE (solo reconoce la forma
formal), y con `wValue 0x0300` y la carga de 5 bytes del driver **no cambia nada**.

### Los envíos de control dan PIPE, todos

Se barrieron 20 combinaciones de `bmRequestType` × `bRequest` y 42 direcciones:

| qué se probó | valores | resultado |
|---|---|---|
| `bmRequestType` | 0x40 (vendor/dev), 0x41 (vendor/intf), 0x01 (std), 0x21 (clase) | PIPE |
| `bRequest` | **0x90**, **0xB8**, 0x91, 0x09, 0x00 | PIPE |
| `wIndex` | 0x72–0x78, 0xBA, 0xBB, 0x172–0x174, 0x272–0x274, 0x1072–0x1074, 0x2072–0x2074 | PIPE |

**Ningún envío de control es aceptado.** Ninguno. Con ninguna dirección.

### Y la lectura sí va — y direcciona por `wIndex`

| wValue | wIndex | resultado |
|---|---|---|
| 0 | 0x00BA | ✓ responde (batería) |
| 0 | 0x0074 | ✓ responde (perfil) |
| 0 | **0x0000** | **PIPE** |
| ≠0 | 0x00BA | ✓ responde **e ignora el wValue** |
| ≠0 | 0x0000 | PIPE |

Dos cosas que se aprenden aquí y que costaron un rato: el aparato **direcciona todo
por el `wIndex`** (el `wValue` le da igual), y **`wIndex = 0` no es un registro
válido** — da PIPE incluso leyendo. O sea que los envíos que se probaron "a la
dirección 0" estaban condenados desde el principio, y eso se veía como si el canal
fuera el problema cuando era la dirección.

### Qué significa todo junto

El R.A.T.9, en su modo normal, **abre una puerta de lectura y ninguna de escritura**.
No es que no hayamos dado con la combinación: no hay ninguna combinación que el
firmware acepte.

Eso deja dos lecturas, y ninguna está demostrada:

1. **Que exista un modo de programación** al que haya que entrar primero — algo que
   encaja con el módulo `Module_Programming` del driver y con el registro de
   programación que aparece en la plantilla del propio driver (`0x1e2b8`). Entrar
   sería cosa de un `SET_REPORT` con la orden de conmutación, y a partir de ahí el
   aparato se dejaría escribir. **No comprobado.**
2. **Que la escritura no pase por aquí** — el R.A.T.9 es inalámbrico, y los ajustes
   pueden viajar por el enlace de radio en vez de por el USB, con el receptor
   limitándose a leer estado. En ese caso el único camino sería replicar lo que hace
   el driver de Windows, incluida su secuencia de inicialización, que no está
   reproducida.

Lo que sí está cerrado con medida: **la lectura funciona y está caracterizada**
(batería 92-93 %, perfil, registros por `wIndex`), y **la escritura directa no existe
en este modo**.

## 12. La lección de método que deja esto

Dos conclusiones se dieron por buenas en su día y las dos eran falsas, por la misma
razón: **se leyó un "no falla" como un "funciona"**.

- `SET_REPORT` no devolvía PIPE → "es el canal de escritura". No: acepta el sobre y no
  tiene buzón.
- Los envíos a `wIndex 0` daban PIPE → "el canal de escritura no está". No: era la
  dirección. `wIndex 0` da PIPE **hasta leyendo**.

Lo que vale aquí, y conviene no volver a olvidar: **un transfer aceptado no es un
efecto**, y **un PIPE no dice dónde está el fallo, solo que lo hay**. Para saber si algo
sirve hay que **medir el efecto** — y en este proyecto el efecto se mide mirando si el
ratón cambia, no si la llamada devuelve error.


