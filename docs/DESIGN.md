# rat9-config — diseño de la interfaz

> Documento vivo. Consolida el diseño ANTES de escribir la interfaz.
> v0.1 — 2026-10-16. Hechos de hardware verificados hoy mismo contra el ratón.

## 1. Qué es esto

Un configurador **local** del Mad Catz R.A.T.9 (`0738:1709`) para Linux. Corre
como app de escritorio (ventana nativa GTK4 con la interfaz web dentro) o en el
navegador contra el mismo servidor local.

Sin cuenta, sin nube, sin telemetría, sin instalador. Un binario Python, un ratón
y la verdad del protocolo que ya verificamos por ingeniería inversa.

**Audiencia:** el dueño del ratón. Técnico, Linux, quiere ver el estado real del
hardware y editar sus perfiles sin pelearse con una interfaz de 2010.

## 2. Hechos del hardware (verificados, no supuestos)

Todo lo de esta tabla se comprobó ejecutando código contra el ratón el
2026-10-16, no leyendo documentación.

| Dato | Valor | Fuente |
|---|---|---|
| Dispositivo | `0738:1709` Mad Catz R.A.T.9 Wireless Mouse, presente | `lsusb` |
| **Acceso sin root** | **Sí** — leer funciona como usuario normal | reglas udev corregidas |
| Perfil activo | 1 | registro `0x0074`, `byte0 >> 4` |
| Batería | 96 %, estable en 8 lecturas seguidas | registro `0x00BA`, byte0 |
| DPI perfil 1 | 800 / 800 (X / Y) | `0x1000·1 + 0x100·eje + 0x73` |
| DPI perfil 2 | 1600 / 1600 | ídem |
| DPI perfil 3 | 3200 / 3200 | ídem |
| DPI perfil 4 | 6400 / 6400 | ídem |
| Registro `0x000B` | devuelve `0x0001`; solo responde a longitud **2**, y **no** responde si se le ponen los bits de modo/eje | sondeo propio |
| Todo el resto de `0x00`–`0xFF` | no responde | `cli.py scan` |

**La batería a veces falla.** Una lectura devolvió `None` y ocho seguidas
devolvieron 96. El firmware suelta basura de forma intermitente, así que la
interfaz **nunca** debe mostrar un valor crudo: o hay un porcentaje válido
(0–100) o dice "desconocida". Ya está resuelto en `protocol.battery()`, y la UI
debe respetarlo en vez de inventarse un 0.

**El registro `0x000B` es nuevo** y no sabemos qué es. No se puede usar para nada
de momento, pero se muestra en el panel de diagnóstico como dato en crudo: es la
prueba de que hay más firmware por descubrir y no queremos esconderlo.

**Cuidado con llamar "perfiles" a los cuatro slots.** La ingeniería inversa del
software original documenta **3 estados de desplazamiento** (*shiftstates*, con
LED rojo / azul / violeta y nombre editable) y **4 niveles de DPI por modo**. Los
valores que leemos —800, 1600, 3200, 6400, exactamente los "niveles" de fábrica—
encajan con la segunda lectura, no con la primera. Nuestro direccionamiento
(`0x1000·m + 0x100·eje + 0x73`) tiene un solo campo de 2 bits, y encaja igual de
bien con "4 modos" que con "4 niveles", así que **la ambigüedad no está resuelta
con los datos que tenemos**. Antes de decidir si la interfaz dice "perfil" o
"etapa" hay que saldarla con una prueba de hardware (leer `0x0074` mientras se
pulsa el botón de modo del ratón). Mientras tanto, la interfaz no usa ninguna de
las dos palabras para esos cuatro slots.

## 3. Modelo de capacidades — la decisión que define toda la interfaz

El error más fácil aquí es tratar la app como si pudiera escribir en el ratón.
**Todavía no puede**: el framing de escritura del perfil y el de DPI están
documentados pero sin verificar contra hardware, y una escritura a lo tonto deja
el ratón sin responder hasta que lo desenchufas.

En vez de esconder eso tras un banner de aviso que nadie lee, la interfaz se
organiza en **tres niveles explícitos**, y cada control declara el suyo:

| Nivel | Qué incluye | Cómo se comporta en la UI |
|---|---|---|
| **Local** (siempre funciona) | editor de macros, biblioteca de perfiles `.pr0`, import/export, catálogo de teclas, el diagrama | Funciona sin ratón y sin permisos. Nunca se desactiva. |
| **Lectura verificada** | perfil activo, batería, DPI por perfil y eje | En vivo, con refresco automático. Es la única fuente de verdad del hardware. |
| **Escritura experimental** | cambiar DPI, enviar un perfil al ratón | Botón presente pero marcado. Guarda **siempre** en local primero, avisa de la consecuencia real (si deja de responder: desenchufar y enchufar), y nunca lo hace sin que el usuario lo pida. |

De ahí sale la regla estructural: **la app está completa sin ratón**. El estado
del hardware es una capa que aparece cuando está; si no está, la app sigue
sirviendo para lo que sí controla (macros y perfiles), con una estado de "sin
dispositivo" honesto en vez de una pantalla muerta.

## 4. Arquitectura de información

Cinco destinos, en un raíl lateral persistente. Se ordenan por lo que el usuario
viene a hacer, no por lo que es fácil de programar:

1. **Panel** — el estado del ratón: diagrama interactivo, batería, perfil activo,
   DPI del perfil activo, y el diagnóstico en crudo. Es la pantalla de "¿cómo
   está mi ratón?".
2. **Botones** — los 9 botones reales del R.A.T.9 y los 3 ejes. Se selecciona una
   zona del diagrama o de la lista y se le asigna qué hace.
   Botones del seed de fábrica: rueda, atrás, adelante, rueda lateral horaria,
   rueda lateral antihoraria, *precision aim*, y los tres de cambio de perfil.
3. **Macros** — el editor que ya tiene lógica hecha: comandos con bloques
   *al pulsar* / *mantener* / *al soltar*, acciones de teclado, botón de ratón,
   rueda y tecla multimedia, cada una con su retardo. Modo abierto (se corta al
   soltar) o cerrado (siempre completa).
4. **DPI** — los 4 perfiles × 2 ejes, con la sensibilidad (1–30) y la distinción
   fábrica / modificado que ya calcula el servidor.
5. **Perfiles .pr0** — la biblioteca local: guardar, cargar, exportar, importar,
   ver la gramática cruda del perfil y comprobar el *round-trip* (leer lo que
   acabamos de escribir).

**Fuera de la lista por falta de pruebas, no por olvido:** no hay sección de
iluminación. Sondeamos los 256 índices y ninguno devuelve nada relacionado con
LEDs. Antes de inventar una pestaña de colorines para un canal que no conocemos,
queda como pregunta abierta (ver §8).

## 5. Disposición y responsive

Un solo requisito duro, heredado de cómo trabaja el usuario: **la ventana se
redimensiona en el tiling y la disposición tiene que reorganizarse de verdad**,
no encogerse. El caso de referencia es la ventana estrecha y alta
(~950 × 1068), que es como aparece en Hyprland; el caso máximo, 4K.

La escala se decide por el ancho **del contenedor**, no del viewport
(*container queries*), porque la interfaz puede acabar embebida en una ventana
nativa, en una pestaña del navegador o en un panel lateral, y en los tres casos
el ancho disponible es distinto del de la pantalla.

| Ancho disponible | Disposición |
|---|---|
| ≥ 1400 px — *command* | raíl con etiquetas (220 px) + lienzo del diagrama + panel de ajustes (380 px). Tres columnas. |
| 1000–1400 px — *standard* | raíl solo iconos (64 px) + lienzo y panel apilados en dos columnas. |
| 700–1000 px — *compact* | raíl horizontal como pestañas arriba; una columna; el diagrama se escala y el panel pasa a acordeón. **Este es el caso normal.** |
| < 700 px — *minimal* | una columna, pestañas, el diagrama se puede plegar para dar sitio a los controles. |

Dentro de cada panel, los controles se colocan con `auto-fit`/`minmax` para que
un panel ancho meta dos columnas y uno estrecho una, sin escribir un breakpoint
por cada combinación.

## 6. Lenguaje visual

Dirección: **panel de control de hardware, tema oscuro, acento azul**. Un HUD
técnico de verdad —líneas finas, rejilla sutil, glow medido, esquinas
técnicas— y no un dashboard de SaaS con tarjetas.

Reglas que nos ponemos por escrito para no acabar en el diseño genérico:

- Nada de gradientes morados ni de glassmorphism decorativo.
- Nada de "todo centrado": la composición es un banco de trabajo, alineado a la
  izquierda, con jerarquía por escala y espacio, no por colorines.
- Iconos solo cuando ayudan a leer de un vistazo; jamás un iconito redondeado
  encima de cada título.
- El diagrama del ratón es el elemento central y **debe ser nuestro**: un SVG por
  capas, no un PNG de fondo. Cada zona (carcasa, botones, rueda, laterales) es
  un elemento clicable y accesible por teclado, y se puede recolorear por zona.
  Los dos PNG que hay en `assets/` son atmósfera, no interfaz: el ratón no está
  recortado, no tiene capas y no se puede ni pulsar ni recolorear.
- Cualquier animación explica un cambio de estado y respeta
  `prefers-reduced-motion`.

Los tokens concretos (paleta, tipografía, espaciado, radios, elevación) se fijan
en §7 en cuanto cierre la investigación en curso.

## 7. Fuentes del lenguaje visual

- **El software original** (`Mad Catz Software 7.0.45.2`): se toma su
  **inventario de disposición** —qué secciones tenía, dónde las ponía, cómo usaba
  la imagen del ratón— y nada más. No se clona su cromo: además de ser de 2010 y
  feo, es material con derechos.
- **Los configuradores actuales** (Razer Synapse, Logitech G HUB, Corsair iCUE,
  SteelSeries, Wooting, Keychron Launcher, ZSA Oryx, Piper/OpenRGB): se extraen
  los patrones que funcionan y, sobre todo, las quejas documentadas de usuarios,
  que es donde está la lección.
- **Referencias de oficio** para el HUD oscuro y el responsive sin framework.

Resultado de la investigación: pendiente, se añade aquí como §7.bis.

## 7.bis. Resultado de la investigación

### 7.bis.1 El software original: qué hacía, y qué copiamos

El instalador real (98 MB de .cab, recuperado de archive.org) se abrió y se
extrajeron sus **recursos gráficos**, además de analizar capturas de la app en
funcionamiento. Esto es lo que había:

**Estructura** — ventana de 1024×767 sin bordes, con **4 pestañas**: *Product*,
*Settings*, *Programming*, *Support*. En *Programming* estaba todo lo
interesante: el ratón en el centro como **render de 24 fotogramas que rota**, con
tres botones de vista (**superior / inferior / 360°**), y sobre el render una
lámina de **etiquetas de llamada** (240×29, contorno naranja, con línea guía) que
apuntan a cada control. Al pasar el ratón la zona se resalta y aparece un anillo
con lupa. Al hacer clic se abre el menú de comandos:

> *Unprogrammed / Fall Back / New Key Presses / New Macro / New Advanced Command*

Eso encaja exactamente con nuestro esquema (`ROLE_UNPROGRAMMED`, `ROLE_FALLBACK`
y los tipos de comando), lo cual es una validación cruzada de que la ingeniería
inversa del formato `.pr0` fue por buen camino.

**Lo que confirma del protocolo** (y nos ahorra dudas):
- **Los macros son bloques *pulsar / mantener / soltar*** — exactamente nuestros
  `BLOCK_PRESS` / `BLOCK_REPEAT` / `BLOCK_RELEASE`. El original los llamaba
  *Pulsar / Mantener (Repetir) / Soltar*, e incluso avisaba de "pulsos de macro no
  balanceados" y bloqueaba la reproducción (*latched*).
- **El DPI va en pasos de 25.** Nuestro `DPI = raw·25 + 25` queda confirmado.
  Consecuencia: `protocol.DPI_MIN = 100` **está mal**, el mínimo representable es
  **25** y la interfaz tiene que moverse en múltiplos de 25, no con un slider libre.
- **Rango real**: 25–5600 en el Cyborg R.A.T.9, 25–6400 en el Mad Catz de 2013.
- El DPI se ajustaba con un **doble slider**: una barra central movía X e Y a la
  vez, y luego cada eje por separado. Con las etiquetas *"Low DPI = Slow mouse
  cursor movement"* / *"High DPI = Fast…"*.
- **Precisión (aim)** = un porcentaje de reducción de sensibilidad mientras se
  mantiene pulsado, **50 % por defecto**, ajustable con un slider. Es una función
  real que deberíamos exponer: hoy la tenemos en el diagrama como una zona más,
  pero sin su parámetro.

**Funciones del original que sí debemos cubrir** (todas verificadas en su UI):
- 3 estados de desplazamiento con nombre editable y LED por estado.
- Niveles de DPI con X/Y independientes.
- Programación de los 8 botones del ratón desde las llamadas del diagrama.
- Editor de comandos con **126 comandos integrados** en dos grupos (atajos de
  aplicación y teclas), e icono por comando.
- Temporizadores de reposo y de reposo del LED, y consumo bajo/completo — cosas
  **específicas de un ratón inalámbrico** que a nosotros nos interesan.
- Ajustes de sensor: *angle snap*, amortiguación, calibración de superficie,
  altura de despegue, tasa de refresco, y reset a fábrica.
- Gestión de perfiles: nuevo/abrir/guardar/exportar/importar/**probar en vivo**
  (una ventana que registra lo que el ratón envía mientras pulsas).
- Estado vacío explícito cuando no hay dispositivo: *"Conecta el dispositivo que
  deseas configurar y ejecuta el programa de nuevo."*

**La pregunta de la iluminación, resuelta: NO.** El panel de *Lighting* del
software original existía, pero era **solo para los dispositivos hermanos**
(M.M.O.7 y S.T.R.I.K.E.5/7). En el R.A.T.9 los LEDs son **fijos por modo** (rojo /
azul / violeta) más el panel de LEDs de DPI. No hay canal de color que controlar,
así que **no se dibuja pestaña de iluminación**. Lo que sí se muestra es el
**panel de LEDs de DPI** tal como lo dibujaba el original (display de 7 segmentos
en rojo), y el color del LED del modo activo como dato informativo.

**Estilo visual del original** — y aquí hay una herencia que merece la pena
conservar: **esquinas achaflanadas en todo** (nada de bordes redondeados), azul
marino profundo (`#001B2F`, `#0868B2`) con cobalto (`#3993BE`, `#00A7E3`) y
naranja como único acento (`#FF9800`, `#FFAE32`), tipografía **Russell Square en
negrita y mayúsculas** a 8–10 px. Nuestra versión mantiene lo estructural
—esquinas técnicas achaflanadas, jerarquía por densidad— y cambia el naranja por
el acento azul, que además es el color favorito del dueño del ratón.

### 7.bis.2 Los 12 configuradores actuales: qué copiar y qué evitar

Se analizaron Synapse 4, G HUB, iCUE 5, SteelSeries GG, Wootility, Glorious CORE,
Pulsar, ATK/VGN WebHub, Keychron Launcher, ZSA Oryx, OpenRGB y Piper.

**Los patrones que vamos a copiar:**
1. **El diagrama es el centro y todo lo demás son paneles alrededor.** El
   configurador se usa *desde* el ratón, no desde una lista de ajustes.
2. **Las etapas de DPI como tira horizontal bajo el diagrama**, con la activa
   resaltada, y **conmutador X/Y separado**. Synapse lo hizo mal: para dejar dos
   etapas había que desactivar las otras una a una.
3. **Macros = lista lineal de eventos con pares pulsar/soltar explícitos y
   retardos editables en línea**, con **modos semánticos de retardo** (*como se
   grabó / fijo / sin retardos*) en lugar de veinte campos numéricos.
4. **La semántica de disparo como etiquetas predefinidas** (no repetir / repetir
   mientras se mantiene / alternar) en vez de lógica montada a mano.
5. **Feedback de estado siempre.** Es la queja número uno del sector, y en
   nuestras manos es más grave porque **todavía no sabemos si la escritura
   funciona**. La interfaz tendrá que decir la verdad: "esto está guardado en
   local", "esto se ha enviado y no lo podemos confirmar", "esto no se ha tocado".
   Nada de un "guardado ✓" que no podemos respaldar.
6. **El ratón funciona al 100 % sin la app.** Ya es nuestro caso.
7. **Previsualización en vivo**, nunca "configurar a ciegas y rezar".
8. Export/import de perfiles en **JSON local, sin nube ni cuenta**.

**Lo que evitamos**, con las citas del daño que hacen: cuentas y nube en el camino
crítico (el modo invitado de Synapse está escondido); bloat y publicidad dentro
del configurador (SteelSeries instala un secuestrador de audio y un grabador de
pantalla); **el rendimiento como impuesto** (iCUE consume un 3–5 % de CPU en
reposo y tarda 30–60 s en dejar el ratón utilizable tras arrancar); rediseños que
borran funciones sin ganancia; y estado fantasma (*"the wrong profile is displayed
as being active"*).

### 7.bis.3 Oficio: lo que se aplica al construir

- **Tokens en OKLCH** con una escalera de luminancia para las superficies y
  **contraste WCAG AA verificado con código** (matrices de Ottosson), no a ojo.
- **Elevación por luminancia**, no por glassmorphism: en una ventana embebida el
  `backdrop-filter` sólo cuesta GPU y detrás casi siempre hay nuestra propia app.
- **Separación de 1 px pintada en el `gap`** del grid en lugar de bordes dobles:
  evita que los bordes parpadeen al redimensionar en Hyprland.
- **Tres disposiciones por `grid-template-areas`** (+container queries para el
  hueco del lienzo, que no es el ancho de la ventana).
- **Motion con tres duraciones y dos easings**, `prefers-reduced-motion` respetado.
- El SVG con **`vector-effect: non-scaling-stroke`** para que la línea de 1,5 px
  siga midiendo 1,5 px a 900 y a 4K.

### 7.bis.4 La app nativa: verificado, no supuesto

`rat9/app.py` existe y se ha **ejecutado**: ventana GTK4 + libadwaita con la
WebView de WebKitGTK 6.0, sirviendo la interfaz y la API desde el mismo proceso.
Hallazgos que ahorran depuración:

- **La UI se sirve por HTTP local, no desde `file://`.** Verificado en esta
  máquina: una página `file://` que hace `fetch()` al servidor local **está
  bloqueada por WebKit** si el servidor no manda cabecera CORS. Sirviendo por HTTP
  es mismo origen y el problema no existe.
- `console-message` **no existe** en WebKitGTK 6.0; el sustituto es
  `Settings.set_enable_write_console_messages_to_stdout(True)`.
- `WebView.new_with_settings` tampoco existe (era de GTK3): se pasa `settings=`.
- El **intérprete tiene que ser `/usr/bin/python3`**: el venv de Hermes no tiene
  `gi`.
- `ThreadingHTTPServer` con `daemon_threads=True`, y `shutdown()` **en un hilo
  aparte** porque bloquea y congelaría el bucle de GTK.

## 8. Abierto, y con qué evidencia

| Pregunta | Estado |
|---|---|
| ¿El R.A.T.9 inalámbrico tiene LEDs controlables por software? | **RESUELTO: no.** El panel de iluminación del software original era solo para M.M.O.7 y S.T.R.I.K.E.5/7. En el R.A.T.9 los LEDs son fijos por modo. No se dibuja pestaña de iluminación; se muestra el panel de LEDs de DPI como información. |
| ¿Los cuatro slots son "perfiles" o "niveles de DPI"? | **Ambiguo.** Ver el aviso de §2. Se salda leyendo `0x0074` mientras se pulsa el botón de modo del ratón. |
| `protocol.DPI_MIN = 100` | **Corregido a la baja: debe ser 25.** El original ajustaba en pasos de 25 y su rango empieza en 25. El slider tiene que ir en múltiplos de 25, no libre. |
| El parámetro de precisión (aim) | El original usaba **un porcentaje de reducción de sensibilidad, 50 % por defecto**. Hoy tenemos la zona en el diagrama pero no su parámetro: falta exponerlo. |
| ¿Qué es el registro `0x000B` = `0x0001`? | Desconocido. Se muestra en crudo. |
| Framing real de escritura del perfil | Documentado (`URB {Length=0x88, Function=0x17}` que traduce el filtro `SaiUsb`), **sin verificar**. Falta cerrar el dispatcher `0x13688-0x14180` o capturar USB con `usbmon`. |
| Escritura de DPI | Parámetros deducidos del driver de Windows, **sin verificar**. |
| ¿Nombre y descripción del repo público? | Pendiente de decidir antes de publicar. |

Hasta que la escritura no esté verificada, la interfaz **no** presenta cambiar el
DPI como una operación normal. La presentará como lo que es: una operación
experimental, aparte, que se pide explícitamente.
