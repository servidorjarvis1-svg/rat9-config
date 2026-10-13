# Procedencia y atribución

`rat9-config` existe por ingeniería inversa del software oficial de Mad Catz para el
ratón R.A.T.9. Este documento explica de dónde sale cada pieza, para que quede claro
qué es nuestro y qué viene de ellos.

## Software de Mad Catz analizado

- **Nombre:** Mad Catz Software 7.0.45.2 (el que controlaba el R.A.T.9 y el R.A.T.7)
- **Autor original:** Mad Catz / Saitek (los directorios de código fuente filtrados
  en los PDB muestran `c:\code\mercurial\sd\`, confirmando desarrollo interno con Mercurial)
- **Obtenido de:** el paquete de archivo `software-x-64-fre-7-0-45-2`
  de Internet Archive. El CDN oficial (`downloads.madcatzhosting.com`) dejó de servir
  ficheros tras el cierre de Mad Catz en 2020.
- **Licencia original:** software propietario de Mad Catz. No se distribuye aquí
  ningún binario suyo.

### Qué contienen sus binarios y qué usamos

| Pieza | Origen | Cómo la usamos |
|---|---|---|
| Esquema de perfil `schema_sd.pr0` | Recurso embebido en `Saitek.Common.dll` | **Reproducido literalmente** en `rat9/schema.py` |
| Formato del perfil (cabecera + UTF-16LE) | Clase `TorontoDevice.SetProfile` | Reimplementado, no copiado |
| Constantes de lectura USB (`0x90`/`0x74`/`0xBA`) | Análisis de `hid.sys`, `usb.sys` y `SaiMini.sys` | Verificadas empíricamente contra hardware |
| Nombres de nodos del esquema | `SaiNode.Schema.SD.Schema.RegisterNodes` | Reproducidos como lista |

## Proyecto previo del que parte este trabajo

El trabajo de la comunidad que hizo esto viable antes que nosotros:

- **[MayeulC/Saitek](https://github.com/MayeulC/Saitek)** — `ratctl.py`, GPLv3.
  Documentó el protocolo USB de los R.A.T. Originalmente para los modelos
  Saitek (`06a3:0cfa`, `06a3:0cd9`); su wiki avisa explícitamente que el
  `0738:1709` (Mad Catz) estaba *sin confirmar*. Hemos confirmado que **no aplica**:
  sus índices para leer DPI devuelven PIPE en esta unidad.
- **[np/MadCatz](https://github.com/np/MadCatz)** — variante con GUI del mismo trabajo.

Nos apoyamos en su enfoque y su wiki, y corregimos sus conclusiones para este hardware.

## Lo que es nuestro

Todo el código de este repositorio:

- `rat9/protocol.py` — la capa USB, reimplementada desde cero y verificada con mediciones propias
- `rat9/cli.py`, `rat9/server.py`, `rat9/web/` — CLI, API e interfaz, de nuestra autoría
- El descubrimiento empírico de que el canal de escritura es `SET_REPORT` con report ID 0
  y de que solo existen dos registros de lectura (`0x0074` y `0x00BA`)

## Advertencia sobre el uso

Mad Catz cerró en 2020 y su software es software propietario. Este proyecto existe
para fines de compatibilidad con hardware ya en circulación y para documentar un
protocolo que nadie había legítimamente documentado para este modelo concreto.

Si eres el titular de los derechos y quieres que retiremos material derivado,
abre un issue y lo retiramos.

## Licencia de este proyecto

GPL-3.0, la misma que usa el proyecto previo del que derivamos el conocimiento.
