"""Filtres des clips des .fla binaires (Flash 8 et après) : lecture, puis rendu en filtre SVG.

Enregistrement (relevé sur l'archive) : u8 type (numéros des filtres SWF : 0 ombre portée, 1 flou, 2 lueur,
6 réglage de couleur), en-tête (lueur et flou : 03 04 01 a ; ombre : 04 01 a ; couleur : 01 01 a ; a = filtre actif,
un filtre désactivé n'est pas exporté par Flash), 3 octets nuls, puis
- ombre, flou, lueur : couleur RGBA, f32 distance, f32 flou x, f32 flou y, f32 angle (radians), u32 intérieur,
  u32 masquage de l'objet (knockout), u32 qualité, u32 intensité (%), u32 (ombre : objet masqué) ;
- réglage de couleur : f32 luminosité, contraste, saturation, teinte (réglages de l'éditeur, -100..100, teinte en
  degrés), convertis en matrice de couleur par les formules de Flash (fl.motion.AdjustColor) : `adjust_matrix`,
  vérifiée contre les ColorMatrixFilter des SWF compilés depuis les mêmes .fla.

Rendu : le flou en boîte de Flash (qualité = nombre de passes) devient un flou gaussien de même variance ; lueur et
ombre suivent la définition de Flash (alpha flouté × intensité, teinté, sous l'objet ou en dedans).
"""
import math, struct

SIZE = {0: 47, 1: 48, 2: 48, 6: 23}
HEAD = {0: 4, 1: 5, 2: 5, 6: 4}  # octets avant les 3 nuls ; le dernier dit si le filtre est actif
KIND = {0: 'ombre', 1: 'flou', 2: 'lueur', 6: 'couleur'}
DELTA = (0, .01, .02, .04, .05, .06, .07, .08, .1, .11, .12, .14, .15, .16, .17, .18, .2, .21, .22, .24, .25, .27, .28,
         .3, .32, .34, .36, .38, .4, .42, .44, .46, .48, .5, .53, .56, .59, .62, .65, .68, .71, .74, .77, .8, .83, .86,
         .89, .92, .95, .98, 1, 1.06, 1.12, 1.18, 1.24, 1.3, 1.36, 1.42, 1.48, 1.54, 1.6, 1.66, 1.72, 1.78, 1.84, 1.9,
         1.96, 2, 2.12, 2.25, 2.37, 2.5, 2.62, 2.75, 2.87, 3, 3.2, 3.4, 3.6, 3.8, 4, 4.3, 4.7, 4.9, 5, 5.5, 6, 6.5,
         6.8, 7, 7.3, 7.5, 7.8, 8, 8.4, 8.7, 9, 9.4, 9.6, 9.8, 10)
LUM = (0.3086, 0.6094, 0.0820)


def parse(buf, q, n):
    """(filtres actifs, position suivante), ou (None, q) si un type est inconnu"""
    out = []
    for _ in range(n):
        t = buf[q] if q < len(buf) else None
        if t not in SIZE or q + SIZE[t] > len(buf):
            return None, q
        rec, h = buf[q:q + SIZE[t]], HEAD[t]
        body, q = rec[h + 3:], q + SIZE[t]
        if rec[h - 1] != 1:
            continue
        if t == 6:
            out.append(dict(kind='couleur', values=struct.unpack_from('<4f', body)))
            continue
        dist, bx, by, angle = struct.unpack_from('<4f', body, 4)
        inner, knock, quality, strength, hide = struct.unpack_from('<5I', body, 20)
        out.append(dict(kind=KIND[t], rgba=tuple(body[:4]), distance=dist, blur=(bx, by), angle=angle,
                        inner=bool(inner), knockout=bool(knock), quality=max(1, quality), strength=strength / 100,
                        hide=t == 0 and bool(hide)))
    return out, q


def mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(len(b))) for j in range(len(b[0]))] for i in range(len(a))]


def hue_matrix(deg):
    """rotation de teinte de Flash (lignes r', g', b' : 3 coefficients, alpha, décalage), vérifiée sur les matrices
    des SWF compilés"""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    lr, lg, lb = 0.213, 0.715, 0.072
    return [[lr + c * (1 - lr) - s * lr, lg - c * lg - s * lg, lb - c * lb + s * (1 - lb), 0, 0],
            [lr - c * lr + s * 0.143, lg + c * (1 - lg) + s * 0.140, lb - c * lb - s * 0.283, 0, 0],
            [lr - c * lr - s * (1 - lr), lg - c * lg + s * lg, lb + c * (1 - lb) + s * lb, 0, 0]]


def adjust_matrix(brightness, contrast, saturation, hue):
    """matrice 4 × 5 (décalages en 0..255) du réglage de couleur : luminosité, contraste, saturation, teinte"""
    ident = lambda: [[float(i == j) for j in range(5)] for i in range(5)]  # noqa: E731
    b, c, s = ident(), ident(), ident()
    for i in range(3):
        b[i][4] = brightness
    if contrast:
        n = DELTA[int(contrast)] * 127 + 127 if contrast > 0 else contrast / 100 * 127 + 127
        for i in range(3):
            c[i][i], c[i][4] = n / 127, 0.5 * (127 - n)
    if saturation:
        v = 1 + 3 * saturation / 100 if saturation > 0 else 1 + saturation / 100
        for i in range(3):
            for j in range(3):
                s[i][j] = (1 - v) * LUM[j] + (v if i == j else 0)
    h = ident()
    if hue:
        h[:3] = hue_matrix(hue)
    return mul(mul(mul(c, b), h), s)[:4]  # produit contraste · luminosité · teinte · saturation (vérifié)


def sigma(blur, quality):
    return blur * math.sqrt(quality / 12)


def svg(defs, uid, filters):
    """attribut filter (vide sans filtre) ; les primitives s'enchaînent dans l'ordre des filtres"""
    if not filters:
        return ''
    prims, src = [], 'SourceGraphic'
    for k, f in enumerate(filters):
        res = 'r%d' % k
        if f['kind'] == 'couleur':
            m = adjust_matrix(*f['values'])
            vals = ' '.join('%g' % (v / 255 if j == 4 else v) for row in m for j, v in enumerate(row))
            prims.append('<feColorMatrix in="%s" type="matrix" values="%s" result="%s"/>' % (src, vals, res))
        else:
            prims += effect(f, src, res, 'e%d' % k)
        src = res
    fid = uid('f')
    defs.append('<filter id="%s" x="-100%%" y="-100%%" width="300%%" height="300%%" '
                'color-interpolation-filters="sRGB">%s</filter>' % (fid, ''.join(prims)))
    return ' filter="url(#%s)"' % fid


def effect(f, src, res, p):
    sx, sy = (sigma(v, f['quality']) for v in f['blur'])
    if f['kind'] == 'flou':
        return ['<feGaussianBlur in="%s" stdDeviation="%g %g" result="%s"/>' % (src, sx, sy, res)]
    out = ['<feColorMatrix in="%s" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 0" result="%sa"/>'
           % (src, p), '<feGaussianBlur in="%sa" stdDeviation="%g %g" result="%sb"/>' % (p, sx, sy, p)]
    last = '%sb' % p
    if f['kind'] == 'ombre' and f['distance']:
        dx, dy = f['distance'] * math.cos(f['angle']), f['distance'] * math.sin(f['angle'])
        out.append('<feOffset in="%s" dx="%g" dy="%g" result="%so"/>' % (last, dx, dy, p))
        last = '%so' % p
    table = '1 0' if f['inner'] else '0 1'
    r, g, b, a = f['rgba']
    out += ['<feComponentTransfer in="%s" result="%sk"><feFuncA type="table" tableValues="%s"/></feComponentTransfer>'
            % (last, p, table),
            '<feComponentTransfer in="%sk" result="%ss"><feFuncA type="linear" slope="%g"/></feComponentTransfer>'
            % (p, p, f['strength']),
            '<feFlood flood-color="#%02x%02x%02x" flood-opacity="%g"/>' % (r, g, b, a / 255),
            '<feComposite in2="%ss" operator="in" result="%sg"/>' % (p, p)]
    if f['inner']:
        out.append('<feComposite in="%sg" in2="%sa" operator="in" result="%si"/>' % (p, p, p))
        out.append('<feComposite in="%si" in2="%s" operator="%s" result="%s"/>'
                   % (p, src, 'in' if f['knockout'] or f['hide'] else 'atop', res))
    elif f['knockout']:
        out.append('<feComposite in="%sg" in2="%sa" operator="out" result="%s"/>' % (p, p, res))
    elif f['hide']:
        out.append('<feMerge result="%s"><feMergeNode in="%sg"/></feMerge>' % (res, p))
    else:
        out.append('<feMerge result="%s"><feMergeNode in="%sg"/><feMergeNode in="%s"/></feMerge>' % (res, p, src))
    return out
