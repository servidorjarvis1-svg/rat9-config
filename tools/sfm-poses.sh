#!/usr/bin/env bash
# Resuelve las POSES DE CAMARA de los fotogramas con COLMAP (SfM), UNA SERIE A LA VEZ.
#
# Por que SfM y no seguir adivinando el rig: en dos intentos modele el movimiento a
# mano (peana de eje vertical, luego rodadura sobre el eje largo) y los dos dieron
# formas que no se reconocen. Medido, el movimiento SI es una rodadura (el alto de la
# silueta varia un 22% y el ancho un 71%), pero de ahi a tener la geometria exacta hay
# un trecho. COLMAP no adivina: saca las poses de las propias imagenes, y ademas te
# dice si ha podido o no.
#
# Las MASCARAS son la clave aqui: el objeto es oscuro y brillante sobre fondo oscuro,
# y sin mascara el extractor se llena de puntos del fondo que no pertenecen al raton
# y arruinan la triangulacion. Van las que ya calculo el 3D.
#
# POR QUE UNA SERIE A LA VEZ (esto costo un rato entenderlo): las dos series NO miden
# lo mismo (275x349 y 280x341; a 2x, 550x698 y 560x682). Con --ImageReader.single_camera 1
# COLMAP impone UNA camara a todas las imagenes, y al llegar a la primera de la otra
# medida la DESCARTA: de 48 imagenes acababa extrayendo 24. La pista que lo delata es
# el emparejado: daba 276 pares, que es C(24,2), cuando un exhaustivo de 48 son 1128.
# Y ademas son dos rotaciones distintas, asi que mezclarlas no aporta nada.
#
# Uso:
#   tools/sfm-poses.sh                 # las dos series
#   tools/sfm-poses.sh --serie s1      # solo una
#   tools/sfm-poses.sh --threads 8     # limite de nucleos (regla del usuario)
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SFM="${RAIZ}/3d/sfm"
NUCLEOS=8
SERIES="s1 s2"

while [ $# -gt 0 ]; do
  case "$1" in
    --threads) NUCLEOS="$2"; shift 2 ;;
    --serie)   SERIES="$2"; shift 2 ;;
    *) echo "opcion desconocida: $1" >&2; exit 2 ;;
  esac
done
command -v colmap >/dev/null || { echo "COLMAP no esta instalado."; exit 1; }

for serie in $SERIES; do
  D="${SFM}/${serie}"
  if [ ! -d "$D/images" ]; then
    echo "== ${serie}: sin fotogramas preparados, me lo salto =="
    continue
  fi
  n=$(ls -1 "$D/images" | wc -l)
  echo "==============================================================="
  echo "== SERIE ${serie}: ${n} vistas =="
  echo "==============================================================="
  rm -rf "$SFM/sparse-${serie}" "$SFM/db-${serie}.db"
  mkdir -p "$SFM/sparse-${serie}"

  echo "-- 1/3  puntos caracteristicos (con mascara, sin GPU) --"
  # OJO con los nombres: COLMAP 4.x los cambio. Ya no son --SiftExtraction.use_gpu ni
  # --SiftMatching.num_threads, sino --FeatureExtraction.* y --FeatureMatching.*. Con
  # los viejos aborta con "unrecognised option" y no hace absolutamente nada.
  colmap feature_extractor \
    --database_path "$SFM/db-${serie}.db" \
    --image_path "$D/images" \
    --ImageReader.mask_path "$D/masks" \
    --ImageReader.single_camera 1 \
    --FeatureExtraction.use_gpu 0 \
    --FeatureExtraction.num_threads "$NUCLEOS" \
    --SiftExtraction.max_num_features 8192 2>&1 \
    | grep -cE "Features:" | sed 's/^/     imagenes procesadas: /'

  echo "-- 2/3  emparejado exhaustivo --"
  colmap exhaustive_matcher \
    --database_path "$SFM/db-${serie}.db" \
    --FeatureMatching.use_gpu 0 \
    --FeatureMatching.num_threads "$NUCLEOS" 2>&1 \
    | grep -E "Elapsed" | tail -1 | sed 's/^/     /'
  echo "     pares con geometria verificada: $(sqlite3 "$SFM/db-${serie}.db" 'SELECT COUNT(*) FROM two_view_geometries;')"

  echo "-- 3/3  reconstruccion (aqui se ve si sale o no) --"
  colmap mapper \
    --database_path "$SFM/db-${serie}.db" \
    --image_path "$D/images" \
    --output_path "$SFM/sparse-${serie}" \
    --Mapper.num_threads "$NUCLEOS" 2>&1 \
    | grep -E "Registering|Could not|Discarding|No good" | tail -4 | sed 's/^/     /'

  echo "-- RESULTADO --"
  if [ -d "$SFM/sparse-${serie}/0" ]; then
    colmap model_analyzer --path "$SFM/sparse-${serie}/0" 2>/dev/null | head -8 | sed 's/^/     /'
  else
    echo "     SIN reconstruccion: el submodelo 0 no existe"
  fi
  echo
done
