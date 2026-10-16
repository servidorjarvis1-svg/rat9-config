#!/usr/bin/env bash
# Resuelve las POSES DE CAMARA de los 48 fotogramas con COLMAP (SfM).
#
# Por que SfM y no seguir adivinando el rig: en dos intentos modele el movimiento a
# mano (peana de eje vertical, luego rodadura sobre el eje largo) y los dos dieron
# formas que no se reconocen. Medido, el movimiento SI es una rodadura (el alto de
# la silueta varia un 22% y el ancho un 71%), pero de ahi a tener la geometria exacta
# hay un trecho. COLMAP no adivina: saca las poses de las propias imagenes, y ademas
# te dice si ha podido o no.
#
# Las MASCARAS son la clave aqui: el objeto es oscuro y brillante sobre fondo oscuro,
# y sin mascara el extractor se llena de puntos del fondo que no pertenecen al raton
# y arruinan la triangulacion. Van las que ya calculo el 3D.
#
# Uso:
#   tools/sfm-poses.sh                 # las 48 vistas
#   tools/sfm-poses.sh --threads 8     # limite de nucleos (regla del usuario)
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SFM="${RAIZ}/3d/sfm"
NUCLEOS=8

while [ $# -gt 0 ]; do
  case "$1" in
    --threads) NUCLEOS="$2"; shift 2 ;;
    *) echo "opcion desconocida: $1" >&2; exit 2 ;;
  esac
done

if [ ! -d "$SFM/images" ] || [ "$(ls -1 "$SFM/images" | wc -l)" -lt 24 ]; then
  echo "Faltan los fotogramas preparados en 3d/sfm/. Preparalos primero."
  exit 1
fi
command -v colmap >/dev/null || { echo "COLMAP no esta instalado."; exit 1; }

rm -rf "$SFM/sparse" "$SFM/db.db"
mkdir -p "$SFM/sparse"

echo "== 1/3  puntos caracteristicos (con mascara, sin GPU) =="
colmap feature_extractor \
  --database_path "$SFM/db.db" \
  --image_path "$SFM/images" \
  --ImageReader.mask_path "$SFM/masks" \
  --ImageReader.single_camera 1 \
  --SiftExtraction.use_gpu 0 \
  --SiftExtraction.num_threads "$NUCLEOS" \
  --SiftExtraction.max_num_features 8192 2>&1 | tail -6

echo
echo "== 2/3  emparejado exhaustivo (48 vistas = 1128 pares) =="
colmap exhaustive_matcher \
  --database_path "$SFM/db.db" \
  --SiftMatching.use_gpu 0 \
  --SiftMatching.num_threads "$NUCLEOS" \
  --TwoViewGeometry.min_num_inliers 12 2>&1 | tail -6

echo
echo "== 3/3  reconstruccion (aqui se ve si sale o no) =="
colmap mapper \
  --database_path "$SFM/db.db" \
  --image_path "$SFM/images" \
  --output_path "$SFM/sparse" \
  --Mapper.num_threads "$NUCLEOS" \
  --Mapper.ba_global_function_tolerance 1e-5 2>&1 | tail -12

echo
echo "== RESULTADO =="
for d in "$SFM"/sparse/*/; do
  [ -d "$d" ] || continue
  n=$(colmap model_analyzer --path "$d" 2>/dev/null | grep -c "Pose" || true)
  printf "  %s -> %s imagenes con pose\n" "$(basename "$d")" "$n"
done
ls -1 "$SFM/sparse" 2>/dev/null | wc -l | sed 's/^/  submodelos: /'
