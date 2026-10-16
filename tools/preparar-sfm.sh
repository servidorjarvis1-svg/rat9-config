#!/usr/bin/env bash
# Prepara los fotogramas para el SfM: las DOS series, cada una en su carpeta, con sus
# mascaras, a 2x.
#
# Por que separadas (esto costo un rato entenderlo): las dos series NO miden lo mismo
# (275x349 y 280x341; a 2x son 550x698 y 560x682). Con --ImageReader.single_camera 1
# COLMAP impone UNA camara a todas las imagenes, y al llegar a la primera de la otra
# medida la DESCARTA: de 48 imagenes acababa extrayendo 24, y el emparejado daba 276
# pares (que es C(24,2)) en vez de 1128. Ademas son dos rotaciones distintas, asi que
# mezclarlas no aporta nada.
#
# Por que 2x: a 280 px el detector de puntos encuentra muy pocos (594 medidos), y este
# objeto es oscuro y brillante. Duplicar ayuda algo; no lo arregla, pero es gratis.
#
# Los ficheros que produce NO van al repositorio: son material grafico del instalador
# original de Mad Catz. 3d/sfm/ esta en .gitignore.
#
#   Uso:  tools/preparar-sfm.sh
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORIGEN="${RAIZ}/docs/original-ui/extracted-from-installer"
SFM="${RAIZ}/3d/sfm"
Z=2

[ -d "$ORIGEN" ] || { echo "No encuentro el material del instalador en $ORIGEN"; exit 1; }
[ -d "${RAIZ}/3d/masks" ] || {
  echo "Faltan las mascaras en 3d/masks/ (las calcula el pipeline del 3D)."; exit 1; }

python_exe=/usr/bin/python3
"$python_exe" - "$ORIGEN" "$SFM" "$Z" <<'PY'
import subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image

origen, sfm, z = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
# el nombre de las mascaras del 3D es mask_s1_00..23 y mask_s2_24..47: la segunda serie
# CONTINUA la numeracion global, no reinicia. De ahi el error de la primera version.
series = [("s1", "275x349", 0), ("s2", "280x341", 24)]
total = 0
for etiqueta, patron, base in series:
    fs = sorted(f for f in origen.iterdir() if patron in f.name)
    if len(fs) != 24:
        print(f"  {etiqueta}: {len(fs)} ficheros, esperaba 24. Revisa el material.")
        sys.exit(1)
    img, msk = sfm / etiqueta / "images", sfm / etiqueta / "masks"
    for d in (img, msk):
        d.mkdir(parents=True, exist_ok=True)
    for i, f in enumerate(fs):
        nombre = f"{i + 1:02d}"
        subprocess.run(["/usr/bin/magick", str(f), "-resize", f"{z*100}%",
                        str(img / f"{nombre}.png")], check=True, capture_output=True)
        m = np.load(sfm.parent / f"masks/mask_{etiqueta}_{base + i:02d}.npy")
        m2 = np.repeat(np.repeat(m, z, axis=0), z, axis=1)
        Image.fromarray((m2 * 255).astype(np.uint8)).save(msk / f"{nombre}.png")
        total += 1
    print(f"  {etiqueta}: 24 imagenes + 24 mascaras")
print(f"  total {total} pares en {sfm}")
PY
echo "Ahora: tools/sfm-poses.sh"
