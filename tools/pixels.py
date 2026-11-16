"""Outils de pixels partagés."""
import numpy as np


def components(mask):
    """composantes connexes (8 voisins) : (x0, y0, x1, y1, masque de la composante dans son rectangle)"""
    h, w = mask.shape
    label = np.zeros((h, w), np.int32)
    out = []
    for y0, x0 in zip(*np.nonzero(mask)):
        if label[y0, x0]:
            continue
        n = len(out) + 1
        stack, ys, xs = [(y0, x0)], [], []
        label[y0, x0] = n
        while stack:
            y, x = stack.pop()
            ys.append(y)
            xs.append(x)
            for ny in (y - 1, y, y + 1):
                for nx in (x - 1, x, x + 1):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not label[ny, nx]:
                        label[ny, nx] = n
                        stack.append((ny, nx))
        bx0, by0, bx1, by1 = min(xs), min(ys), max(xs), max(ys)
        out.append((bx0, by0, bx1, by1, label[by0:by1 + 1, bx0:bx1 + 1] == n))
    return out


def grow(mask, r):
    """masque élargi de r pixels (carré), pour regrouper les pixels proches"""
    out = mask.copy()
    h, w = mask.shape
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
            xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
            out[yd, xd] |= mask[ys, xs]
    return out


def groups(mask, small=64, reach=6, gap=1):
    """morceaux : pixels à 2 × `gap` px ou moins les uns des autres ; un fragment de moins de `small` pixels rejoint le morceau
    le plus proche à `reach` px ou moins (dessin en points séparés), deux morceaux plus grands ne fusionnent jamais.
    Retourne (x0, y0, x1, y1, masque)."""
    parts = []
    for gx0, gy0, gx1, gy1, gm in components(grow(mask, gap)):
        own = mask[gy0:gy1 + 1, gx0:gx1 + 1] & gm
        ys, xs = own.nonzero()
        if len(ys):
            parts.append([gx0 + xs.min(), gy0 + ys.min(), gx0 + xs.max(), gy0 + ys.max(), len(ys),
                          own[ys.min():ys.max() + 1, xs.min():xs.max() + 1]])
    root = list(range(len(parts)))

    def find(i):
        while root[i] != i:
            root[i] = root[root[i]]
            i = root[i]
        return i

    def dist(a, b):
        return max(0, b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3])

    for i, a in enumerate(parts):
        if a[4] >= small:
            continue
        near = [(dist(a, b), j) for j, b in enumerate(parts) if j != i and dist(a, b) <= reach]
        if near:
            root[find(i)] = find(min(near)[1])
    merged = {}
    for i, a in enumerate(parts):
        box = merged.setdefault(find(i), list(a[:4]))
        box[:] = [min(box[0], a[0]), min(box[1], a[1]), max(box[2], a[2]), max(box[3], a[3])]
    out = []
    label = {}
    for i, a in enumerate(parts):
        label.setdefault(find(i), []).append(a)
    for r, (x0, y0, x1, y1) in merged.items():
        own = np.zeros((y1 - y0 + 1, x1 - x0 + 1), bool)
        for a in label[r]:
            own[a[1] - y0:a[3] - y0 + 1, a[0] - x0:a[2] - x0 + 1] |= a[5]
        out.append((x0, y0, x1, y1, own))
    return out


def drawing_key(a, ink):
    """dessin d'une image, fonds et marges ôtés : forme des pixels dessinés et leurs couleurs"""
    ys, xs = ink.nonzero()
    box = (slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1))
    sub, mask = a[box], ink[box]
    return (sub.shape[:2], mask.tobytes(), sub[mask][:, :3].tobytes())


def rects_mask(shape, rects):
    """masque des rectangles [x, y, l, h]"""
    m = np.zeros(shape, bool)
    for x, y, w, h in rects:
        m[y:y + h, x:x + w] = True
    return m
