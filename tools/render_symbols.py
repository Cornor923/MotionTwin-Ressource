"""Rend les symboles exportés d'un SWF (clips) avec swfrender (kadokadeo flash-port), à partir des exports FFDec.

usage : python render_symbols.py <dossier des exports FFDec (rebuild.py)> <dossier de sortie> [id,id,...]
Écrit <sortie>/<id>.png (première image), <id>_sheet.png (toutes les images en grille) et symbols.json.
Toutes les images d'un clip sont montrées (scripts du clip lui-même ignorés), ses clips imbriqués jouent leur timeline.
"""
import json, math, os, struct, sys, time, zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flash'))
import swfrender as R
from PIL import Image

import swf_symbols

SCALE = 2          # pixels par pixel Flash
MAX_FRAMES = 120
MAX_NESTED = 60
SHEET_MAX = 8192


def frame_rate(path):
    raw = open(path, 'rb').read()
    data = zlib.decompress(raw[8:]) if raw[:3] == b'CWS' else raw[8:]
    nbits = data[0] >> 3
    pos = (5 + 4 * nbits + 7) // 8
    return struct.unpack_from('<H', data, pos)[0] / 256.0


def nested_length(swf, sid, seen=()):
    best = 1
    for ops in swf.sprites[sid].frames:
        for kind, v in ops:
            c = v.get('char') if kind == 'place' else None
            if c in swf.sprites and c not in seen:
                best = max(best, swf.sprites[c].nframes, nested_length(swf, c, seen + (sid,)))
    return best


def states(swf, sid):
    sd = swf.sprites[sid]
    total = sd.nframes if sd.nframes > 1 else nested_length(swf, sid)
    total = min(total, MAX_FRAMES if sd.nframes > 1 else MAX_NESTED)
    inst = R.Instance(swf, sid, ctrl={sid: 1})
    snaps = []
    for f in range(1, total + 1):
        if sd.nframes > 1:
            inst._goto(f)
        snaps.append(R._snap(inst))
        inst.tick()
    return snaps, sd.nframes


def sheet(frames):
    w = max(f.width for f in frames)
    h = max(f.height for f in frames)
    cols = math.ceil(math.sqrt(len(frames) * h / max(w, 1)))
    cols = max(1, min(len(frames), cols, SHEET_MAX // max(w, 1)))
    rows = math.ceil(len(frames) / cols)
    while rows * h > SHEET_MAX and len(frames) > 1:
        frames = frames[:-1]
        rows = math.ceil(len(frames) / cols)
    im = Image.new('RGBA', (cols * w, rows * h))
    for i, f in enumerate(frames):
        im.paste(f, ((i % cols) * w, (i // cols) * h))
    return im, w, h, cols, len(frames)


def main(work, out, only=None):
    os.makedirs(out, exist_ok=True)
    swf = R.SWF(os.path.join(work, 'src.swf'), os.path.join(work, 'shp4'), Z=4)
    swf_symbols.add_symbol_classes(swf, os.path.join(work, 'src.swf'))  # symboles AS3
    swf.flash_replace = True
    swf.blur_filters = True
    swf.inner_filters = True
    swf.svg_dir = os.path.join(work, 'svg')
    shape_image = swf.shape_image

    def tolerant_shape_image(cid):
        try:
            return shape_image(cid)
        except FileNotFoundError:  # forme de largeur nulle : FFDec n'écrit pas de PNG
            return Image.new('RGBA', (1, 1))
    swf.shape_image = tolerant_shape_image
    fps = frame_rate(os.path.join(work, 'src.swf'))
    rd = R.Renderer(swf, out_scale=SCALE)
    result, errors = [], []
    previous = None
    if only and os.path.exists(os.path.join(out, 'symbols.json')):
        previous = json.load(open(os.path.join(out, 'symbols.json')))
    for cid, name in sorted(swf.exports.items()):
        if only and cid not in only:
            continue
        t0 = time.time()
        entry = dict(id=cid, name=name)
        try:
            if cid in swf.sprites:
                snaps, timeline_frames = states(swf, cid)
                imgs, reg = rd.render_frames(snaps)
                uniq = [imgs[0]]
                if any(im.tobytes() != imgs[0].tobytes() for im in imgs[1:]):
                    uniq = imgs
                entry.update(kind='clip', timeline=timeline_frames, regX=round(reg[0], 2), regY=round(reg[1], 2))
            elif cid in swf.shapes:
                entry.update(kind='shape')
                result.append(entry)
                continue
            else:
                continue
            uniq[0].save(os.path.join(out, '%d.png' % cid), optimize=True)
            entry.update(w=uniq[0].width, h=uniq[0].height, frames=1)
            if len(uniq) > 1:
                im, w, h, cols, n = sheet(uniq)
                im.save(os.path.join(out, '%d_sheet.png' % cid), optimize=True)
                entry.update(w=w, h=h, frames=n, cols=cols, fps=fps)
            result.append(entry)
            print('%5d %-28s %3d img %5.1fs' % (cid, name, entry['frames'], time.time() - t0), flush=True)
        except Exception as e:  # un symbole illisible ne bloque pas les autres
            errors.append(dict(id=cid, name=name, error='%s: %s' % (type(e).__name__, e)))
            print('%5d %-28s ERREUR %s' % (cid, name, errors[-1]['error']), flush=True)
    if previous:  # rendu partiel : on remplace seulement les symboles demandés
        done = {e['id'] for e in result} | {e['id'] for e in errors}
        result = sorted([e for e in previous['symbols'] if e['id'] not in done] + result, key=lambda e: e['id'])
        errors = [e for e in previous['errors'] if e['id'] not in done] + errors
    json.dump(dict(fps=fps, symbols=result, errors=errors), open(os.path.join(out, 'symbols.json'), 'w'), indent=1)
    print('%d symboles, %d erreurs' % (len(result), len(errors)))


if __name__ == '__main__':
    ids = {int(x) for x in sys.argv[3].split(',')} if len(sys.argv) > 3 else None
    main(sys.argv[1], sys.argv[2], ids)
