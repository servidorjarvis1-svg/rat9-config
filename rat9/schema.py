"""rat9.schema — el esquema del perfil XML del R.A.T.9.

Fuente: recurso embebido `schema_sd.pr0` de Saitek.Common.dll (v7.0.45.2),
extraido con ilspycmd. Define el lenguaje de macros completo.
"""

from __future__ import annotations

SCHEMA_PR0 = """\
[profile
  [controllers
    [controller min=1 guid=controller req=group
      [member min=1 guid=member req='name shortname']
      [controls num=1 notempty=true
        [axis key=axis req=name]
        [button key=button req=name]
        [hat key=hat req=name]
        [mousepointer :key=mousepointer req=name
          [mouseaxis key=mouseaxis req=name num=2]]
        [mouseaxis key=mouseaxis req=name]
        [slider :key=slider req=name
          [button min=3 key=button req=name]]
        [ministick :key=ministick req=name
          [button max=1 key=button req=name]
          [axis num=2 key=axis req=name]]]
      [shifts num=1
        [shift min=1 guid=shift req=name
          [selectionset max=1
            [buttoncombo
              [buttonhid key=buttonhid]]]
          [shiftcommand max=1]
          [assignments max=1
            [mouseaxis key=mouseaxis
                [directional max=1]]
            [mousepointer :key=mousepointer
              [mouseaxis key=mouseaxis min=1 max=2
                [sensitivity max=1]]]
            [axis key=axis
              [mouse-x max=1]
              [mouse-y max=1]
              [bands max=1
                [band quay=band]]
              [directional max=1]
              [sensitivity max=1]]
            [button key=button
              [bands max=1
                [band quay=band]]
              [report-as key=report-as]]
            [hat key=hat
              [mouse max=1]
              [bands max=1
                [band quay=band]]]
            [slider :key=slider
              [button min=1 max=3 key=button
                [bands max=1
                  [band quay=band]]
                [report-as key=report-as]]]
            [ministick :key=ministick
              [button key=button max=1
                [bands max=1
                  [band quay=band]]
                [report-as key=report-as]]
              [axis key=axis max=2
                [mouse-x max=1]
                [mouse-y max=1]
                [bands max=1
                  [band quay=band]]
                [directional max=1]
                [sensitivity max=1]]]]]]]]]
  [commands max=1
    [stringcommand guid=stringcommand req=name type=type data=data]
    [actioncommand guid=actioncommand req=name
      [actionblock min=1 max=3 quay=type
        [action]
        [string]]]]
  [blasts max=1
    [blast guid=blast data=data]]
  ]"""

# Nodos registrados en SaiNode.Schema.SD.Schema (60 tipos)
NODE_TYPES = [
    "Profile", "ControllerList", "Controller", "Member",
    "ControlList", "ControlSlider", "ControlMiniStick", "ControlAxis",
    "ControlButton", "ControlHat", "ControlMousePointer", "ControlMouseAxis",
    "Bands", "Mouse", "MouseX", "MouseY", "Directional", "Band",
    "ShiftList", "Shift", "ShiftCommand", "SelectionSet", "ButtonCombo",
    "AssignmentList", "CommandList", "CommandAction", "CommandString",
    "ActionBlock", "Action", "StringAction", "ButtonHid",
    "EnvelopeSensitivity", "ReportAs", "BlastList", "Blast",
    "CommandCycle", "CommandTemporal", "Cycle", "Temporal", "Envelope",
    "Event", "Map", "MapHat", "MapPedal", "Mapping", "MappingBase",
    "PersistEnvelopes", "PersistMappings", "PersistRole",
    "SensitivityNode", "NodeCommandAssignment", "NodeControl",
    "Schema", "SchemaBase",
]

# Tags XML confirmados en los strings del driver nativo Profiler_x64 (offset 0x45c48)
XML_TAGS = [
    "controls", "bands", "shift", "selectionset", "buttoncombo",
    "buttonhid", "assignments", "button", "band", "blast",
]

# Perfil mínimo válido según el esquema, para pruebas.
MINIMAL_PROFILE = (
    "[profile "
    "[controllers "
    "[controller guid=00000001-0000-0000-0000-000000000001 req=group "
    "[member guid=00000001-0000-0000-0000-000000000002 "
    "req='name shortname' name=Linux shortname=L] "
    "[controls num=1 notempty=true [button req=name name=Button1]] "
    "[shifts num=1 "
    "[shift guid=00000001-0000-0000-0000-000000000003 req=name name=Shift1]"
    "]]]]"
)

# ============================================================================
# CATÁLOGO DE ACCIONES (extraído por análisis del código y los seeds reales)
# ============================================================================
#
# Una acción es un evento de entrada con estado. Los 3 atributos clave son
# device / usage / page / value, más `time` (retardo ANTES de emitir).
#
# Codificación por tipo de dispositivo:
#
#   device=keyboard  page=0x7  usage=<uso HID de tecla>   value=1 down / 0 up
#   device=mouse     page=0x9  usage=1..5 (izq,der,central,X1,X2)  value=1/0
#   device=mouse     page=0x1  usage=0x38 (rueda)           value=1 arriba / 0xFF abajo
#   device=mouse     page=0x1  usage!=0x38                  value=X|<<8 Y con signo
#   device=hotkey    page=0xC  usage=<uso Consumer>         value=1
#
# Tabla completa tecla -> uso HID: Saitek.Helpers/Keyboard.cs en el descompilado.

DEVICE_SELF = "self"
DEVICE_KEYBOARD = "keyboard"
DEVICE_MOUSE = "mouse"
DEVICE_HOTKEY = "hotkey"

PAGE_KEYBOARD = 0x7
PAGE_BUTTONS = 0x9
PAGE_GENERIC_DESKTOP = 0x1
PAGE_CONSUMER = 0xC

# --- actionblock: los tres modos de reproducción ----------------------------
# press   -> se dispara al pulsar el botón
# repeat  -> se repite en bucle mientras se mantiene pulsado
# release -> se dispara al soltar el botón
BLOCK_PRESS = "press"
BLOCK_REPEAT = "repeat"
BLOCK_RELEASE = "release"

# Playback mode: open = se detiene al soltar el botón
#                closed = siempre completa la ejecución
PLAYBACK_OPEN = "regular"
PLAYBACK_CLOSED = "macro"

# --- roles de un botón -------------------------------------------------------
ROLE_FALLBACK = "fallback"
ROLE_UNPROGRAMMED = "unprogrammed"
ROLE_BANDS = "bands"
ROLE_MOUSE_X = "mouse-x"
ROLE_MOUSE_Y = "mouse-y"
ROLE_DIRECTIONAL = "directional"
ROLE_REPORT_AS = "report-as"

# --- botones reales del R.A.T.9 (del seed de fabrica 0738:1709) --------------
RAT9_BUTTONS = {
    "0x00090003": "Scroll Button",
    "0x00090004": "Back",
    "0x00090005": "Forward",
    "0x00090006": "Thumb Clockwise",
    "0x00090007": "Thumb Anticlockwise",
    "0x00090008": "Precision Aim",
    "0x00090009": "Mode 1",
    "0x0009000A": "Mode 2",
    "0x0009000B": "Mode 3",
}
RAT9_AXES = {
    "0x00010030": "X Axis",
    "0x00010031": "Y Axis",
    "0x00010038": "Scroll Wheel",
}

# --- sensitivity: pasos 1..30 (la GUI lo muestra como porcentaje) -----------
SENS_MIN, SENS_MAX = 1, 30

# --- Hot keys de consumo (device=hotkey page=0xC) ---------------------------
HOTKEYS = {
    176: "Play", 177: "Pause", 183: "Stop", 179: "Fast Forward",
    180: "Rewind", 181: "Next", 182: "Previous", 184: "Eject",
    226: "Mute", 233: "Volume +", 234: "Volume -",
    404: "Computer", 547: "Internet", 394: "Email",
    387: "Media Player", 402: "Calculator", 545: "Search",
    548: "Back", 549: "Forward", 550: "Stop", 551: "Refresh",
    554: "Bookmarks",
}

# --- eventos string (stringaction / stringcommand) ---------------------------
EVENT_APP_LAUNCH = "c9a025f1-b461-4e9d-a60a-911e02e080eb"   # ejecuta un programa
EVENT_GENERIC = "268f3b38-1e48-42f4-a1f5-cf7561b15dfa"      # evento con nombre
EVENT_LICENSED = "374a14dc-f6a0-4e28-a54c-cd6f31400975"      # evento de aplicacion

# NOTAS IMPORTANTES
# - El formato NO es XML: es texto UTF-16LE con corchetes [tag attr=valor ...].
# - Los atributos uint se serializan en hexadecimal de 8 digitos: 0xXXXXXXXX
# - Los valores por defecto NO se escriben.
# - [blast] NO es una secuencia de teclas: es el ICONO del comando en base64.
#   Las secuencias de teclas viven en los actionblock/action.
# - El DPI NO vive en el perfil: se configura aparte, a nivel de hardware.

# ============================================================================
# CONSTRUCTORES DE PERFILES
# ============================================================================

def action(device: str, page: int = 0, usage: int = 0, value: int = 1,
           time: int = 0) -> str:
    """Construye una accion. Solo escribe los atributos distintos del defecto."""
    a = f"device={device}"
    if page:
        a += f" page=0x{page:08X}"
    if usage:
        a += f" usage=0x{usage:08X}"
    if value != 1:
        a += f" value=0x{value:08X}"
    if time:
        a += f" time=0x{time:08X}"
    return f"[action {a}]"


def key(usage: int, down: bool = True, time: int = 0) -> str:
    """Tecla. usage = uso HID (0x04='a', 0xE0=Ctrl izq, 0x0D='m')."""
    return action(DEVICE_KEYBOARD, PAGE_KEYBOARD, usage, 1 if down else 0, time)


def mouse_button(usage: int, down: bool = True, time: int = 0) -> str:
    """Boton del raton: 1=izq 2=der 3=central 4=X1 5=X2."""
    return action(DEVICE_MOUSE, PAGE_BUTTONS, usage, 1 if down else 0, time)


def wheel(up: bool = True, time: int = 0) -> str:
    """Rueda: value 1 = arriba, 0xFF = abajo."""
    return action(DEVICE_MOUSE, PAGE_GENERIC_DESKTOP, 0x38,
                  1 if up else 0xFF, time)


def hotkey(usage: int, time: int = 0) -> str:
    """Tecla multimedia / de consumo."""
    return action(DEVICE_HOTKEY, PAGE_CONSUMER, usage, 1, time)


def action_block(actions: list, block: str = BLOCK_PRESS,
                 closed: bool = False) -> str:
    """Agrupa acciones en un bloque press / repeat / release."""
    head = "actionblock=macro" if closed else "actionblock"
    if block != BLOCK_PRESS:
        head += f" type={block}"
    return "[" + head + " " + " ".join(actions) + "]"


def action_command(name: str, guid: str, press=None, repeat=None,
                   release=None) -> str:
    """Comando completo con hasta 3 bloques."""
    blocks = [b for b in (press, repeat, release) if b]
    return f"[actioncommand={guid} name={name} " + " ".join(blocks) + "]"


def simple_command(name: str, guid: str, key_usage: int,
                   hold_ms: int = 0) -> str:
    """Atajo: comando 'simple' de una sola pulsacion de tecla."""
    a1 = key(key_usage, True)
    a2 = key(key_usage, False, hold_ms) if hold_ms else key(key_usage, False)
    return action_command(name, guid, action_block([a1, a2]))
