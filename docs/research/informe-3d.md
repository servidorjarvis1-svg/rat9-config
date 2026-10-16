# Informe: reconstrucción 3D del R.A.T.9 desde las rotaciones del instalador

Fecha: 2026-10-16 · Máquina: Arch Linux, RTX 2070 SUPER 8 GB (sm_75), 31 GB RAM, 20 cores, 448 GB libres.
Material: docs/original-ui/extracted-from-installer/ — 24 fotogramas @275x349 + 24 @280x341 (recurso del instalador `c9e4beb7`, giro de ~15°/paso, cámara fija elevada ~10°, fondo claro). Todo lo que sigue está MEDIDO, no supuesto.

## 1. Estado real del pipeline 3D de la máquina

| Componente | Estado | Evidencia |
|---|---|---|
| GPU / driver | OK. RTX 2070 SUPER, CUDA UMD 13.4, 7.6 GiB útiles | nvidia-smi |
| torch (3 venvs) | OK. 2.14.1+cu130, `cuda=True`, capacidad (7,5) | test directo en cada venv |
| spconv (comfyui-venv) | **FALLA: wheel solo-CPU**. forward CUDA → `RuntimeError ... not implemented for CPU ONLY build`. La ruta CPU sí convuelve | traceback ejecutado |
| TRELLIS.2 (ComfyUI-TRELLIS2 0.2.19) | **NO EJECUTABLE HOY**. El nodo se registra al arrancar ComfyUI, pero el env aislado `~/.ce/.pixi/envs/trellis2-nodes` no existe y los kernels que importa el VAE no están: `flex_gemm_ap` ModuleNotFoundError; el `flex_gemm` instalado solo trae `grid_sample`; `o_voxel_vb_ap` es un shim vacío; `comfy_sparse_attn.ops` no existe. Pesos sí presentes (15 GB en ~/comfyui/models/trellis2 + 6 GGUF en ~/3d-tools/models/trellis2, este último del callejón sin salida GGUF) | imports ejecutados + log de arranque de ComfyUI |
| ComfyUI | Arranca bien en comfyui-venv (server OK, 7793 MB VRAM) | boot test |
| nvdiffrast | importa (0.4.0); contexto GL headless sin probar | — |
| **Stable Fast 3D** | **FUNCIONA**. Repo en ~/3d-tools/stable-fast-3d con parches de memoria (pesos bf16 + SDPA por bloques en sf3d_safe.py), pesos descargados (3,8 GB en HF cache). Run completo en **18,5 s, pico 4,8 GB VRAM**, GLB texturizado. La sesión previa ya producía mesh.glb | ejecutado en esta sesión |
| rembg/u2net | OK (CPU). 48 recortes en ~2 min | ejecutado |
| onnxruntime-gpu (sf3d-venv) | roto para CUDA: falta libcudnn/libnvinfer → **rembg hay que fijarlo a CPUExecutionProvider** (parcheado run.py) | traceback |
| upscayl-ncnn | Funciona en 2 s (280→1120 px). **TRAMPA confirmada en persona**: nombre de modelo inválido (`-n real-esrgan-x4plus`, que no existe en /usr/share/upscayl/models) devuelve imagen NEGRA silenciosa. Modelos válidos: remacri-4x, ultrasharp-4x, digital-art-4x, high-fidelity-4x, ultramix-balanced-4x | comparado gradiente: 0,0 negro vs 3,12 válido |
| TripoSR | Repo + venv listos; **pesos NO descargados** (model.ckpt = 1,56 GB) | búsqueda en cachés |
| COLMAP / Meshroom / MeshLab | **No instalados.** COLMAP no está en repos oficiales de Arch (solo AUR: 4.2.0-4, 7 votos). yay+gcc16+cmake+ninja disponibles para compilar | pacman -Si, AUR RPC |
| Blender 5.2.2 | Binario arranca; **python embebido roto headless**: `No module named 'math'` (mismatch libpython/sistema tras actualización de python). bpy PyPI 5.2.2 es cp313 (esta máquina: sistema 3.14, venvs 3.11). Trabajo sin Blender posible vía renders numpy (se usó así) | ejecutado |
| Disco | 448 GB libres — espacio no es problema | df |

**Lo que FALLA hoy, en corto:** TRELLIS.2 (kernels sparse para cp311/torch2.14/sm75 no existen), spconv CUDA, onnxruntime CUDA en sf3d-venv, Blender headless. Todo lo demás funciona.

## 2. Viabilidad de la fotogrametría multivista con las 48 vistas

Qué hacen las vistas (medido con rembg + carve):
- 24 pasos ≈ 15°/frame, elevación ≈ 10° en AMBAS series (búsqueda en grilla de elevación/offset: mejor IoU con θ=10°, φ0=3° y 12°).
- Proporción ancho/alto de silueta: **ningún frame llega a 0,9** (máx 0,79–0,84): todas las vistas son oblicuas des de arriba, con un apéndide vertical giratorio ("cable") pegado encima. No hay vista lateral limpia ni baja ninguna.
- El elemento superior GIRA con el objeto (no es overlay de UI: std de 45–27 entre frames) → contamina TODAS las siluetas.
- Verificación extra en los 1832 ficheros extraídos: hay 384 sprites 280x340 más del mismo recurso (multiples colorways rojo/blanco/plata/negro intercalados), 72× 275x376, 72× 496x290 — **ninguna serie a mayor resolución ni con otra elevación**. El techo del material es este.

El experimento decisivo (visual hull SIN SfM, ~20 líneas de numpy sobre los 48 cutouts):
- Carve con rig conocido + refinado: **IoU silueta reproyectada 0,79 / 0,81 / 0,71 combinado** a 112³ voxeles.
- La malla resultante (`hull/rat9_hull.glb`): proporciones L:H ≈ **2,1–2,3:1**, morro estrecho, cola ancha — **se lee como ratón (6/10 como bloqueo)**. La misma prueba con SF3D desde una foto dio proporciones L:H 0,78–0,84 (torreta), 3/10.

Veredicto honesto por técnica:
- **SfM clásico (COLMAP/Meshroom)**: caso casi degenerado — centros de cámara coplanarios (una sola latitud), objeto oscuro con brillos especulares que se mueven (la luz no gira con el objeto), 280 px de resolución. Riesgo alto de fallo/careo; podría rescatar algo si upscaledas 4x y limitas el match a pares consecutivos. No es la vía con mejor esperanza aquí.
- **Hull por siluetas (rig conocido)**: probado, funciona, sin instalar nada. Es la única técnica que ya ha demostrado extraer geometría REAL de este material.
- **Lo que el material NO puede dar**: la base del ratón (ninguna cámara la ve), concavidades (hueco de la rueda, juntas — el hull las rellena), y textura nítida (280 px origen; 4x remacri da 1120 px interpolados).

## 3. Alternativas (ordenadas por probabilidad de merecer la pena)

### A. Visual hull por siluetas + textura retroproyectada — la recomendada
- Herramienta: script numpy propio (ya escrito y validado: `~/.hermes/cache/scratch/rat9/visual_hull.py`) + marching cubes (skimage, ya en sf3d-venv) + remallado `pynanoinstantmeshes` (ya en sf3d-venv).
- Coste: **0 MB nuevos, 0 €, ya funciona**. Textura: retroproyectar 24–48 vistas upscaled 4x sobre los UVs del hull (posiciones de cámara conocidas del rig; sin SfM).
- Riesgos: base plana inventada, concavidades perdidas (se modelan a mano), spike del "cable" (se limpia editando máscaras), textura blanda.

### B. SfM/MVS clásica — solo si hace falta densa
- COLMAP (AUR 4.2.0-4, ~500–700 MB con deps, build 15–40 min con 20 cores) o Meshroom binario Linux (descarga ≈1–1,5 GB con AliceVision; MVS necesita CUDA — sm_75 vale).
- Por qué no primero: degeneración parcial del rig + brillos móviles + 280 px. Probabilidad de malla densa limpia: baja-media. Útil solo como refinado del hull, no como base.

### C. Image-to-3D desde UNA vista — descartado para forma, útil para nada
- **SF3D: corre hoy** (18,5 s; 4,8 GB VRAM; parche de memoria ya en el repo) pero la forma sale **3/10** con estas vistas: la vista oblicua superior es el peor caso, inventa profundidad, proporciones al revés. Descartado como generador de forma.
- **TRELLIS.2**: bloqueado por arquitectura (kernels sparse inexistentes para cp311/torch2.14/CUDA13/sm75; probado con import exacto). Descartado hoy.
- **TripoSR**: correría (fp16, 4–6 GB) pero con el mismo problema de entrada; pesos no descargados (1,56 GB). Mismo resultado esperable que SF3D.
- **Hunyuan3D-2 / InstantMesh / SV3D**: más pesados (no caben o requieren compilar rasterizadores y descargas grandes) y mismo problema de entrada. Descartados.
- Conclusión (c): el cuello de botella no es el motor, es la ENTRADA (una vista oblicua superior de 280 px de un objeto oscuro y brillante). Ningún image-to-3D la salva.

### D. Camino intermedio (recomendado como variante del A)
- Geometría = hull (real) + **SF3D solo como textura/aspecto** (su GLB texturizado existe y funciona) o mejor: retroproyección de las fotos reales sobre el hull, que es textura VERDADERA del objeto. Con Blender arreglado (tarball oficial ~350 MB, o flatpak ~2 GB) la proyección/inpainting es cómoda; sin Blender, el pintor numpy ya sirve para validar.

## 4. Camino recomendado, paso a paso

1. *(hecho, 10 min, 0 MB)* Cutouts de los 48 frames con rembg + escala 4x remacri.
2. *(30–60 min, 0 MB)* Limpieza de máscaras: recortar el apéndice superior donde es fino (heurística de anchura de fila, ya esbozada) — repetir hull a N=160–192, suavizado gaussiano 1,5, marching cubes, decimar con pynanoinstantmeshes. Salida: **blockout GLB con proporciones reales** (el actual a 112³ ya da 6/10).
3. *(opcional, ~350 MB)* Reparar Blender: tarball oficial de blender.org (el pacman está roto headless) → proyección de las 24 vistas 4x sobre el hull con poses del rig (θ≈10°, 15°/paso, centro=bbox) + inpaint entre vistas → **GLB con textura del objeto real**. Alternativa sin Blender: proyección numpy sobre UVs (trimesh/xatlas ya en sf3d-venv).
4. *(opcional, 0 MB)* Pasada de belleza con la textura de SF3D sobre la geometría del hull corregida.
- Salida final esperable: GLB/obj con malla 20–60k tris y textura 1–2k plausible pero blanda (fuente 280 px). Coste: 0 €, ~4–6 GB de nuevo disco solo si se arregla Blender; tiempos: 1–2 h de trabajo total.
- Primer paso concreto (30 min): repetir el carve del hull con las máscaras limpiadas del apéndice superior a 160³ y mirar las 4 vistas — si el spike desaparece y la base queda bien terminada, el camino está confirmado.

## 5. Qué falta para un modelo DECENTE (sin inflar expectativas)

- **Cobertura polar**: el instalador solo da una banda de elevación (~10°). Sin vistas desde abajo o desde arriba, la base nunca se reconstruye — con ninguna técnica. Hace falta un segundo giro con la cámara baja (los sprites del instalador no lo traen: verificado) o fotos reales.
- **Resolución**: 280 px es un techo físico. Una serie de fotos reales a ~2000 px del RAT9 físico (teléfono, mesa giratoria, 3 elevaciones, luz difusa, fondo contrastado) valdría más que todo el material del instalador y habilitaría COLMAP/Meshroom de verdad.
- **El apéndice superior** ("cable"/mecanismo) en todas las vistas: sin separarlo, todo recorte/hull hereda un spike.
- **Un modelo con arte del instalador**: si el objetivo final es un modelo visual para un frontend de configuración, otra vía seria es RETRO-INGENIERÍA del recurso 3D original (el instalador renderiza un modelo real al vuelo; el .dll/.resource puede contener la malla o sprites más finos que los PNG extraídos — no se ha agotado esa mina; los 550x550 (61 ficheros) no han sido identificados).

## Artefactos de esta sesión
- Informe: este fichero (`docs/research/informe-3d.md`).
- Parche: `~/3d-tools/stable-fast-3d/run.py` (rembg fijado a CPUExecutionProvider — onnxruntime CUDA roto en ese venv).
- Experimentos y datos: `~/3d-tools/` + `~/rat9-config/3d/` (visual_hull.py, render_glb_trimesh.py, cutouts/, hull/, masks/, params.json, renders/, sheets de contacto). Nada más tocado en rat9-config.

---

## ADDENDA (medido después del informe — CORRIGE dos conclusiones de arriba)

El paso 1 de la sección 4 se ejecutó tal cual se recomendaba, y el resultado obliga a
corregir dos cosas de este informe. Se deja escrito aquí para que no se repita el
trabajo creyendo que faltaba probarlo.

### Lo que se hizo
- Pipeline reescrito como herramienta del repo: `tools/visual-hull.py` (carve + IoU +
  marching cubes + suavizado Taubin), con la limpieza del apéndice del paso 1.
- **Fidelidad comprobada**: a N=112 y SIN limpiar da **IoU 0,708**, el mismo número que
  reportaba este informe. La implementación reproduce la del informe; el resultado
  negativo no es un error de implementación.
- N=160 con limpieza: **IoU 0,793**, 211.284 caras, 104.936 vértices.

### Corrección 1 — la hipótesis del apéndice superior es FALSA
Decir que "contamina TODAS las siluetas" y que hay que "separarlo" para que no haya
spike era una suposición, no una medida. Medido: recortar las filas cuya anchura no
llega al 30% de la máxima quita **el 0,6% de los píxeles de silueta** (1.752.972 →
1.742.331). Es decir, **rembg ya se lo había comido**. No es la causa del pincho ni
del mal hull. El spike que se ve en las vistas es un artefacto del carve, no un
apéndice que quedara en las máscaras.

### Corrección 2 — la malla NO se lee como un ratón, y subir N no lo arregla
El informe decía "~6/10 como bloqueo, se lee como ratón (L:H 2,1–2,3:1)". Una lectura
fría de las cuatro vistas ortográficas del GLB a N=160 dice otra cosa: grietas,
rebabas, depresiones y artefactos; **solo en uno de los cuatro perfiles se intuye
algo**. Las proporciones medidas del volumen (0,45 : 0,89 : 1,06 en el espacio del
grid) no corresponden a un ratón bajo y alargado.

Y **no es cuestión de resolución de vóxel**: al pasar de 112³ a 160³ el IoU sube de
0,708 a 0,793 y la malla de 96k a 211k caras, y la forma sigue sin reconocerse. Es
**falta de información**, no de cómputo.

### Por qué falla, en una frase
Las 48 vistas están **todas en una sola banda de elevación (~10°)**. Un visual hull
construido con vistas de una sola latitud es un desbaste pobre **por construcción**:
el volumen que sobrevive a las 48 siluetas no es el objeto, es la intersección de 48
"prismas" oblicuos, y esa intersección rellena y deforma. Ninguna resolución de grid
arregla eso, y ninguna técnica por siluetas tampoco.

### Qué queda vivo
1. **Fotos reales del R.A.T.9 físico**: móvil, mesa giratoria, 2–3 alturas de cámara
   (no una), luz difusa, fondo contrastado. Valdría más que todo el material del
   instalador junto y habilitaría COLMAP/Meshroom de verdad.
2. ~~Sacar la malla original del instalador~~ — **DESCARTADO**. Dos motivos:
   - El "visor 3D giratorio" del software original **no es 3D**: son 24 fotogramas
     pre-renderizados (`Rotational.RAT9_01..24.png`), una ruleta de sprites. Si el
     visor usa sprites, **no hay malla que extraer** del DLL. La premisa de la que
     partía esta vía era falsa.
   - Los **61 PNG de 550x550** (la última pista) están revisados uno a uno en hoja de
     contactos: son **imágenes promocionales de toda la gama** Mad Catz/Cyborg
     (mandos, teclados, joysticks, ratones), con fondos variados y un panel de
     software. No hay serie ordenada de rotación, no hay vista inferior (la única
     candidata era una vista oblicua superior-lateral sin sensor ni patines) y no
     hay más resolución. Muestran el R.A.T.9 en varios ángulos sueltos, que no sirven
     para reconstruir: sin poses conocidas y con una vista por ángulo, no hay
     multivista.

**Por tanto: con este material no hay modelo 3D posible, y no queda ninguna vía
abierta por el lado del instalador.** Lo único que lo desbloquea son fotos reales del
aparato.

---

## SEGUNDA ADDENDA — la conclusión de arriba es FALSA. El rig estaba mal.

Lo anterior se apoyaba en dos cosas que, medidas, no se sostienen. Se deja escrito
porque es el error más caro de esta sesión.

### El material SÍ cubre todo el giro, incluida la base
El informe decía que "la base del ratón es irrecuperable: ninguna cámara la ve" y que
todas las vistas son de "una sola banda de elevación". **Falso.** Mirando los
fotogramas uno a uno, el **fotograma 12 muestra la cara INFERIOR**: la placa de la
base, el sensor y los patines. Con la cámara dando vueltas alrededor de un objeto
siempre derecho, la cara inferior no puede verse nunca. Verla significa que lo que
gira es **el objeto**, no la cámara.

### El movimiento es una RODADURA sobre el eje largo, y está medido
No hace falta creerse al modelo de visión: se mide la silueta de los 24 fotogramas de
la serie 1.

| | mínimo | máximo | recorrido sobre el medio |
|---|---|---|---|
| **ALTO** de la silueta (vertical) | 280 px | 348 px | **22%** |
| **ANCHO** de la silueta (horizontal) | 98 px | 224 px | **71%** |

El alto casi no se mueve y el ancho se desploma a menos de la mitad (98 px en los
fotogramas 6 y 18: el ratón de perfil). Eso es la firma exacta de **rodar sobre el eje
largo**: el largo es invariante y la sección transversal proyectada va cambiando. En
una peana de eje vertical, el alto variaría tanto como el ancho.

### Y por eso el IoU de 0,79 del primer intento era un FALSO POSITIVO
Se entiende ahora por qué el rig equivocado puntuaba alto: con el eje vertical, el
código mapeaba la **altura del objeto** a la **vertical de la imagen**. Como las
siluetas son altas (340 px), el tallado "explicaba" esas siluetas construyendo un
objeto **alto y estrecho** — y de hecho sus dimensiones salieron 0,45 : 0,89 : 1,06,
más alto que largo. Es decir: encajaba los contornos con un objeto con forma de
torre, no de ratón. **Un IoU alto con un objeto de forma equivocada no valida nada.**

### Estado real y qué falta
- El rig correcto es una rotación sobre el eje largo, con el largo del ratón en la
  **vertical** de la imagen (los fotogramas son verticales) y una relación
  largo:ancho **medida de 1,52:1** (340 px / 224 px). Con la rejilla cúbica de antes el
  objeto ni siquiera cabía: la rejilla daba 246 px de largo y el ratón mide 340.
- Con eso implementado (`tools/visual-hull-ejelargo.py`), mi tallado sigue puntuando
  **bajo (0,20)** frente al 0,79 del rig equivocado. **Tengo un fallo ahí que no he
  encontrado** (sospecha concreta: el cálculo de IoU proyecta los vóxeles como puntos
  sueltos y con rejilla gruesa deja huecos, lo que hunde artificialmente la medida,
  pero no está confirmado).
- Conclusión honesta: **el material es suficiente en principio y el movimiento ya está
  identificado**. Lo que no se puede es seguir adivinando el rig a mano: la vía
  correcta es **resolver las poses de cámara por SfM (COLMAP)**, que las calcula desde
  las propias imágenes en vez de que yo las suponga. Requiere compilar COLMAP del AUR
  (~500-700 MB, 15-40 min, `MAX_JOBS=8` por la regla del usuario de un solo build a la
  vez y con la paralelización limitada). **Hay que preguntar antes de compilar.**

### Lo que sí se puede hacer hoy, sin reconstruir nada
Las 48 vistas, tal cual, son una **ruleta de 24 fotogramas reales**: un visor en la app
donde el ratón gira al arrastrar. Es exactamente lo que hacía el software original
(que no era 3D, eran sprites) y da un ratón girando de verdad, sin inventar geometría.

### Dónde vive ahora el trabajo
`3d/` en el repo (scripts, las 48 máscaras, malla y parámetros; los binarios van en
`.gitignore`), porque `~/.hermes/cache/scratch/` **se poda a las 24 h** y se habría
perdido. La herramienta reproducible es `tools/visual-hull.py`.