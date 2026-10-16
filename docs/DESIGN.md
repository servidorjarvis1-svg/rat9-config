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

## 8. Abierto, y con qué evidencia

| Pregunta | Estado |
|---|---|
| ¿El R.A.T.9 inalámbrico tiene LEDs controlables por software? | **Sin pruebas.** Ningún índice responde con datos de LED. No se dibuja una pestaña de iluminación hasta tener canal. |
| ¿Qué es el registro `0x000B` = `0x0001`? | Desconocido. Se muestra en crudo. |
| Framing real de escritura del perfil | Documentado (`URB {Length=0x88, Function=0x17}` que traduce el filtro `SaiUsb`), **sin verificar**. Falta cerrar el dispatcher `0x13688-0x14180` o capturar USB con `usbmon`. |
| Escritura de DPI | Parámetros deducidos del driver de Windows, **sin verificar**. |
| ¿Nombre y descripción del repo público? | Pendiente de decidir antes de publicar. |

Hasta que la escritura no esté verificada, la interfaz **no** presenta cambiar el
DPI como una operación normal. La presentará como lo que es: una operación
experimental, aparte, que se pide explícitamente.
