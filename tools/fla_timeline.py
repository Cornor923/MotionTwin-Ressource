"""Ligne de temps des symboles de .fla : état d'un symbole à une image donnée, pour fla_compose.

Calque : {'frames': [image clé], 'elements': éléments de la première}. Image clé : {'start', 'dur', 'elements',
'tween' ('motion', 'shape' ou None), 'ease' (-100..100), 'rotate' (sens), 'turns'} (fla_bin.py, xfl.py). Un calque sans
'frames' (ancien format) est une seule image.

Interpolation classique (« motion ») entre une image clé et la suivante, élément par élément quand les deux sont des
instances : matrice décomposée (échelles, angles des axes x et y) et point de transformation interpolés, position
de ce point linéaire ; accélération t' = t - a·t·(1 - t) (a = valeur enregistrée / 100, vérifié sur les SWF) ; couleur
linéaire. Les interpolations de forme gardent la forme de l'image clé (non décodées).

Symboles placés : un clip déroule sa propre ligne de temps depuis l'image où il apparaît (même symbole au même
rang dans les images clés qui se suivent = même instance) ; un graphique suit celle du parent depuis sa première
image (boucle, une fois ou image fixe) ; un bouton reste sur sa première image.
"""
import math

LOOP, ONCE, SINGLE = 1, 2, 3


def length(layers):
    return max([k['start'] + k['dur'] for l in layers for k in l.get('frames') or []] or [1])


def labels(layers):
    """étiquettes d'images du symbole, dans l'ordre (« nom (image n) »)"""
    found = sorted({(k['start'], k['label']) for l in layers for k in l.get('frames') or [] if k.get('label')})
    return ['%s (%d)' % (name, start + 1) for start, name in found]


def at(doc, name, f):
    """calques du symbole `name` à l'image `f` (mêmes clés que les calques statiques), mis en cache dans doc"""
    cache = doc.setdefault('_frames', {})
    key = (name, f)
    if key not in cache:
        layers = doc['symbols'][name]
        cache[key] = [dict(layer, elements=layer_at(doc, layer, f)) if layer.get('frames') else layer
                      for layer in layers]
    return cache[key]


def layer_at(doc, layer, f):
    frames = layer['frames']
    i = next((i for i, k in enumerate(frames) if k['start'] <= f < k['start'] + k['dur']), None)
    if i is None:
        return []
    k = frames[i]
    nxt = frames[i + 1] if i + 1 < len(frames) and frames[i + 1]['start'] == k['start'] + k['dur'] else None
    t = (f - k['start']) / k['dur']
    t = t - k.get('ease', 0) / 100 * t * (1 - t)
    out = []
    for j, el in enumerate(k['elements']):
        if el[0] != 'use':
            out.append(el)
            continue
        if k.get('tween') == 'motion' and nxt and j < len(nxt['elements']) and nxt['elements'][j][0] == 'use':
            other = nxt['elements'][j]
            el = el[:2] + (tween_matrix(el, other, t, k), tween_colour(el[3], other[3], t)) + el[4:]
        out.append(with_frame(doc, el, f - run_start(frames, i, j, el[1]), f - k['start']))
    return out


def run_start(frames, i, j, name):
    """début de l'instance : images clés précédentes, contiguës, avec le même symbole au même rang"""
    while i > 0:
        prev = frames[i - 1]
        if prev['start'] + prev['dur'] != frames[i]['start'] or j >= len(prev['elements']) or \
                prev['elements'][j][0] != 'use' or prev['elements'][j][1] != name:
            break
        i -= 1
    return frames[i]['start']


def with_frame(doc, el, since_placed, since_key):
    """élément ('use', nom, m, couleur, filtres, fusion, instance, image du symbole placé)"""
    el = tuple(el) + (None,) * (7 - len(el))
    inst = el[6] or {}
    sym = doc['symbols'].get(el[1])
    n = length(sym) if sym else 1
    kind = inst.get('kind', 'clip')
    if kind == 'bouton' or n == 1:
        frame = 0
    elif kind == 'graphique':
        first, loop = inst.get('first', 0), inst.get('loop', LOOP)
        frame = first if loop == SINGLE else min(first + since_key, n - 1) if loop == ONCE else \
            (first + since_key) % n
    else:
        frame = since_placed % n
    return el[:7] + (frame,)


def decompose(m):
    a, b, c, d, tx, ty = m
    return math.hypot(a, b), math.hypot(c, d), math.atan2(b, a), math.atan2(-c, d)


def turn(a0, a1, key):
    """angle d'arrivée selon le sens de rotation de l'image clé : 0 automatique (plus court chemin), 1 horaire,
    2 antihoraire, plus le nombre de tours (sens horaire = angle croissant, l'axe y descendant)"""
    while a1 - a0 > math.pi:
        a1 -= 2 * math.pi
    while a1 - a0 < -math.pi:
        a1 += 2 * math.pi
    direction, turns = key.get('rotate', 0), key.get('turns', 0)
    if direction == 1:
        return a1 + (2 * math.pi if a1 < a0 else 0) + 2 * math.pi * turns
    if direction == 2:
        return a1 - (2 * math.pi if a1 > a0 else 0) - 2 * math.pi * turns
    return a1


def tween_matrix(el, other, t, key):
    m0, m1 = el[2], other[2]
    sx0, sy0, rx0, ry0 = decompose(m0)
    sx1, sy1, rx1, ry1 = decompose(m1)
    if not key.get('scale', True):
        sx1, sy1 = sx0, sy0
    rx1, ry1 = turn(rx0, rx1, key), turn(ry0, ry1, key)
    lerp = lambda u, v: u + (v - u) * t  # noqa: E731
    sx, sy, rx, ry = lerp(sx0, sx1), lerp(sy0, sy1), lerp(rx0, rx1), lerp(ry0, ry1)
    a, b, c, d = sx * math.cos(rx), sx * math.sin(rx), -sy * math.sin(ry), sy * math.cos(ry)
    local = local_point(el)
    p0, p1 = apply(m0, local), apply(m1, local)
    px, py = lerp(p0[0], p1[0]), lerp(p0[1], p1[1])
    return (a, b, c, d, px - (a * local[0] + c * local[1]), py - (b * local[0] + d * local[1]))


def local_point(el):
    """point de transformation dans le repère du symbole (point d'alignement s'il n'est pas défini)"""
    inst = el[6] if len(el) > 6 and el[6] else {}
    if inst.get('tp_local'):
        return inst['tp_local']
    tp = inst.get('tp')
    if not tp:
        return (0.0, 0.0)
    a, b, c, d, tx, ty = el[2]
    det = a * d - b * c
    if abs(det) < 1e-12:
        return (0.0, 0.0)
    x, y = tp[0] - tx, tp[1] - ty
    return ((d * x - c * y) / det, (a * y - b * x) / det)


def apply(m, p):
    return (m[0] * p[0] + m[2] * p[1] + m[4], m[1] * p[0] + m[3] * p[1] + m[5])


def tween_colour(c0, c1, t):
    if not c0 and not c1:
        return c0
    c0, c1 = c0 or (1, 1, 1, 1, 0, 0, 0, 0), c1 or (1, 1, 1, 1, 0, 0, 0, 0)
    return tuple(u + (v - u) * t for u, v in zip(c0, c1))
