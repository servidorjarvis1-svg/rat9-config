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

## 6. Lo que FALTA, y por qué

**El perfil viaja por IOCTL al driver de Windows, y el troceado en mensajes USB lo
hace el driver, no el userland.** Por eso aquí no aparece: está en
`_hid_0738_1709.sys` (180 KB, kernel x64), no en el .NET.

Lo que se sabe del driver por los strings y el análisis previo: manda al dispositivo
**mensajes de 5 bytes `{cmd:u8, w1:u16, w2:u16}`** dentro de su propio URB
(`{Length=0x88, Function=0x17}`). Cerrar el dispatcher de ahí es lo que falta para
poder enviar un perfil desde Linux sin adivinar.

Alternativas, por orden de sensatez:
1. **Terminar de leer el driver** (`objdump`/`radare2` sobre el .sys) para sacar los
   `cmd` y el significado de `w1`/`w2`. Es la vía limpia y no toca el ratón.
2. **Capturar el USB de verdad** mientras el software manda un perfil. Necesita un
   Windows con el ratón conectado; Wine no sirve porque el software depende de un
   driver de kernel.
3. **Probar a ciegas** por el canal `SET_REPORT` ya confirmado con el candidato
   `CommandSetFeature + DeviceProfileProgramming`. Es la vía más rápida y la más
   arriesgada: **nunca enviar la orden de guardar en EEPROM** hasta tener el framing
   verificado, y tener presente que `detachKernelDriver` puede dejar el `hidraw`
   huérfano hasta reconectar el ratón.
