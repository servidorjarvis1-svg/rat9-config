#!/usr/bin/env python3
"""gen_image.py — llama a MiniMax image-01 y guarda el resultado en disco.

Uso: gen_image.py <prompt> <salida.png> [ancho] [alto] [referencia.png]
"""
import base64, json, os, sys, urllib.request

ENV = os.path.expanduser("~/.hermes/.env")


def load_key():
    with open(ENV) as f:
        for line in f:
            if line.startswith("MINIMAX_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("MINIMAX_API_KEY no encontrada")


def main():
    prompt, out = sys.argv[1], sys.argv[2]
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    w = int(sys.argv[3]) if len(sys.argv) > 3 else 1920
    h = int(sys.argv[4]) if len(sys.argv) > 4 else 1080
    ref = sys.argv[5] if len(sys.argv) > 5 else None

    body = {
        "model": "image-01",
        "prompt": prompt[:1500],
        "aspect_ratio": "16:9" if w == 1920 else f"{w}:{h}",
        "response_format": "base64",
        "n": 1,
    }
    if ref and os.path.exists(ref):
        with open(ref, "rb") as f:
            body["subject_reference"] = [{
                "type": "character",
                "image": "data:image/png;base64," +
                         base64.b64encode(f.read()).decode(),
            }]

    req = urllib.request.Request(
        "https://api.minimax.io/v1/image_generation",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {load_key()}",
            "Content-Type": "application/json",
        })
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read())

    item = data["data"]["image_base64"]
    b64 = item[0] if isinstance(item, list) else item
    raw = base64.b64decode(b64)
    if raw[:3] == b"\xff\xd8\xff":          # la API devuelve JPEG
        with open(out + ".jpg", "wb") as f:
            f.write(raw)
        print(out + ".jpg")
    else:
        with open(out, "wb") as f:
            f.write(raw)
        print(out)


main()
