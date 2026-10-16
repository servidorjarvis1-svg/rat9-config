# Entorno de trabajo

Notas de dónde se prueba y qué hay instalado. Para no volver a averiguarlo.

## Pantallas (Hyprland)

| id | salida | resolución | posición | workspace | uso |
|---|---|---|---|---|---|
| 0 | `HDMI-A-1` | 1920×1080@60, escala 1.333 | (3840,0) | 1 | **el usuario**: aquí vive Hermes |
| 1 | `DP-2` | 1920×1080@144 | (1920,0) | 2 | **nuestra**: pruebas y ventanas de trabajo |
| 2 | `DP-3` | 1920×1080@72 | (0,0) | 3 | el usuario |

**Regla:** todo lo que abramos para probar (navegador de automatización, la
ventana de la app, capturas) va al **workspace 2 / DP-2**, sin robar el foco de
la pantalla del usuario. El usuario dejó esa pantalla para el desarrollo.

## Acceso al ratón

Sin root, con las reglas `99-rat9.rules` instaladas (grupo `rat9`, usuario dentro).
Verificado: lectura de perfil, batería y los 4 DPI funcionando como usuario normal.

## Navegador de automatización

Brave por CDP en `127.0.0.1:9222`. Arranque: `~/.local/bin/browser-cdp-start.sh`.
Ya abre en DP-2. Parada: `browser-cdp-stop.sh`.

## Intérpretes

- `/usr/bin/python3` (3.14) tiene `gi` (Gtk 4.24, Adw 1.10, **WebKit 6.0**) y
  `usb1`. O sea: la app nativa no necesita el venv de Hermes ni instalar nada.
- Herramientas de la casa: `ilspycmd` en `~/.dotnet/tools` (para descompilar
  .NET si hace falta volver al software original).
