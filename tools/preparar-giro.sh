#!/usr/bin/env bash
# Prepara los fotogramas del VISOR DE ROTACION del raton.
#
# Por que este guion y no los PNG a pelo en el repo: los fotogramas son material
# grafico del instalador original de Mad Catz, no nuestro. El repositorio publica
# el codigo y el esquema de protocolo (con atribucion, ver PROVENANCE.md), pero no
# los recursos graficos ajenos. Este guion los saca de TU copia local del
# instalador y los deja en rat9/ui/assets/giro/, que esta fuera del control de
# versiones. Si no existen, la app simplemente no ofrece la vista "Giro".
#
# El orden importa y NO es alfabetico por casualidad: los ficheros van por offset
# dentro de la DLL, y resulta que ese orden ES el del giro. Se comprobo midiendo el
# ancho de la silueta en los 24 fotogramas: 224, 193, 98, 188, 224, 193, 98, 188,
# 217... una curva suave y periodica. Si estuvieran desordenados, daria saltos.
#
#   Uso:  tools/preparar-giro.sh            # 24 fotogramas, 3x
#         tools/preparar-giro.sh --zoom 4  # mas grandes (mas disco, misma info)
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORIGEN="${RAIZ}/docs/original-ui/extracted-from-installer"
DESTINO="${RAIZ}/rat9/ui/assets/giro"
PATRON="275x349"
ZOOM=3
MODELOS=/usr/share/upscayl/models
MODELO=remacri-4x

while [ $# -gt 0 ]; do
  case "$1" in
    --zoom) ZOOM="$2"; shift 2 ;;
    --origen) ORIGEN="$2"; shift 2 ;;
    *) echo "opcion desconocida: $1" >&2; exit 2 ;;
  esac
done

if [ ! -d "$ORIGEN" ]; then
  echo "No encuentro el material del instalador en:"
  echo "  $ORIGEN"
  echo "Los fotogramas salen de ahi (ver docs/ENTORNO.md). Sin ellos la vista"
  echo "'Giro' no aparece en la app, y no pasa nada mas."
  exit 1
fi

mapfile -t FRAMES < <(find "$ORIGEN" -maxdepth 1 -name "*${PATRON}.png" | sort)
if [ "${#FRAMES[@]}" -ne 24 ]; then
  echo "Esperaba 24 fotogramas de ${PATRON} y he encontrado ${#FRAMES[@]}."
  echo "Revisa el material antes de seguir."
  exit 1
fi

mkdir -p "$DESTINO"
i=0
for f in "${FRAMES[@]}"; do
  i=$((i + 1))
  crudo=$(printf "%s/.crudo-%02d.png" "$DESTINO" "$i")
  # upscayl-ncnn: si no se le pasa -m, busca los modelos en /usr/share/upscayl/bin/models
  # (que no existe) y DEVUELVE UNA IMAGEN NEGRA SIN DAR ERROR. Por eso el -m va fijo.
  /usr/bin/upscayl-ncnn -i "$f" -o "$crudo" -n "$MODELO" -z "$ZOOM" -m "$MODELOS" >/dev/null 2>&1
  # Se queda en 550 px de ancho: el render de al lado mide 700 y no hace falta mas.
  # En WebP pesa ~10 veces menos que en PNG, y son 24 fotogramas que se cargan
  # todos: en PNG eran 30 MB y en WebP son 1,5.
  /usr/bin/magick "$crudo" -resize 550x -quality 88 "$(printf "%s/%02d.webp" "$DESTINO" "$i")"
  rm -f "$crudo"
  printf "  %02d/24\n" "$i"
done

echo
echo "listos ${i} fotogramas en rat9/ui/assets/giro/"
echo "Comprobacion de que NO han salido en negro (el fallo silencioso de upscayl):"
/usr/bin/magick identify -format "  %f  %wx%h  brillo medio %[mean]\n" "$DESTINO"/*.webp | head -4
echo "  (un 0 en brillo medio = imagen negra: el modelo no se encontro)"
