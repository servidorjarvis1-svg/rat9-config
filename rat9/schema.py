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
