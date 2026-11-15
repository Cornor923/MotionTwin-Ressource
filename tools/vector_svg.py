"""Rendu SVG de formes vectorielles Flash (lues dans les .fla) et composition de symboles, sans rien ajouter.

Forme : {'fills': [style], 'strokes': [{'width': px, 'fill': style}], 'edges': [(f0, f1, trait, x0, y0, cx, cy, x1,
y1)]} en pixels, indices 1..n (0 = aucun), cx None pour un segment droit. Style : {'kind': 'solid', 'rgba'},
{'kind': 'linear'|'radial', 'stops': [(0..1, rgba)], 'm': matrice} (carré de dégradé de ±819,2 px) ou
{'kind': 'bitmap', 'href', 'w', 'h', 'm'}. Chaque remplissage est reconstitué en enchaînant ses bords (ceux de
gauche à l'envers), comme un lecteur SWF ; chaque trait en enchaînant les bords de son style.
"""
import math

GRAD = 819.2


class Svg:
    def __init__(self):
        self.defs, self.n, self.images = [], 0, {}
        self.box = [math.inf, math.inf, -math.inf, -math.inf]

    def image(self, uri, w, h):
        """bitmap déclaré une seule fois dans <defs>, réutilisé par <use>"""
        if uri not in self.images:
            self.images[uri] = self.uid('i')
            self.defs.append('<image id="%s" href="%s" width="%g" height="%g"/>' % (self.images[uri], uri, w, h))
        return self.images[uri]

    def uid(self, p):
        self.n += 1
        return '%s%d' % (p, self.n)

    def grow(self, m, x, y, pad=0.0):
        X, Y = m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]
        b = self.box
        b[0], b[1], b[2], b[3] = min(b[0], X - pad), min(b[1], Y - pad), max(b[2], X + pad), max(b[3], Y + pad)

    def extent(self, m, segs, pad):
        for x0, y0, cx, cy, x1, y1 in segs:
            self.grow(m, x0, y0, pad), self.grow(m, x1, y1, pad)
            if cx is not None:
                self.grow(m, cx, cy, pad)

    def paint(self, style):
        if not style:
            return 'none', 1.0
        k = style['kind']
        if k == 'solid':
            r, g, b, a = style['rgba']
            return '#%02x%02x%02x' % (r, g, b), a / 255
        gid = self.uid('g')
        if k == 'bitmap':
            self.defs.append('<pattern id="%s" patternUnits="userSpaceOnUse" width="%g" height="%g" '
                             'patternTransform="matrix(%s)"><use href="#%s"/></pattern>'
                             % (gid, style['w'], style['h'], ' '.join('%g' % v for v in style['m']),
                                self.image(style['href'], style['w'], style['h'])))
            return 'url(#%s)' % gid, 1.0
        stops = ''.join('<stop offset="%g" stop-color="#%02x%02x%02x" stop-opacity="%g"/>'
                        % (o, c[0], c[1], c[2], c[3] / 255) for o, c in style['stops'])
        m = ' '.join('%g' % v for v in style['m'])
        if k == 'radial':
            self.defs.append('<radialGradient id="%s" gradientUnits="userSpaceOnUse" cx="0" cy="0" r="%g" '
                             'gradientTransform="matrix(%s)">%s</radialGradient>' % (gid, GRAD, m, stops))
        else:
            self.defs.append('<linearGradient id="%s" gradientUnits="userSpaceOnUse" x1="%g" y1="0" x2="%g" y2="0" '
                             'gradientTransform="matrix(%s)">%s</linearGradient>' % (gid, -GRAD, GRAD, m, stops))
        return 'url(#%s)' % gid, 1.0

    def shape(self, shape, m):
        out = []
        for i, style in enumerate(shape['fills'], 1):
            segs = [e[3:] for e in shape['edges'] if e[1] == i]
            segs += [rev(e[3:]) for e in shape['edges'] if e[0] == i and e[1] != i]
            if segs:
                paint, op = self.paint(style)
                out.append('<path d="%s" fill="%s"%s fill-rule="evenodd"/>' % (
                    path(chain(segs, True)), paint, ' fill-opacity="%g"' % op if op < 1 else ''))
                self.extent(m, segs, 0)
        for i, st in enumerate(shape['strokes'], 1):
            segs = [e[3:] for e in shape['edges'] if e[2] == i]
            if segs:
                paint, op = self.paint(st['fill'])
                w = max(st['width'], 0.05)
                out.append('<path d="%s" fill="none" stroke="%s"%s stroke-width="%g" stroke-linecap="round" '
                           'stroke-linejoin="round"/>' % (path(chain(segs, False)), paint,
                                                          ' stroke-opacity="%g"' % op if op < 1 else '', w))
                self.extent(m, segs, w / 2)
        return out

    def document(self, body):
        x0, y0, x1, y1 = self.box
        if x0 > x1:
            return None
        w, h = max(x1 - x0, 0.5), max(y1 - y0, 0.5)
        return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="%.2f %.2f %.2f %.2f" width="%.2f" height="%.2f">'
                '<defs>%s</defs>%s</svg>' % (x0, y0, w, h, w, h, ''.join(self.defs), ''.join(body)))


def rev(s):
    x0, y0, cx, cy, x1, y1 = s
    return (x1, y1, cx, cy, x0, y0)


def chain(segs, close):
    """segments -> sous-chemins : chaque bord est rattaché à celui qui finit là où il commence"""
    starts = {}
    for i, s in enumerate(segs):
        starts.setdefault((round(s[0], 2), round(s[1], 2)), []).append(i)
    used, runs = set(), []
    for i in range(len(segs)):
        if i in used:
            continue
        run, cur = [], i
        while cur is not None and cur not in used:
            used.add(cur)
            run.append(segs[cur])
            end = (round(segs[cur][4], 2), round(segs[cur][5], 2))
            nxt = [j for j in starts.get(end, []) if j not in used]
            cur = nxt[0] if nxt else None
        runs.append((run, close))
    return runs


def path(runs):
    out = []
    for run, close in runs:
        out.append('M%.2f %.2f' % run[0][:2])
        for x0, y0, cx, cy, x1, y1 in run:
            out.append('Q%.2f %.2f %.2f %.2f' % (cx, cy, x1, y1) if cx is not None else 'L%.2f %.2f' % (x1, y1))
        if close:
            out.append('Z')
    return ''.join(out)


def mul(a, b):
    """composition de matrices (a, b, c, d, tx, ty) : a appliquée après b"""
    return (a[0] * b[0] + a[2] * b[1], a[1] * b[0] + a[3] * b[1], a[0] * b[2] + a[2] * b[3],
            a[1] * b[2] + a[3] * b[3], a[0] * b[4] + a[2] * b[5] + a[4], a[1] * b[4] + a[3] * b[5] + a[5])


ID = (1, 0, 0, 1, 0, 0)
