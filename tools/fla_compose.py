"""Composition d'un symbole de .fla en SVG : calques du bas vers le haut, première image de chaque calque.

Document : {'symbols': {nom: [calque]}, 'bitmaps': {nom: (data URI, l, h)}}. Calque : {'elements': [...],
'mask': bool, 'masked_by': indice du calque masque ou None, 'guide': bool}. Élément : ('shape', forme, m),
('use', nom du symbole, m, couleur[, filtres, mode de fusion]), ('bitmap', nom, m), ('group', [éléments], m) ;
m = (a, b, c, d, tx, ty) en pixels, couleur = (multiplicateurs r, g, b, a, décalages r, g, b, a) ou None, filtres :
voir fla_filters.py. Les calques guides ne sont pas dessinés ; un calque masque devient un <mask> (alpha) appliqué
aux calques qu'il masque.
"""
import fla_filters
import vector_svg as V

DEPTH = 24
# modes de fusion Flash (numéros SWF) rendus par CSS ; soustraction, inversion, alpha et effacement n'y ont pas
# d'équivalent et restent en mode normal
BLEND = {3: 'multiply', 4: 'screen', 5: 'lighten', 6: 'darken', 7: 'difference', 8: 'plus-lighter', 13: 'overlay',
         14: 'hard-light'}


def render(doc, name):
    """SVG d'un symbole, ou None s'il ne dessine rien"""
    svg = V.Svg()
    body = layers(svg, doc, doc['symbols'][name], V.ID, 0, {name})
    return svg.document(body)


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
        if kind == 'shape':
            box = list(svg.box)
            inner = svg.shape(el[1], mm)
            if not grow:
                svg.box = box
        elif kind == 'group':
            inner = elements(svg, doc, el[1], mm, depth, stack, grow)
        elif kind == 'use':
            sym = doc['symbols'].get(el[1])
            if sym is None or el[1] in stack or depth >= DEPTH:
                continue
            inner = layers(svg, doc, sym, mm, depth + 1, stack | {el[1]})
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
