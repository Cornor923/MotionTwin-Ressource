"""Lecteur minimal de fichiers GraphicsGale « Gale106 » (.gal) : images d'une animation, calques composés.

En-tête : u32 largeur @15, hauteur @19, bits par pixel @23, nombre d'images @27.
Image : [u32 n][nom][u32 couleur transparente][u32 délai ms]...
Calque : [u8 visible][u32 couleur transparente][u8 opacité][u32][u32 n][nom][u32 taille][zlib BGR, lignes alignées sur 4 octets].
"""
import os, struct, zlib
import numpy as np
from PIL import Image

import compact

NONE = 0xFFFFFFFF


def _name_at(d, i):
    if i + 4 > len(d):
        return None
    n = struct.unpack_from('<I', d, i)[0]
    if not 1 <= n <= 255 or i + 4 + n > len(d):
        return None
    s = d[i + 4:i + 4 + n]
    if not all(32 <= c < 127 for c in s):
        return None
    return s.decode('ascii')


def read(path):
    d = open(path, 'rb').read()
    if not d.startswith(b'Gale106'):
        raise ValueError('format GraphicsGale non géré : %r' % d[:8])
    w, h, bpp, nframes = (struct.unpack_from('<I', d, o)[0] for o in (15, 19, 23, 27))
    if bpp != 24:
        raise ValueError('%d bits par pixel non géré' % bpp)
    stride = (w * 3 + 3) & ~3
    frames, i = [], 31
    while i < len(d) - 8:
        name = _name_at(d, i)
        if name is None:
            i += 1
            continue
        after = i + 4 + len(name)
        size = struct.unpack_from('<I', d, after)[0] if after + 4 <= len(d) else 0
        if d[after + 4:after + 5] == b'\x78' and frames:
            raw = zlib.decompressobj().decompress(d[after + 4:after + 4 + size])
            if len(raw) >= stride * h:
                px = np.frombuffer(raw[:stride * h], np.uint8).reshape(h, stride)[:, :w * 3].reshape(h, w, 3)[:, :, ::-1]
                frames[-1]['layers'].append(dict(name=name, visible=d[i - 10] != 0,
                                                 trans=struct.unpack_from('<I', d, i - 9)[0],
                                                 opacity=d[i - 5], px=px))
                i = after + 4 + size
                continue
        if after + 8 <= len(d):
            trans, delay = struct.unpack_from('<II', d, after)
            if delay < 100000:
                if frames and not frames[-1]['layers']:
                    frames.pop()  # faux positif dans l'en-tête
                frames.append(dict(name=name, trans=trans, delay=delay, layers=[]))
                i = after + 8
                continue
        i += 1
    frames = [f for f in frames if f['layers']]
    if len(frames) != nframes:
        raise ValueError('%d images lues sur %d' % (len(frames), nframes))
    return dict(w=w, h=h, frames=frames)


def compose(g, frame):
    out = np.zeros((g['h'], g['w'], 4), np.float32)
    for layer in reversed(frame['layers']):  # le premier calque est au-dessus
        if not layer['visible']:
            continue
        px = layer['px']
        trans = layer['trans'] if layer['trans'] != NONE else frame['trans']
        if trans == NONE and (px == px[0, 0]).all():
            continue  # calque de fond uni
        alpha = np.full(px.shape[:2], layer['opacity'] / 255.0, np.float32)
        if trans != NONE:
            rgb = np.array([(trans >> s) & 255 for s in (0, 8, 16)], np.uint8)
            alpha[(px == rgb).all(2)] = 0
        a = alpha[..., None]
        out[..., :3] = px / 255.0 * a + out[..., :3] * (1 - a)
        out[..., 3:] = a + out[..., 3:] * (1 - a)
    rgb = np.where(out[..., 3:] > 0, out[..., :3] / np.maximum(out[..., 3:], 1e-6), 0)
    return Image.fromarray((np.dstack([rgb, out[..., 3:]]) * 255 + 0.5).astype(np.uint8), 'RGBA')


def frames(path):
    g = read(path)
    return [compose(g, f) for f in g['frames']], [f['delay'] for f in g['frames']]


def save_sheet(frames, path):
    w, h = frames[0].size
    cols = max(1, min(len(frames), round((len(frames) * h / w) ** 0.5) or 1))
    rows = -(-len(frames) // cols)
    sheet = Image.new('RGBA', (cols * w, rows * h))
    for i, f in enumerate(frames):
        sheet.paste(f, ((i % cols) * w, (i // cols) * h))
    sheet.save(path, optimize=True)
    return cols


def add(game, full, path, ctx):
    """fiche d'un .gal : première image, planche d'animation et délais s'il en a plusieurs"""
    images, delays = frames(full)
    out = os.path.join(ctx.GEN, game.cfg['id'], 'gal', os.path.splitext(path)[0])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    images[0].save(out + '.png', optimize=True)
    item = dict(i=path, t='anim', n=os.path.splitext(os.path.basename(path))[0], s=ctx.rel(out + '.png'), p=path,
                w=images[0].width, h=images[0].height, f=len(images), z=os.path.getsize(full), fmt='GAL',
                u=game.source_url(path), px=1, o=ctx.rel(full))
    if len(images) > 1:
        item['cols'] = save_sheet(images, out + '_sheet.png')
        sheet = compact.sheet(out + '_sheet.png', out + '_sheet', ctx.WORK)
        if sheet != out + '_sheet.png':
            os.remove(out + '_sheet.png')
        item['sh'] = ctx.rel(sheet)
        item['d'] = delays
    game.add(item, ctx.pixel_hash(images[0]) if len(images) == 1 else None)
