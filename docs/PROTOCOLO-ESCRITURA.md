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

## 7. Lo que queda exactamente

1. **Los valores de `cmd`** y el significado de `w1`/`w2` en cada operación. Se sacan
   siguiendo las ramas del dispatcher que construyen el mismo búfer de 5 bytes
   (el camino de `Module_Programming` para el perfil).
2. **Cómo van montados los 5 bytes dentro del feature report**: si el report es de 8,
   16 o 64 bytes, y si hay prefijo. El `Capabilities.FeatureReportByteLength` del
   aparato lo dice, y se puede leer sin escribir nada.
3. Una vez con eso: **probar con el ratón**, empezando por algo visible y reversible.

**Nada de esto se ha probado todavía contra el hardware.** Todo lo de esta sección es
análisis estático: código desensamblado, sin tocar el aparato.

