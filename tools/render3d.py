"""Aperçu PNG d'un modèle 3D : projection orthographique, tampon de profondeur, sans ajout. `up` : axe vertical
du modèle ('y' pour COLLADA sans axe précisé, 'z' pour le monde de Galaxy55).

Sans texture : gris uni éclairé (lumière fixe, faces vues des deux côtés). Avec texture (porte de Galaxy55) : couleur
de la texture aux coordonnées du modèle, multipliée par l'ombrage stocké dans le fichier ; pixels transparents ignorés.
"""
import math
import numpy as np
from PIL import Image

LIGHT = np.array([-0.45, 0.7, -0.55]) / np.linalg.norm([-0.45, 0.7, -0.55])
GREY = np.array([188, 192, 202], float)


def thumbnail(objects, tex, out, size, up='z', ss=2, az=-35, el=22):
    P = np.concatenate([np.array(o['pos'], float).reshape(-1, 3) for o in objects])
    if up == 'y':
        P = np.stack([P[:, 0], -P[:, 2], P[:, 1]], axis=1)
    uv = shade = None
    if tex and all(o.get('uv') for o in objects):
        uv = np.concatenate([np.array(o['uv'], float).reshape(-1, 2) for o in objects])
        shade = np.concatenate([np.array(o['shade'], float) for o in objects])
        texture = np.asarray(Image.open(tex).convert('RGBA'))
    q = P - (P.min(0) + P.max(0)) / 2
    a, e = math.radians(az), math.radians(el)
    x = q[:, 0] * math.cos(a) - q[:, 1] * math.sin(a)
    y = q[:, 0] * math.sin(a) + q[:, 1] * math.cos(a)
    sy = q[:, 2] * math.cos(e) - y * math.sin(e)
    depth = y * math.cos(e) + q[:, 2] * math.sin(e)
    W = size * ss
    span = max(x.max() - x.min(), sy.max() - sy.min()) or 1
    k = W * 0.86 / span
    px, py = W / 2 + x * k, W / 2 - sy * k
    img = np.zeros((W, W, 4), float)
    zbuf = np.full((W, W), np.inf)
    for t in range(len(P) // 3):
        i = slice(t * 3, t * 3 + 3)
        X, Y, Z = px[i], py[i], depth[i]
        x0, x1 = max(0, int(X.min())), min(W - 1, int(math.ceil(X.max())))
        y0, y1 = max(0, int(Y.min())), min(W - 1, int(math.ceil(Y.max())))
        if x0 > x1 or y0 > y1:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        d = (Y[1] - Y[2]) * (X[0] - X[2]) + (X[2] - X[1]) * (Y[0] - Y[2])
        if abs(d) < 1e-9:
            continue
        w0 = ((Y[1] - Y[2]) * (gx - X[2]) + (X[2] - X[1]) * (gy - Y[2])) / d
        w1 = ((Y[2] - Y[0]) * (gx - X[2]) + (X[0] - X[2]) * (gy - Y[2])) / d
        w2 = 1 - w0 - w1
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        z = w0 * Z[0] + w1 * Z[1] + w2 * Z[2]
        win = zbuf[y0:y1 + 1, x0:x1 + 1]
        ok = inside & (z < win)
        if uv is not None:
            u = w0 * uv[i][0, 0] + w1 * uv[i][1, 0] + w2 * uv[i][2, 0]
            v = w0 * uv[i][0, 1] + w1 * uv[i][1, 1] + w2 * uv[i][2, 1]
            tx = np.clip((u * texture.shape[1]).astype(int), 0, texture.shape[1] - 1)
            ty = np.clip((v * texture.shape[0]).astype(int), 0, texture.shape[0] - 1)
            texel = texture[ty, tx].astype(float)
            ok &= texel[..., 3] >= 128
            s = w0 * shade[i][0] + w1 * shade[i][1] + w2 * shade[i][2]
            rgb = texel[..., :3] * np.clip(s, 0, 1)[..., None]
        else:
            Zk = Z * k  # même échelle que X et Y
            n = np.cross([X[1] - X[0], Y[0] - Y[1], Zk[1] - Zk[0]], [X[2] - X[0], Y[0] - Y[2], Zk[2] - Zk[0]])
            n = n / (np.linalg.norm(n) or 1)
            rgb = np.broadcast_to(GREY * (0.38 + 0.62 * abs(float(n @ LIGHT))), z.shape + (3,))
        win[ok] = z[ok]
        tile = img[y0:y1 + 1, x0:x1 + 1]
        tile[ok, :3] = rgb[ok]
        tile[ok, 3] = 255
    im = Image.fromarray(img.clip(0, 255).astype(np.uint8), 'RGBA').convert('RGBa')
    im.resize((size, size), Image.LANCZOS).convert('RGBA').save(out, optimize=True)
