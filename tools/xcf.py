"""Lecture des fichiers GIMP `.xcf` (versions 0 à 2, pointeurs 32 bits, 8 bits par canal, compression RLE ou aucune),
écrite d'après la description du format de GIMP (devel-docs/xcf.txt), sans dépendance.

`read(path)` -> dict(w, h, base, layers=[dict(name, x, y, w, h, visible, opacity, mode, pixels RGBA numpy, mask)])
`compose(doc)` -> image RGBA de tous les calques visibles, du bas vers le haut, en mode normal (« over » 8 bits).
Les calques d'un autre mode de fusion ne sont pas composés (signalés dans `doc['skipped']`).
"""
import os, struct

import numpy as np
from PIL import Image

PROP_END, PROP_COLORMAP, PROP_OPACITY, PROP_MODE, PROP_VISIBLE = 0, 1, 6, 7, 8
PROP_APPLY_MASK, PROP_OFFSETS, PROP_COMPRESSION, PROP_GROUP_ITEM = 11, 15, 17, 29
TILE = 64


class Reader:
    def __init__(self, data):
        self.d = data

    def u32(self, pos):
        return struct.unpack_from('>I', self.d, pos)[0]

    def props(self, pos):
        out = {}
        while True:
            kind, size = struct.unpack_from('>II', self.d, pos)
            out[kind] = self.d[pos + 8:pos + 8 + size]
            pos += 8 + size
            if kind == PROP_END:
                return out, pos

    def string(self, pos):
        n = self.u32(pos)
        return self.d[pos + 4:pos + 4 + n].rstrip(b'\0').decode('utf-8', 'replace'), pos + 4 + n


def read(path):
    data = open(path, 'rb').read()
    if not data.startswith(b'gimp xcf '):
        raise ValueError('pas un fichier XCF')
    version = 0 if data[9:13] == b'file' else int(data[10:13])
    if version > 2:
        raise ValueError('XCF version %d (GIMP 2.10+) non gérée' % version)
    r = Reader(data)
    w, h, base = struct.unpack_from('>III', data, 14)
    props, pos = r.props(26)
    rle = props.get(PROP_COMPRESSION, b'\0')[0] == 1
    colormap = None
    if PROP_COLORMAP in props:
        n = struct.unpack_from('>I', props[PROP_COLORMAP], 0)[0]
        colormap = np.frombuffer(props[PROP_COLORMAP][4:4 + 3 * n], np.uint8).reshape(n, 3)
    pointers = []
    while r.u32(pos):
        pointers.append(r.u32(pos))
        pos += 4
    layers = [layer(r, p, rle, colormap) for p in pointers]
    return dict(w=w, h=h, base=base, version=version, layers=layers[::-1])  # du bas vers le haut


def layer(r, pos, rle, colormap):
    lw, lh, kind = struct.unpack_from('>III', r.d, pos)
    name, pos = r.string(pos + 12)
    props, pos = r.props(pos)
    hierarchy, mask_ptr = r.u32(pos), r.u32(pos + 4)
    x, y = struct.unpack_from('>ii', props[PROP_OFFSETS], 0) if PROP_OFFSETS in props else (0, 0)
    out = dict(name=name, x=x, y=y, w=lw, h=lh,
               visible=struct.unpack_from('>I', props.get(PROP_VISIBLE, b'\0\0\0\1'), 0)[0] == 1,
               opacity=struct.unpack_from('>I', props.get(PROP_OPACITY, b'\0\0\0\xff'), 0)[0],
               mode=struct.unpack_from('>I', props.get(PROP_MODE, b'\0\0\0\0'), 0)[0],
               group=PROP_GROUP_ITEM in props, mask=None)
    raw = pixels(r, hierarchy, lw, lh, rle) if hierarchy else np.zeros((lh, lw, 4), np.uint8)
    out['pixels'] = rgba(raw, kind, colormap)
    if mask_ptr and props.get(PROP_APPLY_MASK, b'\0\0\0\0')[3:] == b'\1':
        mw, mh = struct.unpack_from('>II', r.d, mask_ptr)
        _, mpos = r.string(mask_ptr + 8)
        _, mpos = r.props(mpos)
        out['mask'] = pixels(r, r.u32(mpos), mw, mh, rle)[..., 0]
    return out


def pixels(r, hierarchy, w, h, rle):
    bpp = r.u32(hierarchy + 8)
    level = r.u32(hierarchy + 12)
    pos = level + 8
    out = np.zeros((h, w, bpp), np.uint8)
    tiles_x = (w + TILE - 1) // TILE
    i = 0
    while r.u32(pos):
        start = r.u32(pos)
        ty, tx = divmod(i, tiles_x)
        tw, th = min(TILE, w - tx * TILE), min(TILE, h - ty * TILE)
        tile = rle_tile(r.d, start, tw * th, bpp) if rle else \
            np.frombuffer(r.d, np.uint8, tw * th * bpp, start).reshape(-1, bpp)
        out[ty * TILE:ty * TILE + th, tx * TILE:tx * TILE + tw] = tile.reshape(th, tw, bpp)
        pos += 4
        i += 1
    return out


def rle_tile(data, pos, n, bpp):
    """canaux l'un après l'autre, chacun en paquets : 0-126 = n+1 fois l'octet suivant, 127 = long (2 octets de
    compte) répété, 128 = long littéral, 129-255 = 256-n octets littéraux"""
    out = np.zeros((bpp, n), np.uint8)
    for c in range(bpp):
        k = 0
        while k < n:
            op = data[pos]
            pos += 1
            if op <= 126:
                out[c, k:k + op + 1] = data[pos]
                k, pos = k + op + 1, pos + 1
            elif op == 127:
                count = data[pos] * 256 + data[pos + 1]
                out[c, k:k + count] = data[pos + 2]
                k, pos = k + count, pos + 3
            elif op == 128:
                count = data[pos] * 256 + data[pos + 1]
                out[c, k:k + count] = np.frombuffer(data, np.uint8, count, pos + 2)
                k, pos = k + count, pos + 2 + count
            else:
                count = 256 - op
                out[c, k:k + count] = np.frombuffer(data, np.uint8, count, pos)
                k, pos = k + count, pos + count
    return out.T


def rgba(raw, kind, colormap):
    h, w = raw.shape[:2]
    out = np.zeros((h, w, 4), np.uint8)
    if kind in (0, 1):  # RGB, RGBA
        out[..., :3] = raw[..., :3]
        out[..., 3] = raw[..., 3] if kind == 1 else 255
    elif kind in (2, 3):  # niveaux de gris
        out[..., :3] = raw[..., :1]
        out[..., 3] = raw[..., 1] if kind == 3 else 255
    else:  # couleurs indexées
        out[..., :3] = colormap[raw[..., 0]]
        out[..., 3] = (raw[..., 1] >= 128) * 255 if kind == 5 else 255
    return out


def compose(doc):
    canvas = np.zeros((doc['h'], doc['w'], 4), np.float64)
    doc['skipped'] = []
    for lay in doc['layers']:
        if not lay['visible'] or lay['group']:
            continue
        if lay['mode'] != 0:
            doc['skipped'].append(lay['name'])
            continue
        src = lay['pixels'].astype(np.float64) / 255
        alpha = src[..., 3] * lay['opacity'] / 255
        if lay['mask'] is not None:
            alpha = alpha * lay['mask'] / 255
        x0, y0 = max(0, lay['x']), max(0, lay['y'])
        x1, y1 = min(doc['w'], lay['x'] + lay['w']), min(doc['h'], lay['y'] + lay['h'])
        if x0 >= x1 or y0 >= y1:
            continue
        s = (slice(y0 - lay['y'], y1 - lay['y']), slice(x0 - lay['x'], x1 - lay['x']))
        a, rgb = alpha[s][..., None], src[s][..., :3]
        dst = canvas[y0:y1, x0:x1]
        out_a = a + dst[..., 3:] * (1 - a)
        dst[..., :3] = np.where(out_a > 0, (rgb * a + dst[..., :3] * dst[..., 3:] * (1 - a)) / np.maximum(out_a, 1e-9), 0)
        dst[..., 3:] = out_a
    return (canvas * 255 + 0.5).clip(0, 255).astype(np.uint8)


def add(game, full, path, ctx):
    """fiche de l'image composée, puis une par calque dessiné (calques vides ou d'une seule couleur ignorés)"""
    try:
        doc = read(full)
    except (ValueError, struct.error, IndexError) as e:
        print('  illisible', path, e)
        return
    out = os.path.join(ctx.GEN, game.cfg['id'], 'xcf', os.path.splitext(path)[0])
    os.makedirs(out, exist_ok=True)
    stem, names = os.path.splitext(os.path.basename(path))[0], [lay['name'] for lay in doc['layers']]
    img = Image.fromarray(compose(doc))
    dst = os.path.join(out, 'composition.png')
    img.save(dst, optimize=True)
    base = dict(t='img', f=1, u=game.source_url(path), o=ctx.rel(full))
    game.add(dict(i=path, n=stem, s=ctx.rel(dst), p=path, w=img.width, h=img.height, fmt='XCF', z=os.path.getsize(full),
                  x=dict(layers=names[::-1], skipped=doc['skipped']), k=ctx.words(stem, *names), **base),
             ctx.pixel_hash(img))
    for k, lay in enumerate(doc['layers']):
        px = lay['pixels']
        if not px[..., 3].any() or (px == px[0, 0]).all():
            continue
        im, dst, ref = Image.fromarray(px), os.path.join(out, 'calque_%02d.png' % k), '%s#calque%d' % (path, k)
        im.save(dst, optimize=True)
        game.add(dict(i=ref, n='%s · %s' % (stem, lay['name']), s=ctx.rel(dst), p=ref, w=lay['w'], h=lay['h'], fmt='PNG',
                      z=os.path.getsize(dst), k=ctx.words(lay['name'], stem), x=dict(
                          layer=lay['name'], offset=[lay['x'], lay['y']], visible=lay['visible'],
                          opacity=lay['opacity']), **base), ctx.pixel_hash(im))
