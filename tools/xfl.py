"""Lecture des .fla XFL (Flash CS5 et plus : archive ZIP de XML) en document pour fla_compose.

Flash écrit un répertoire central ZIP non standard : l'archive est lue par ses en-têtes locaux. Symboles :
LIBRARY/*.xml (DOMSymbolItem) ; scène : DOMDocument.xml ; bitmaps : DOMBitmapItem -> bin/*.dat (fla_bitmaps).
Bords (attribut `edges`) en twips : « ! x y » déplacement, « | x y » droite, « [ cx cy x y » courbe, « S n »
sélecteur ignoré ; nombres décimaux ou « #hex.hex » (24 bits signés, fraction en 256ᵉ). Première image de chaque calque.
"""
import base64, io, re, struct, zlib
import xml.etree.ElementTree as ET

import fla_bitmaps

NS = '{http://ns.adobe.com/xfl/2008/}'
TOKEN = re.compile(r'[!|/\[\]S]|#[0-9A-Fa-f]+(?:\.[0-9A-Fa-f]+)?|-?\d+(?:\.\d+)?')


def read_zip(path):
    b, pos, out = open(path, 'rb').read(), 0, {}
    while b[pos:pos + 4] == b'PK\x03\x04':
        _, flag, meth, _, _, _, csize, _, nlen, xlen = struct.unpack_from('<HHHHHIIIHH', b, pos + 4)
        name = b[pos + 30:pos + 30 + nlen].decode('utf-8', 'replace')
        at = pos + 30 + nlen + xlen
        data = b[at:at + csize]
        out[name] = zlib.decompress(data, -15) if meth == 8 else data
        pos = at + csize
    return out


def num(t):
    if t.startswith('#'):
        whole, _, frac = t[1:].partition('.')
        v = int(whole, 16)
        if v >= 0x800000:
            v -= 0x1000000
        return (v + (int(frac.ljust(2, '0')[:2], 16) / 256 if frac else 0)) / 20
    return float(t) / 20


def edges(text, f0, f1, ln, out):
    toks, i, cur = TOKEN.findall(text), 0, (0.0, 0.0)
    while i < len(toks):
        t = toks[i]
        if t == '!':
            cur = (num(toks[i + 1]), num(toks[i + 2]))
            i += 3
        elif t in '|/':
            nxt = (num(toks[i + 1]), num(toks[i + 2]))
            out.append((f0, f1, ln, cur[0], cur[1], None, None, nxt[0], nxt[1]))
            cur, i = nxt, i + 3
        elif t in '[]':
            cx, cy, x, y = (num(v) for v in toks[i + 1:i + 5])
            out.append((f0, f1, ln, cur[0], cur[1], cx, cy, x, y))
            cur, i = (x, y), i + 5
        else:
            i += 2 if t == 'S' else 1


def matrix(el, scale=1.0):
    m = el.find(NS + 'matrix/' + NS + 'Matrix') if el is not None else None
    if m is None:
        return (scale, 0, 0, scale, 0, 0)
    g = lambda k, d: float(m.get(k, d))
    return (g('a', 1) * scale, g('b', 0) * scale, g('c', 0) * scale, g('d', 1) * scale, g('tx', 0), g('ty', 0))


def rgba(el, colour='color', alpha='alpha'):
    c = el.get(colour, '#000000').lstrip('#')
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), round(float(el.get(alpha, 1)) * 255))


def style(el, doc):
    if el is None:
        return None
    for kind, tag in (('solid', 'SolidColor'), ('linear', 'LinearGradient'), ('radial', 'RadialGradient')):
        f = el.find(NS + tag)
        if f is not None:
            if kind == 'solid':
                return dict(kind='solid', rgba=rgba(f))
            stops = [(float(g.get('ratio', 0)), rgba(g)) for g in f.findall(NS + 'GradientEntry')]
            return dict(kind=kind, stops=stops, m=matrix(f))
    f = el.find(NS + 'BitmapFill')
    if f is not None and f.get('bitmapPath') in doc['bitmaps']:
        uri, w, h = doc['bitmaps'][f.get('bitmapPath')]
        return dict(kind='bitmap', href=uri, w=w, h=h, m=matrix(f, 1 / 20))
    return None


def shape(el, doc):
    fills = [style(f, doc) for f in el.findall(NS + 'fills/' + NS + 'FillStyle')]
    strokes = []
    for s in el.findall(NS + 'strokes/' + NS + 'StrokeStyle'):
        st = next(iter(s), None)
        strokes.append(dict(width=float(st.get('weight', 1)) if st is not None else 1,
                            fill=style(st.find(NS + 'fill'), doc) if st is not None else None))
    out = []
    for e in el.findall(NS + 'edges/' + NS + 'Edge'):
        if e.get('edges'):
            edges(e.get('edges'), int(e.get('fillStyle0', 0)), int(e.get('fillStyle1', 0)),
                  int(e.get('strokeStyle', 0)), out)
    return dict(fills=fills, strokes=strokes, edges=out)


def colour(el):
    c = el.find(NS + 'color/' + NS + 'Color')
    if c is None:
        return None
    g = lambda k, d: float(c.get(k, d))
    m, o = [g('redMultiplier', 1), g('greenMultiplier', 1), g('blueMultiplier', 1), g('alphaMultiplier', 1)], \
        [g('redOffset', 0), g('greenOffset', 0), g('blueOffset', 0), g('alphaOffset', 0)]
    if c.get('tintMultiplier'):
        t, tc = g('tintMultiplier', 0), rgba(c, 'tintColor')
        m[:3], o[:3] = [1 - t] * 3, [t * v for v in tc[:3]]
    if c.get('brightness'):
        b = g('brightness', 0)
        m[:3], o[:3] = ([1 + b] * 3, [0] * 3) if b < 0 else ([1 - b] * 3, [b * 255] * 3)
    return tuple(m + o)


def elements(parent, doc):
    out = []
    for el in parent:
        tag = el.tag[len(NS):]
        if tag == 'DOMShape':
            out.append(('shape', shape(el, doc), (1, 0, 0, 1, 0, 0)))
        elif tag == 'DOMSymbolInstance':
            out.append(('use', el.get('libraryItemName'), matrix(el), colour(el)))
        elif tag == 'DOMBitmapInstance':
            out.append(('bitmap', el.get('libraryItemName'), matrix(el)))
        elif tag == 'DOMGroup':
            out.append(('group', elements(el.find(NS + 'members') or [], doc), matrix(el)))
    return out


def timeline(tl, doc):
    xml_layers = tl.findall(NS + 'layers/' + NS + 'DOMLayer')
    roles = [l.get('layerType', 'normal') for l in xml_layers]
    out = []
    for i in reversed(range(len(xml_layers))):
        l, frame = xml_layers[i], None
        for f in l.findall(NS + 'frames/' + NS + 'DOMFrame'):
            if int(f.get('index', 0)) <= 0 < int(f.get('index', 0)) + int(f.get('duration', 1)):
                frame = f
        els = elements(frame.find(NS + 'elements') or [], doc) if frame is not None else []
        parent = l.get('parentLayerIndex')
        masked = parent is not None and roles[int(parent)] == 'mask'
        out.append(dict(elements=els, mask=roles[i] == 'mask', guide=roles[i] in ('guide', 'folder'),
                        masked_by=len(xml_layers) - 1 - int(parent) if masked else None))
    return out


def load(path):
    z = read_zip(path)
    doc = dict(symbols={}, bitmaps={}, scenes=[], raw_bitmaps={})
    root = ET.fromstring(z['DOMDocument.xml'])
    for b in root.iter(NS + 'DOMBitmapItem'):
        data = z.get('bin/' + b.get('bitmapDataHRef', ''))
        im = fla_bitmaps.decode(data) if data else None
        if im is not None:
            buf = io.BytesIO()
            im.save(buf, 'PNG')
            doc['raw_bitmaps'][b.get('name')] = im
            doc['bitmaps'][b.get('name')] = ('data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode(),
                                             im.width, im.height)
    for name, data in z.items():
        if name.startswith('LIBRARY/') and name.endswith('.xml'):
            item = ET.fromstring(data)
            tl = item.find(NS + 'timeline/' + NS + 'DOMTimeline')
            if item.tag == NS + 'DOMSymbolItem' and tl is not None:
                doc['symbols'][item.get('name')] = tl
    doc['symbols'] = {k: timeline(v, doc) for k, v in doc['symbols'].items()}
    for tl in root.findall(NS + 'timelines/' + NS + 'DOMTimeline'):
        doc['symbols']['[%s]' % tl.get('name')] = timeline(tl, doc)
        doc['scenes'].append('[%s]' % tl.get('name'))
    return doc
