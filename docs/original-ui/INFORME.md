# INFORME: UI del software original del Mad Catz / Cyborg R.A.T.9 (Mad Catz Smart Technology "ST" Profile Editor, v7.0.45.2)

**Fecha:** 2026-10-16 · **Método:** ingeniería inversa directa del instalador REAL de archive.org
(`item software-x-64-fre-7-0-45-2`, .cab 98.5 MB) + verificación cruzada con vídeo detutorial
oficial en YouTube (YyA0nL__NHc "R.A.T. 7 Gaming Mouse Software", 6H5K8TiDtzk) y
reviews de 2010-2013 (everythingusb, techplayboy/archive, gameranx, OC3D, TechRadar).

**Identificación del binario:** `Saitek.Branding, Version=7.0.45.2`, `SmartTechnology, Version=7.0.45.2`
(copyright interno "© Mad Catz 2013"). Es la MISMA familia de app que cubrió el R.A.T.9 Cyborg
(2010-2011) y el R.A.T.9 Mad Catz (2013): el controller `CyborgMouse_V5` contiene las páginas
de los modelos R.A.T.5/7/9 con todas sus variantes de color (GlossBlack/Red/White, Albino,
Contagion, Infection) y ambos device IDs (Cyborg 0CD9/0CFA y Mad Catz 0738:1709).

---

## 1. ARQUITECTURA DE LA VENTANA (desde los binarios, verificado)

- Ventana WPF `SmartTechnology.MainWindow`, título "Smart Technology", **`WindowStyle=None`**
  (chrome propio dibujado), `AllowsTransparency`, `Topmost` opcional, `ResizeMode=CanResizeWithGrip`,
  tamaño nominal ~1024×767 (fondo `app_window_background.png` 1024×767).
- Dentro: **WindowsFormsHost "ProfileEditor"** — el editor de perfiles es WinForms (ToolStrip:
  New, Open, Save, Save As, Print, Test Profile, combo de perfil, botón "Views") incrustado
  en el shell WPF. Los recursos de imagen (`Pr0fileEditor_Forms_*`) son de este host.
- Estado vacío: "No controllers found – Plug in the device you wish to configure and run the
  program again." + error de "controller seeds".
- Splash: `splash_screen.png` (icono negro tile + garra/"M" roja Mad Catz + wordmark).
  Icono de ventana: `madcatz.ico`.

## 2. PESTAÑAS (4 páginas, tooltips verificados en Localize.resources)

| Pestaña | Tooltip oficial | Contenido |
|---|---|---|
| **PRODUCT** | "Select your device" | Selección de dispositivo; imagen del producto + RTF de bienvenida ("CyborgIntro"/"MadcatzIntro"), tips de inicio "Did you know?" con checkbox "Show at startup" |
| **SETTINGS** | "Examine and change your hardware settings" | Página "BmpView/Product View": imagen del ratón + panel DPI + Precision Aim + opciones de hardware |
| **PROGRAMMING** | "Make your controller come alive" | Página "Rotational View": ratón giratorio 3D + callouts de botones + editor de comandos por modo (shiftstate) |
| **SUPPORT** | "Get: Help, Tips and Contact us" | Manual, Quick Start Guide, tutorial vídeo, knowledgebase, contact/ticket, versiones software/driver/firmware + descargas de drivers y perfiles |

**Estilo de pestaña:** pieza 9-slice (left/middle/right, 159×21) con silueta achaflanada;
estado normal = negro (#030303→#111111), activa = naranja #FF9800–#FFAE32 (skin Mad Catz con
header `madcatz_header.png`: regla superior naranja #FFAF00, logo ovalado dorado #FFD400,
tagline "Play Harder" plateado #BEBEBE–#C5C5C5, y botones min/close ámbar #FFD36A→#E88A00
— sin maximize; menú contextual de la ventana: Maximize/Minimize/Close).
Capturas de vídeo 2012 confirman: pestañas PRODUCT / SETTINGS / PROGRAMMING / SUPPORT
con la activa rellena de naranja (#F2A000) y las demás carbón (#303334, texto blanco).

## 3. INVENTARIO PANTALLA POR PANTALLA

### 3.1 PRODUCT (Product View)
- Lista de dispositivos soportados por la suite (R.A.T.3/5/7/9 + variantes, M.M.O.7,
  S.T.R.I.K.E.5/7, Cyborg V.7, Pro Flight, gamepads L.Y.N.X.).
- Imagen "hero" del modelo conectado: `madcatz/rat9/rat9.png` (600×407, hero shot) y
  variantes GlossBlack/Red/White (`*_hero.png`).
- Panel de texto RTF de introducción de marca y "startup tips".
- En vídeo: título "CYBORG R.A.T.7", logo Cyborg rojo, min/close ámbar arriba-derecha.

### 3.2 SETTINGS (página `ratsettingspage.xaml` — "Product View")
Estructura (XAML/BAML extraído + capturas de vídeo):
- **Imagen del ratón** (render de fábrica del modelo, p.ej. `Rat9Mouse.png` 217×338) sobre
  fondo negro `RAT_Background.png` (275×376); a la izquierda la placa "ratname" con
  `LittleRAT.png` (franja 90×350, texto en Russell Square) y el nombre del dispositivo.
- **Dial/DPI display circular** arriba-izquierda (en vídeo: gauge azul brillante con arco
  naranja y número grande blanco "5600"; también existe el widget "DpiBigDisplay" y el
  panel LED digital rojo `DPI_LED_1..4.png` que muestra el DPI actual en dígitos tipo 7
  segmentos).
- **Panel "DPI Adjustment"**: descripción literal — "set the different DPI levels for each
  mode of the mouse. Drag the middle bar to adjust both X and Y DPI simultaneously. Drag
  each of the sliders to set X and Y DPI separately." → **DoubleSlider** (LeftValue/Middle/
  RightValue) por nivel DPI: 4 niveles independientes, X e Y por separado, en pasos de 25
  (rango 25–5600 R.A.T.9 Cyborg / 25–6400 R.A.T.9 Mad Catz 2013).
- Indicadores de nivel: imágenes `dpi_led_1..4` (y variantes GlossRed/Infection/White) que
  dibujan el panel LED físico del ratón según el nivel activo.
- **Panel "Precision Aim"** (componente Branding `PrecisionAim`): slider horizontal con
  marcador triangular, regla de ticks y lectura "%"; descripción: "Use this section to set
  the sensitivity level of the mouse in Precision Aim mode. The higher the precision you
  set, the slower your aiming movement speed will be…" (por defecto 50 %). En la versión
  2013 también `PrecisionAimDpi_Description` → "Set the DPI level that you wish to use
  whilst the Precision Aim button is pressed."
- **Reset To Defaults** (con animación show/hide por storyboard) y botón/link
  **Windows Mouse Settings**.
- Controles "hardware" adicionales del software (strings verificados; la app los muestra
  para otros dispositivos o según firmware):
  Angle Snap (con descripción), Sensor Damping, Surface Calibration (Dynamic/Calibrated),
  Lift-Off Height (sensor PMW3310: calibración dinámica/calibrada, recomendaciones mm),
  Poll Rate (descripción verificada), Power Consumption (Low/Full), **Sleep Timer**
  (0 = nunca duerme), **D.P.I. L.E.D. Sleep Timer / L.E.D. Sleep Timer** (apaga el LED de
  estado tras conectar para ahorrar batería), **Battery Life** y **BatteryChargeIndicator**
  (widget con cruz roja para batería vacía/extraída + medidor de % y animación de carga),
  LED Brightness.
- Ayuda superpuesta al panel: tarjetas chamflanadas (`help_dpi_double_slider.png`,
  `help_dpi_single_slider.png`, `help_precision_aim.png`).

### 3.3 PROGRAMMING (página "Rotational View", especificada al 100 % en `RotationalView.xml`)
- **Visor 3D giratorio**: 24 fotogramas del render del modelo (`Rotational.RAT9_01..24.png`),
  arrastrables/rotan; iconos de vista a la derecha (x=630): **underside / vtop / 360**
  (80×80, cada uno con estados default/over/pressed).
- Fondo de página `RAT_Background.png`; ratón en x=350,y=80.
- **Nombre de perfil**: caja "Loaded Profile" (rect 84,71,176×20, texto en Russell Square
  uppercase) + campo editable del nombre (84,94,176×18).
- **Callouts interactivos** (`Callouts.png`, 501×1000): columnas de etiquetas (240×29,
  fondo azul claro/azul oscura, contorno naranja) con líneas guía terminadas en punto
  naranja que apuntan al control físico del ratón. Sección activa = la etiqueta se
  resalta (estado static/active definido por coordenadas XML).
- **Filas de comandos** (commandrects 220×22 apiladas cada 50 px a partir de y=157):
  Mouse scroll button (HID 0x90003), Precision Aim button (0x90008), Forwards button
  (0x90005), Backwards button (0x90004), Thumb Anticlockwise (0x90007), Thumb Clockwise
  (0x90006); en la vista inferior: **Mouse sensitivity** (0x10030) → sliders X/Y.
- **Menú contextual del callout** (confirmado en vídeo): lista con "Unprogrammed", "Fall
  Back", "New Key &Presses...", "New &Macro...", "New &Advanced Command..." + acciones de
  lista (copiar/cortar/pegar/borrar, Load/Save..., Reset).
- **Editor de comandos (ActionBlockEditor)**: bloques por acción con
  **artistas por entrada** (keyboard, mouse, RAT-mouse-recording up/down, wheel up/down,
  teclas ST), segmentos **Simple vs Advanced: press / repeat / release**, grabación en vivo
  ("Hover your mouse cursor over this area to begin recording keyboard input"), **Record
  Delays / Type Delay / Time Editor** (retardos editables por fila, ocultos a 0 ms),
  avisos de macros desemparejadas (presses/releases faltantes), borrado ("clear"),
  iconos propios por comando (Import Image / Select An Icon).
- **Iconos de tipo de comando** (`command_icon_*.png` 16×16): Advanced (consola bloque),
  KeyPress (tecla), Macro (documento-panel), **Cycle** (flechas circulares), **Temporal**
  (reloj de arena) → tipos: key, macro, avanzado, ciclo, temporal.
- **Botones inferiores fila (y=550)**: NEW (x=170), OPEN (x=290), SAVE (x=410),
  SAVE AS (x=530), TEST (x=650) — Botones de texto Russell Square 8 uppercase con skin
  9-slice (normal/hover/pressed/disabled) glossy cian.
- **Botones de modo (shiftstates) (y=500)**: tres botones en x=170/273/376 con skins por
  color: **R (roja), B (azul), P (púrpura)** = los 3 modos del ratón (LED del botón de modo
  rojo/azul/violeta). En la build 2013 se presentan como "PROFILE 1/2/3" (vídeo: activa
  cian #00A7E3, resto carbón); cada modo = perfil completo propio (comandos + DPI +
  Precision Aim). "Click to name shiftstate", "Choose Shift Buttons" (combinación de
  botones física para seleccionar el modo), fallback opcional del modo, ActionLock
  (bloqueo de acciones), Export/Import Programming.
- **Botón ACTIVATE PROFILE** (arriba-derecha x=625,y=70 + texto 605,53, con 4 estados)
  y lectura "800 DPI"/"5600" del display.
- **Panel inferior de curvas** (vídeo): grafo negro con rejilla y línea naranja =
  editor de curva de respuesta del eje (`AxisResponseCurveControl`/`ScrollingGraph`,
  Curve profiles, Curvature, Deadzone, Link Axis — en RAT: sensibilidad por eje).
- Diálogo **Test**: ventana Windows estándar "Keep this window open whilst testing!" con
  log en vivo de las pulsaciones (strings RTBInfo verificadas) y Close/OK.

### 3.4 SUPPORT
- Read Programming Manual (SST_Manual_En.html), Quick Start Guide, Tutorial Video,
  Knowledgebase, Contact Us, Submit a Ticket.
- Estado de versiones: Software/Driver/Firmware Version + "update available" +
  "…is now ready to install" + "Your software is up to date"; Download Drivers and
  Software; Download Profiles; Download Custom Tabs; Show startup tips.
- Enlaces sociales (Facebook/Twitter/YouTube/RSS feed display).

## 4. USO DE LA IMAGEN DEL RATÓN (verificado)

- **PROGRAMMING: diagrama 3D interactivo** — render 24 frames que ROTAN (360º drag/free),
  con 3 botones de vista (underside/top/360). Al pasar por encima, cada zona física se
  resalta (dos estados por región: static/active en la lámina de callouts) y la fila de
  comandos correspondiente enlaza mediante líneas guía naranjas con punto terminal.
- En vídeo se ve además un **anillo naranja + lupa/callout ampliada** flotando sobre la
  zona del botón al enfocarla ("press me"/badge).
- Click en el callout → menú contextual de comandos ("Unprogrammed / Fall Back / New Key
  Presses / New Macro / New Advanced Command…").
- **SETTINGS: imagen fija de producto** (render lateral 3/4, 217×338) con placa de nombre;
  en R.A.T.9 se muestran además los estados del **panel LED DPI** (`dpi_led_N.png`) y el
  hero 600×407 en PRODUCT. Cambia de imagen según variante de color comprada
  (GlossBlack/Red/White…).
- La franja izquierda "ratname" usa `LittleRAT.png` (miniatura).

## 5. ESTILO VISUAL (colores medidos sobre recursos reales)

- **Cromo de ventana:** header glossy carbón #626262→#4A4A4A→#303030→#090909 con regla
  naranja superior #FFAF00–#F3A900; botones min/close ámbar #E88A00/#FFD36A; pestañas
  negro #030303–#111111 (inactivas) / **naranja activo #FF9800–#FFAE32**.
- **Fondo de app:** navy profundo con circuito azulado: #001B2F base → #002A46 →
  #0868B2 brillo central; mosaico pixel #3993BE/#196FA3; rejilla digital #6388A6;
  hexágonos acero #3D6073, líneas claras #7899AD.
- **Widgets glossy tipo cristal:** slider/botones azul→blanco→cian con borde #29A4D1
  (paradas #1475B4, #245F88, #7A8994, #F8F9F8, #D6E9ED, #A3D1DE, #2E9FCC); fondos
  #3C7FB1, #5EB4E3, #B0DFF8–#B8E4FA; neutros #EBEBEB/#F3F3F3; gris #8E8F8F/#CDCDCD/
  #DDDDDD; texto secundario #FF929292→#FF929292; negro total #FF000000 para texto.
- **Acentos:** naranja #FFF7941D (BAML) = #F7941D; cian seleccionador #00A7E3/#22A4DC;
  LED DPI rojo (dígitos 7-seg sobre panel carbón achaflanado).
- **Paneles de ayuda:** tarjetas gris-verdoso #6F756D/#858887 con esquinas cortadas
  (chamfer) y texto negro; overlays de tutorial: fondo #080D15 con pastillas blancas
  #F2F4F7 y rombos indicador #23547F; tarjeta Lighting con degradado #65BDD0→#557891.
- **Tipografía:** **Russell Square** (russellc.ttf, bold, uppercase en botones/etiquetas)
  + Arial y Arial Rounded Bold (arlrdbd) para texto; tamaño 8-10.
- **Densidad:** panel principal 1024×767, listas de comandos en columna izquierda con
  filas de 22 px; callouts 240×29 por fila cada 50 px; botones de barra ~90×28.
- **Animaciones:** storyboards WPF a 0.2 s/0.4 s en hover (opacidad), show/hide del botón
  Reset; rotación de 24 frames en el visor; medidor de batería animado; ScrollingGraph.
- **Cromos:** sin bordes redondeados — **chaflanes/esquinas cortadas** en todos los
  paneles, botones y pestañas (silueta hexagonal). Skins intercambiables por marca
  (Cyborg silver/azul vs Mad Catz naranja) en el mismo binario.

## 6. FUNCIONES A CUBRIR EN rat9-config (de la app original, distinguiendo RAT9 wireless)

Verificadas para R.A.T.9:
1. 3 modos ("shiftstates", LED de modo rojo/azul/violeta), nombre de modo editable,
   combinación de botones para cambiar de modo, fallback de modo, ActionLock.
2. 4 niveles DPI por modo con X e Y independientes (sliders doble, incrementos de 25
   DPI, 25–5600/6400), display digital del DPI, rocker switch del ratón para subir/bajar
   nivel, opción de convertir el rocker en 2 botones de macro ("DpiButtonsDescription")
   y en ciclo ("DpiCycleButtonsDescription"); los features DPI se pueden asignar a
   cualquier botón sin anular su programación ("DpiButtons_FeatureMap_Description").
3. Precision Aim: % de reducción (por defecto 50 %, ajustable) o DPI propio en la
   versión 2013; programable como tecla/modificador en builds recientes.
4. Programación de botones por modo: scroll button (middle click), precisión aim,
   forwards, backwards, rueda de pulgar CW/CCW, izquierda/derecha; menú por botón
   (Unprogrammed/Fall Back/New Key Presses/New Macro/New Advanced Command).
5. Macros: grabación en vivo de teclado + ratón + rueda, bloques press/repeat/release,
   quantize/Record Delays/Type Delay, tipos Cycle y Temporal, edición de iconos,
   Test Profile (log en vivo), Latched playback, Delete Unused Commands, Default Command.
6. Perfiles .pr0: New/Open/Save/Save As/Print/Export-Import Programming, Activate
   Profile en caliente, "startup profile" vía icono de bandeja (verificado en
   gam.SE) — **sin** auto-switching por aplicación (lo hace la 3rd-party Cyborg
   Auto-Profiler, feature NO oficial del software).
7. Sensibilidad por eje (X/Y %) vía vista inferior del ratón, curvas de respuesta y
   Link/Calibrate de ejes (curvas para sticks; para ratón: sliders de sensibilidad).
8. Batería: BatteryChargeIndicator (medidor %, cruz roja si está vacía), Sleep Timer,
   LED Sleep Timer y D.P.I. LED Sleep Timer (ahorro de energía del LED), Power
   Consumption (Low/Full) — **exclusivos del modelo inalámbrico**.
9. Sensor de hardware: Angle Snap, Sensor Damping, Surface Calibration, Lift-Off Height
   (PMW3310 en ratones posteriores; R.A.T.9 original = láser Plair Twin-Eye 5600/6400),
   Poll Rate (dinámico hasta 1000 Hz), Reset to Factory Defaults.
10. Iluminación: **sólo para M.M.O.7 / S.T.R.I.K.E.5-7** (colour tile por modo + swatch +
    sliders RGB, se aplica al firmware). El R.A.T.9 NO tiene iluminación configurable —
    sus LEDs son fijos por modo (rojo/azul/violeta) + panel LED DPI (verificado: su
    RotationalView.xml no tiene sección de lighting).
11. Soporte multidevice (R.A.T.3/5/7/9, M.M.O.7, S.T.R.I.K.E.5/7, V.7, Pro Flight,
    gamepads) + localización (14 idiomas) + página de versiones y descargas + enlaces
    sociales + impresión de perfil.

Para el R.A.T.9 (inalámbrico) en concreto: batería medidor + sleep/LED timers + power
consumption (10.ª y 8.ª); el resto es común con R.A.T.7. El R.A.T.7/5 (cableados) tienen
las páginas equivalentes sin widgets de batería (mismo software, mismo layout).

## 7. IMÁGENES GUARDADAS (rutas absolutas, válidas verificadas con `file`)

Directorio base: ~/rat9-config/docs/original-ui/
(+ subdirectorios extracted-from-installer/ [1832 PNGs tallados de todos los binarios],
 gres_controller/ [65 recursos WPF con nombre], resdump/ y el árbol
 ~/.hermes/cache/scratch/rat9_app/{gdump,resdump,ren} con TODOS los recursos nombrados
 por ensamblado.)

(Ver lista en el JSON entregado por el agente: cada entrada incluye descripción de una
línea y origen. Los JEPG de galería cyborg_site_gallery_*.jpg provienen de la Wayback
de cyborggaming.com (fotos de producto/receptor); video_*.jpg son fotogramas del
tutorial oficial en YouTube.)

## 8. NO VERIFICADO / INCERTIDUMBRES

- **Batería en la página del R.A.T.9:** el control BatteryChargeIndicator existe en
  Saitek.WPF_ControlLib y hay string "Battery Life", pero no pude confirmar EN QUÉ
  página de la R.A.T.9 se muestra el medidor (puede ser la pestaña Product).
- ¿4 perfiles o 3?: los binarios y todas las reviews confirman **3 modos** con LED
  rojo/azul/violeta; si tu unidad de muestra 4 "perfiles" son los 4 NIVELES DPI
  (800/1600/3200/6400), no 4 perfiles conmutables por software.
- El panel inferior con grafo naranja en vídeo ("Precision Axis") puede ser el editor
  de curva de respuesta (AxisResponseCurveControl) o parte del panel Precision Aim —
  no diferenciado a resolución de vídeo.
- La animación de arranque exacta del splash y la identidad del botón circular
  inferior-izq del settings (en vídeo) no se resolvieron.
- Color de pestaña activa en el skin CYBORG 2010-2011 (naranja es la Mad Catz; la
  variante Cyborg silver/azul usa los mismos BAML "silver" — no vi su estado activo).
- "Poll Rate" y "Lift-Off Height" están en la tabla de strings de la app; su presencia
  en la página SETTINGS del R.A.T.9 concreto (vs otros ratones de la familia) no se
  distinguió por dispositivo.
- El menú contextual completo del callout se leyó de vídeo a baja resolución: los
  ítems base (Unprogrammed/Fall Back/New Key Presses/New Macro/New Advanced Command)
  están verificados por strings; las entradas "Reset/Copy/Delete/Load-Save" del
  vídeo no se confirmaron 1:1.
- No se encontró ningún widget de nivel de batería del receptor (el receptor es
  cargador físico con LEDs propios, no controlado por software según lo hallado).