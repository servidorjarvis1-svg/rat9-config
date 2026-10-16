#!/usr/bin/env python3
"""Renderiza un GLB a 4 vistas ortograficas con pintor por caras (PIL), flat shading
usando la textura difusa del GLB. No necesita GL ni Blender: puro numpy/PIL.

    python render_glb_pil.py <glb> <dir_salida>
"""
import json
import os
import struct
import sys

import numpy as np
from PIL import Image


def load_glb(path):
    d = open(path, "rb").read()
    ln = struct.unpack("<I", d[12:16])[0]
    js = json.loads(d[20:20 + ln])
    off = 20 + ln
    bln = struct.unpack("<I", d[off:off + 4])[0]
    blob = d[off + 8:off + 8 + bln]

    def acc(i):
        a = js["accessors"][i]
        ct = {5120: "b", 5121: "B", 5122: "h", 5123: "H", 5125: "I", 5126: "f"}[a["componentType"]]
        n = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[a["type"]] * a["count"]
        s = np.dtype(ct).itemsize * n
        return np.frombuffer(blob, ct, count=n, offset=a.get("byteOffset", 0))

    prim = js["meshes"][0]["primitives"][0]
    pos = acc(prim["attributes"]["POSITION"]).reshape(-1, 3)
    idx = acc(prim["indices"]).reshape(-1, 3)
    uv, tex = None, None
    if "TEXCOORD_0" in prim["attributes"]:
        uv = acc(prim["attributes"]["TEXCOORD_0"]).reshape(-1, 2)
    imgs = js.get("images", [])
    if imgs:
        ii = js["materials"][prim["material"]].get("pbrMetallicRoughness", {}).get("baseColorTexture", {}).get("index")
        if ii is not None:
            vi = imgs[ii].get("bufferView")
            if vi is None:  # imagen dentro del blob apuntada por uri data
                uri = imgs[ii].get("uri", "")
                import base64
                if uri.startswith("data:"):
                    from io import BytesIO
                    tex = Image.open(BytesIO(base64.b64decode(uri.split(",", 1)[1])).read() and None or base64.b64decode(uri.split(",", 1)[1])).convert("RGB")
                    tex = Image.open(BytesIO(base64.b64decode(uri.split(",", 1)[1])))
            else:
                bv = js["bufferViews"][vi]
                from io import BytesIO
                tex = Image.open(BytesIO(blob[bv.get("byteOffset", 0): bv.get("byteOffset", 0) + bv["byteLength"]]))
        if tex is not None:
            tex = tex.convert("RGB").resize((1024, 1024))
            tex = np.asarray(tex)
    return pos.astype(np.float64), idx.astype(np.int64), uv, tex


def render_view(pos, idx, uv, tex, az_deg, out, W=560, elev_deg=12):
    az, el = np.radians(az_deg), np.radians(elev_deg)
    c, s = np.cos(az), np.sin(az)
    Rz = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])
    ce, se = np.cos(el), np.sin(el)
    Rx = np.array([[1, 0, 0], [0, ce, -se], [0, se, ce]])
    P = (Rx @ Rz @ pos.T).T
    lo, hi = P.min(0), P.max(0)
    scale = 0.82 * min(W, W) / (hi - lo).max()
    X = (P[:, 0] - (lo[0] + hi[0]) / 2) * scale + W / 2
    Y = W - ((P[:, 1] - (lo[1] + hi[1]) / 2) * scale + W / 2)
    Z = P[:, 2]
    img = Image.new("RGB", (W, W), (88, 96, 108))
    from PIL import ImageDraw
    dr = ImageDraw.Draw(img)
    tris = idx
    zc = Z[tris].mean(1)
    order = np.argsort(zc)
    # luz desde arriba-izq-frente
    light = np.array([-0.35, -0.5, 0.79])
    n = np.cross(P[tris[:, 1]] - P[tris[:, 0]], P[tris[:, 2]] - P[tris[:, 0]])
    nn = np.linalg.norm(n, axis=1) + 1e-12
    n_ = n / nn[:, None]
    lam = np.clip((n_ @ light), 0.15, 1.0)
    if uv is not None and tex is not None:
        uvc = np.clip((uv[tris].mean(1) * 1024), 0, 1023).astype(int)
        col = tex[uvc[:, 1], uvc[:, 0]]
    else:
        col = np.full((len(tris), 3), 150)
    coln = (col * lam[:, None]).clip(0, 255).astype(np.uint8)
    for t in order:
        a, b, c3 = tris[t]
        dr.polygon([(X[a], Y[a]), (X[b], Y[b]), (X[c3], Y[c3])], fill=tuple(coln[t]))
    img.save(out)


pos, idx, uv, tex = load_glb(sys.argv[1])
outdir = sys.argv[2]
os.makedirs(outdir, exist_ok=True)
print("verts", len(pos), "faces", len(idx), "uv", uv is not None, "tex", tex is not None)
print("dimensiones modelo:", np.round(pos.max(0) - pos.min(0), 4))
for i, az in enumerate([0, 90, 180, 270]):
    render_view(pos, idx, uv, tex, az, os.path.join(outdir, f"v_{i}.png"))
print("OK 4 vistas")