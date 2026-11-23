"""Composition d'un symbole de .fla en SVG : calques du bas vers le haut, image par image (fla_timeline.py).

Document : {'symbols': {nom: [calque]}, 'bitmaps': {nom: (data URI, l, h)}}. Calque : {'elements': [...],
'mask': bool, 'masked_by': indice du calque masque ou None, 'guide': bool}. Élément : ('shape', forme, m),
('use', nom du symbole, m, couleur[, filtres, mode de fusion]), ('bitmap', nom, m), ('group', [éléments], m) ;
m = (a, b, c, d, tx, ty) en pixels, couleur = (multiplicateurs r, g, b, a, décalages r, g, b, a) ou None, filtres :
voir fla_filters.py. Les calques guides ne sont pas dessinés ; un calque masque devient un <mask> (alpha) appliqué
aux calques qu'il masque.

`render` : une image (la première) ; `animate` : planche SVG de toutes les images d'un symbole animé, une case par
image (cadre commun à toutes), le contenu commun (symboles placés à une image donnée, formes) défini une fois dans
<defs> et réutilisé par <use>.
"""
import math

import fla_filters
import fla_timeline as T
import vector_svg as V

DEPTH = 24
# modes de fusion Flash (numéros SWF) rendus par CSS ; soustraction, inversion, alpha et effacement n'y ont pas
# d'équivalent et restent en mode normal
BLEND = {3: 'multiply', 4: 'screen', 5: 'lighten', 6: 'darken', 7: 'difference', 8: 'plus-lighter', 13: 'overlay',
         14: 'hard-light'}


LIMIT = 400  # images d'une planche au plus


def render(doc, name, box=None):
    """SVG de la première image d'un symbole (cadre `box` = x, y, l, h imposé), ou None s'il ne dessine rien"""
    svg = V.Svg()
    body = layers(svg, doc, T.at(doc, name, 0), V.ID, 0, {name})
    if box:  # planche : la première image peut être vide
        svg.box = [box[0], box[1], box[0] + box[2], box[1] + box[3]]
    return svg.document(body)


def animate(doc, name):
    """planche d'un symbole de plusieurs images : dict(sheet, frames, w, h, cols, box), ou None"""
    n = min(T.length(doc['symbols'][name]), LIMIT)
    if n < 2:
        return None
    svg, bodies = V.Svg(), []
    svg.cache, total = {}, list(svg.box)
    for f in range(n):
        svg.box = [math.inf, math.inf, -math.inf, -math.inf]
        bodies.append(''.join(layers(svg, doc, T.at(doc, name, f), V.ID, 0, {name})))
        b = svg.box
        total = [min(total[0], b[0]), min(total[1], b[1]), max(total[2], b[2]), max(total[3], b[3])]
    if total[0] > total[2]:
        return None
    x0, y0 = total[0], total[1]
    w, h = max(total[2] - x0, 0.5), max(total[3] - y0, 0.5)
    cols = math.ceil(math.sqrt(n))
    rows, cells, seen = math.ceil(n / cols), [], {}
    for f, body in enumerate(bodies):
        if body not in seen:
            seen[body] = svg.uid('f')
            svg.defs.append('<g id="%s">%s</g>' % (seen[body], body))
        cells.append('<svg x="%g" y="%g" width="%.2f" height="%.2f" viewBox="%.2f %.2f %.2f %.2f"><use href="#%s"/>'
                     '</svg>' % ((f % cols) * w, (f // cols) * h, w, h, x0, y0, w, h, seen[body]))
    sheet = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %.2f %.2f" width="%.2f" height="%.2f"><defs>%s'
             '</defs>%s</svg>' % (cols * w, rows * h, cols * w, rows * h, ''.join(svg.defs), ''.join(cells)))
    return dict(sheet=sheet, frames=n, w=w, h=h, cols=cols, box=(x0, y0, w, h))


def shared(svg, doc, key, draw):
    """contenu défini une fois dans <defs> (planches) : (id ou None, cadre dans son propre repère)"""
    if key not in svg.cache:
        box, svg.box = svg.box, [math.inf, math.inf, -math.inf, -math.inf]
        inner = draw()
        local, svg.box = svg.box, box
        gid = svg.uid('s') if inner else None
        if gid:
            svg.defs.append('<g id="%s">%s</g>' % (gid, ''.join(inner)))
        svg.cache[key] = (gid, local)
    return svg.cache[key]


def reuse(svg, key_draw, mm, grow):
    gid, b = key_draw
    if not gid:
        return []
    if grow and b[0] <= b[2]:
        for x, y in ((b[0], b[1]), (b[2], b[1]), (b[0], b[3]), (b[2], b[3])):
            svg.grow(mm, x, y)
    return ['<use href="#%s"/>' % gid]


def layers(svg, doc, sym, m, depth, stack):
    out, masks = [], {}
    for i, layer in enumerate(sym):
        if layer.get('mask'):
            mid = svg.uid('m')
            inner = elements(svg, doc, layer['elements'], m, depth, stack, grow=False)
            svg.defs.append('<mask id="%s" mask-type="alpha" maskUnits="userSpaceOnUse" x="-1e5" y="-1e5" '
                            'width="2e5" height="2e5">%s</mask>' % (mid, ''.join(inner)))
            masks[i] = mid
    for i, layer in enumerate(sym):
        if layer.get('guide') or layer.get('mask'):
            continue
        inner = elements(svg, doc, layer['elements'], m, depth, stack)
        mid = masks.get(layer.get('masked_by'))
        if inner and mid:
            inner = ['<g mask="url(#%s)">' % mid] + inner + ['</g>']
        out += inner
    return out


def elements(svg, doc, els, m, depth, stack, grow=True):
    out = []
    for el in els:
        kind, local, attrs = el[0], el[2], ''
        mm = V.mul(m, local)
        sharing = getattr(svg, 'cache', None) is not None
        if kind == 'shape' and sharing:
            inner = reuse(svg, shared(svg, doc, ('forme', id(el[1])), lambda: svg.shape(el[1], V.ID)), mm, grow)
        elif kind == 'shape':
            box = list(svg.box)
            inner = svg.shape(el[1], mm)
            if not grow:
                svg.box = box
        elif kind == 'group':
            inner = elements(svg, doc, el[1], mm, depth, stack, grow)
        elif kind == 'use':
            if el[1] not in doc['symbols'] or el[1] in stack or depth >= DEPTH:
                continue
            frame = el[7] if len(el) > 7 and el[7] else 0
            draw = lambda base, el=el, frame=frame: layers(  # noqa: E731
                svg, doc, T.at(doc, el[1], frame), base, depth + 1, stack | {el[1]})
            inner = reuse(svg, shared(svg, doc, ('symbole', el[1], frame), lambda: draw(V.ID)), mm, grow)                 if sharing else draw(mm)
            attrs = colour(svg, el[3])
            fx = fla_filters.svg(svg.defs, svg.uid, el[4]) if len(el) > 4 else ''
            blend = BLEND.get(el[5]) if len(el) > 5 else None
            attrs += ' style="mix-blend-mode:%s"' % blend if blend else ''
            if inner and fx:  # filtres dans le repère du parent, transformation de couleur après eux (Flash)
                out += ['<g%s><g%s><g transform="matrix(%s)">' % (attrs, fx, ' '.join('%g' % v for v in local))]
                out += inner + ['</g></g></g>']
                continue
        else:
            bmp = doc['bitmaps'].get(el[1])
            if bmp is None:
                continue
            uri, w, h = bmp
            inner = ['<use href="#%s"/>' % svg.image(uri, w, h)]
            if grow:
                for x, y in ((0, 0), (w, 0), (0, h), (w, h)):
                    svg.grow(mm, x, y)
        if inner:
            out += ['<g transform="matrix(%s)"%s>' % (' '.join('%g' % v for v in local), attrs)] + inner + ['</g>']
    return out


def colour(svg, c):
    if not c or c == (1, 1, 1, 1, 0, 0, 0, 0):
        return ''
    rm, gm, bm, am, ro, go, bo, ao = c
    if (rm, gm, bm, ro, go, bo, ao) == (1, 1, 1, 0, 0, 0, 0):
        return ' opacity="%g"' % max(0, min(1, am))
    fid = svg.uid('c')
    svg.defs.append('<filter id="%s" color-interpolation-filters="sRGB"><feColorMatrix type="matrix" values="'
                    '%g 0 0 0 %g 0 %g 0 0 %g 0 0 %g 0 %g 0 0 0 %g %g"/></filter>'
                    % (fid, rm, ro / 255, gm, go / 255, bm, bo / 255, am, ao / 255))
    return ' filter="url(#%s)"' % fid
