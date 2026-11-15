"""Lecture des .fla binaires (Flash 5 à CS4, conteneur OLE) en document pour fla_compose, avec fla-decoder.

fla-decoder (tools/fla_decoder, MIT) décode les flux de symboles (« Symbol N » ou « S N horodatage ») en arbre
CPicPage -> CPicLayer -> CPicFrame -> CPicShape. Ce module en tire la première image de chaque calque et convertit
les formes : bords en ultra-twips (2560 par pixel), indices de style dans l'ordre trait, remplissage, remplissage
(vérifié sur toutes les formes : c'est le seul ordre compatible avec la taille des tables), traits en twips.
Les instances de symboles (CPicSprite) ne sont pas reliées à leur symbole par fla-decoder : un symbole qui ne fait
qu'assembler d'autres symboles ne dessine rien. Noms : le flux « Contents » cite chaque flux suivi de son nom.
"""
import os, wave
import olefile
from fla_decoder import decoder
from fla_decoder.audio import parse_sound_records, RATE_TABLE

import fla_bitmaps

UNIT = 2560.0


def rgba(u):
    return (u & 255, (u >> 8) & 255, (u >> 16) & 255, (u >> 24) & 255)


def mat(m):
    return (m.get('a', 1), m.get('b', 0), m.get('c', 0), m.get('d', 1), m.get('tx', 0), m.get('ty', 0)) if m else \
        (1, 0, 0, 1, 0, 0)


def style(f):
    if not f:
        return None
    if f.get('kind') == 'solid':
        return dict(kind='solid', rgba=rgba(f['color_u32']))
    if f.get('kind') == 'gradient':
        radial = (f['subtype_flags'] & 0x0F) in (2, 3)
        return dict(kind='radial' if radial else 'linear', m=mat(f['matrix']),
                    stops=[(s['position'] / 255, rgba(s['color_u32'])) for s in f['stops']])
    return None


def shape(sd):
    fills = [style(f) for f in sd.get('fills', [])]
    strokes = [dict(width=l.get('flags16', 20) / 20, fill=style(l.get('fill_style')) or
                    dict(kind='solid', rgba=rgba(l['stroke_color_u32']))) for l in sd.get('lines', [])]
    edges = []
    for e in sd.get('byte_edges', []):
        (x0, y0), (cx, cy), (x1, y1) = e['from'], e['ctrl'], e['to']
        ctrl = (None, None) if e['kind'] == 'line' else (cx / UNIT, cy / UNIT)
        edges.append((e['fill1'], e['line_style'], e['fill0'], x0 / UNIT, y0 / UNIT, ctrl[0], ctrl[1],
                      x1 / UNIT, y1 / UNIT))
    return dict(fills=fills, strokes=strokes, edges=edges)


def children(node, cls):
    return [c for c in node.get('children', []) if isinstance(c, dict) and c.get('class') == cls]


def frame_elements(fr):
    out = []
    if fr.get('shape', {}).get('byte_edges'):
        out.append(('shape', shape(fr['shape']), mat(fr.get('matrix'))))
    for c in fr.get('children', []):
        if isinstance(c, dict) and c.get('class') == 'CPicShape' and c.get('shape', {}).get('byte_edges'):
            out.append(('shape', shape(c['shape']), mat(c.get('matrix'))))
    return out


def symbol(result):
    page = result.get('body') or {}
    layers = []
    for layer in reversed(children(page, 'CPicLayer')):
        frames = children(layer, 'CPicFrame')
        if frames:
            layers.append(dict(elements=frame_elements(frames[0]), guide=layer.get('layer_field_type') == 1))
    if not any(l['elements'] for l in layers):
        rec = [('shape', shape(r['shape']), mat(r.get('matrix'))) for r in result.get('recovered_shapes', [])
               if r.get('shape', {}).get('byte_edges')]
        layers = [dict(elements=rec)] if rec else layers
    return layers


def stream_names(contents, streams):
    names = {}
    for s in streams:
        key = s.encode('utf-16le')
        i = contents.find(key)
        j = contents.find(b'\xff\xfe\xff', i + len(key), i + len(key) + 40) if i >= 0 else -1
        if j >= 0:
            n = contents[j + 3]
            names[s] = contents[j + 4:j + 4 + 2 * n].decode('utf-16le', 'replace')
    return names


def load(path, sound_dir):
    ole = olefile.OleFileIO(path)
    streams = ['/'.join(s) for s in ole.listdir(streams=True)]
    contents = ole.openstream('Contents').read() if 'Contents' in streams else b''
    names = stream_names(contents, streams)
    doc = dict(symbols={}, bitmaps={}, scenes=[], raw_bitmaps={}, sounds=[], errors=0)
    for s in streams:
        kind = s.split()[0]
        if kind in ('S', 'Symbol', 'P', 'Page'):
            try:
                layers = symbol(decoder.decode_symbol_stream(ole.openstream(s).read()))
            except Exception:
                doc['errors'] += 1
                continue
            label = names.get(s) or s
            key = '[%s]' % label if kind in ('P', 'Page') else label
            while key in doc['symbols']:
                key += ' '
            doc['symbols'][key] = layers
        elif kind in ('M', 'Media'):
            im = fla_bitmaps.decode(ole.openstream(s).read())
            if im is not None:
                doc['raw_bitmaps'][names.get(s) or s] = im
    by_number = {s.split()[1]: s for s in streams if s.split()[0] in ('M', 'Media') and len(s.split()) > 1}
    for rec in parse_sound_records(contents) if contents else []:
        label = (rec.get('media_label') or '').split()
        s = by_number.get(label[1]) if len(label) > 1 else None
        if s:
            doc['sounds'].append(sound(ole.openstream(s).read(), rec, sound_dir))
    ole.close()
    return doc


def sound(data, rec, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    base = ''.join(c if c.isalnum() or c in '-_.' else '_' for c in (rec['linkage'] or rec['filename'] or 'son'))
    if rec['filename'].lower().endswith('.mp3') or data[:2] in (b'\xff\xfb', b'\xff\xfa', b'\xff\xf3'):
        out = os.path.join(out_dir, os.path.splitext(base)[0] + '.mp3')
        open(out, 'wb').write(data)
    else:
        rate, ch = RATE_TABLE.get(rec['rate_tag'], 44100), 1
        for tag, count in rec['candidates']:
            if count > 0 and abs(len(data) / (2 * count) - 2) < 0.01:
                rate, ch = RATE_TABLE.get(tag, rate), 2
                break
            if count > 0 and abs(len(data) / (2 * count) - 1) < 0.01:
                rate = RATE_TABLE.get(tag, rate)
                break
        out = os.path.join(out_dir, os.path.splitext(base)[0] + '.wav')
        with wave.open(out, 'wb') as w:
            w.setnchannels(ch), w.setsampwidth(2), w.setframerate(rate), w.writeframesraw(data)
    return dict(path=out, name=rec['filename'] or base)
