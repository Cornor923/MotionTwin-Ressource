"""Ressources tirées d'un SWF : clips rendus (render_symbols.py), formes SVG, bitmaps et sons (rebuild.py).

Une entrée `variant_of` (autre version d'un SWF déjà traité, mêmes formes) n'apporte que ses clips au rendu
différent ; les autres sont notés comme doublons de la version principale.
"""
import hashlib, json, os, re, shutil
from PIL import Image

import swfrender as R
import compact, fla_items, swf_symbols


def add_swf(game, entry, ctx):
    path = entry['file']
    stem, ext = os.path.splitext(path)
    folder = (stem if ext.lower() == '.swf' else stem + '_' + ext[1:]).replace('/', '_')  # all.swf ≠ all.mtswf
    work = os.path.join(ctx.WORK, entry['work'])
    render = os.path.join(ctx.WORK, 'render', entry['work'])
    out = os.path.join(ctx.GEN, game.cfg['id'], 'swf', folder)
    shutil.rmtree(out, ignore_errors=True)
    swf = R.SWF(os.path.join(work, 'src.swf'), os.path.join(work, 'shp4'))
    swf_symbols.add_symbol_classes(swf, os.path.join(work, 'src.swf'))
    coll = ctx.collection(game.cfg, path)
    primary = game.clips.get(entry.get('variant_of'), {})
    mine = game.clips.setdefault(path, {})
    meta_path = os.path.join(render, 'symbols.json')
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else dict(symbols=[], errors=[])
    if not os.path.exists(meta_path):
        print('  clips non rendus (render_symbols.py) :', path)
    os.makedirs(os.path.join(out, 'clips'), exist_ok=True)
    rendered = set()

    def copies(sid):  # ce clip dans ce SWF et dans ses copies identiques (`also`)
        return ['%s#%d' % (p, sid) for p in [path] + entry.get('also', [])]
    for s in meta['symbols']:
        if s['kind'] != 'clip':
            continue
        sid = s['id']
        rendered.add(sid)
        ref = '%s#%d' % (path, sid)
        h = render_hash(render, s)
        if sid in primary and primary[sid][1] == h:
            primary[sid][0].setdefault('dup', []).extend(copies(sid))
            continue
        same = game.__dict__.setdefault('clip_seen', {}).get(h)
        if same is not None and same['x']['swf'] != path:  # même rendu dans un autre SWF du jeu (SWF embarqué…)
            same.setdefault('dup', []).extend(copies(sid))
            same['k'] = sorted(set(same['k']) | set(ctx.words(s['name'])))
            continue
        thumb = first_visible(render, s)
        if not thumb.getchannel('A').getbbox():
            continue  # clip entièrement vide (code AS3, repère invisible)
        dst = os.path.join(out, 'clips', '%d.png' % sid)
        thumb.save(dst, optimize=True)
        sd = swf.sprites[sid]
        labels = sorted(sd.labels, key=sd.labels.get)
        item = dict(i=ref, t='clip', n=s['name'], s=ctx.rel(dst), p=ref, w=s['w'], h=s['h'], f=s['frames'], c=coll,
                    u=game.source_url(path), x=dict(swf=path, id=sid, timeline=s['timeline'], labels=labels),
                    k=ctx.words(s['name'], *labels))
        if s['frames'] > 1:
            sheet = compact.sheet(os.path.join(render, '%d_sheet.png' % sid), os.path.join(out, 'clips', '%d_sheet' % sid),
                                  ctx.WORK)
            item.update(sh=ctx.rel(sheet), cols=s['cols'], fps=s['fps'])
        if entry.get('also'):
            item['dup'] = ['%s#%d' % (a, sid) for a in entry['also']]
        mine[sid] = (item, h)
        game.clip_seen.setdefault(h, item)
        game.add(item)
    for err in meta['errors']:
        print('  clip non rendu', path, err)
    if 'variant_of' in entry:
        for sid in swf.exports:
            if sid in primary and sid not in rendered:
                primary[sid][0].setdefault('dup', []).extend(copies(sid))
        return
    add_shapes(game, swf, path, work, out, coll, ctx)
    add_bitmaps(game, swf, path, work, out, coll, ctx)
    add_sounds(game, path, work, out, coll, ctx)


def add_shapes(game, swf, path, work, out, coll, ctx):
    used = shapes_used(swf)
    svg_dir = os.path.join(work, 'svg')
    os.makedirs(os.path.join(out, 'shapes'), exist_ok=True)
    seen = game.svg_seen
    for fn in sorted(os.listdir(svg_dir), key=lambda f: int(re.match(r'\d+', f).group())):
        sid = int(re.match(r'\d+', fn).group())
        data = open(os.path.join(svg_dir, fn), 'rb').read()
        hsh = hashlib.sha1(data).hexdigest()
        if hsh in seen:
            first = seen[hsh]
            if first['x']['swf'] == path:
                first['x'].setdefault('same', []).append(sid)
            else:
                first.setdefault('dup', []).append('%s#shape%d' % (path, sid))
            continue
        m = re.search(rb'height="([\d.]+)px" width="([\d.]+)px"', data)
        h, w = (float(m.group(1)), float(m.group(2))) if m else (0, 0)
        if w == 0 or h == 0:
            continue  # forme dégénérée (un trait de largeur nulle) : rien à voir
        dst = os.path.join(out, 'shapes', fn)
        open(dst, 'wb').write(data)
        owners = sorted(used.get(sid, ()))
        name = swf.exports.get(sid) or 'forme %d' % sid
        ref = '%s#shape%d' % (path, sid)
        item = dict(i=ref, t='svg', n=name, s=ctx.rel(dst), p=ref, w=round(w, 2), h=round(h, 2), z=len(data),
                    c=coll + ' · formes vectorielles', u=game.source_url(path), x=dict(swf=path, id=sid, owners=owners),
                    k=ctx.words(name, *owners), vec=1)
        seen[hsh] = item
        game.add(item)


def add_bitmaps(game, swf, path, work, out, coll, ctx):
    img_dir = os.path.join(work, 'img')
    for fn in sorted(os.listdir(img_dir)) if os.path.isdir(img_dir) else []:
        full = os.path.join(img_dir, fn)
        im = Image.open(full)
        ph = ctx.pixel_hash(im)
        sid = int(re.match(r'\d+', fn).group())
        ref = '%s#bitmap%d' % (path, sid)
        same = game.by_hash.get(ph) or game.same_as_file(im)
        if same is not None:
            same.setdefault('dup', []).append(ref)
            continue
        os.makedirs(os.path.join(out, 'bitmaps'), exist_ok=True)
        dst = os.path.join(out, 'bitmaps', fn)
        shutil.copy(full, dst)
        name = os.path.splitext(fn)[0].split('_', 1)[1] if '_' in fn else swf.exports.get(sid, 'bitmap %d' % sid)
        game.add(dict(i=ref, t='img', n=name, s=ctx.rel(dst), p=ref, w=im.width, h=im.height, f=1,
                      z=os.path.getsize(full), fmt=os.path.splitext(fn)[1][1:].upper(), c=coll + ' · bitmaps',
                      u=game.source_url(path), x=dict(swf=path, id=sid)), ph)


def add_sounds(game, path, work, out, coll, ctx):
    """sons exportés par FFDec ; un son identique (octet pour octet) à une ressource existante devient un doublon
    (Hammerfest : game.swf reprend les sons de _sounds.swf)"""
    snd_dir = os.path.join(work, 'snd')
    index = fla_items.sound_index(game)
    for fn in sorted(os.listdir(snd_dir)) if os.path.isdir(snd_dir) else []:
        src = os.path.join(snd_dir, fn)
        if fn.lower().endswith('.wav') and os.path.getsize(src) <= 44:
            continue  # en-tête WAV sans données (son en flux déclaré, vide : « -1.wav » d'Hammerfest)
        m = re.match(r'-?\d+', fn)
        sid = int(m.group()) if m else -1  # -1 : son en flux de la scène (sans numéro de caractère)
        ref = '%s#sound%d' % (path, sid) if sid >= 0 else '%s#%s' % (path, os.path.splitext(fn)[0])
        h = hashlib.sha1(open(src, 'rb').read()).hexdigest()
        if h in index:
            index[h].setdefault('dup', []).append(ref)
            continue
        os.makedirs(os.path.join(out, 'sounds'), exist_ok=True)
        dst = os.path.join(out, 'sounds', fn)
        shutil.copy(src, dst)
        item = dict(i=ref, t='snd', n=os.path.splitext(fn)[0], s=ctx.rel(dst), p=ref, z=os.path.getsize(dst),
                    fmt=os.path.splitext(fn)[1][1:].upper(), c=coll + ' · sons', u=game.source_url(path),
                    x=dict(swf=path, id=sid))
        game.add(item)
        index[h] = item


def render_hash(render, s):
    name = '%d_sheet.png' % s['id'] if s['frames'] > 1 else '%d.png' % s['id']
    im = Image.open(os.path.join(render, name)).convert('RGBA')
    return hashlib.sha1(b'%dx%d' % im.size + im.tobytes()).hexdigest()


def first_visible(render, s):
    """miniature d'un clip : sa première image non vide (certaines animations commencent vides)"""
    im = Image.open(os.path.join(render, '%d.png' % s['id'])).convert('RGBA')
    if s['frames'] < 2 or im.getchannel('A').getbbox():
        return im
    sheet = Image.open(os.path.join(render, '%d_sheet.png' % s['id'])).convert('RGBA')
    for f in range(s['frames']):
        x, y = (f % s['cols']) * s['w'], (f // s['cols']) * s['h']
        frame = sheet.crop((x, y, x + s['w'], y + s['h']))
        if frame.getchannel('A').getbbox():
            return frame
    return im


def shapes_used(swf):
    """forme -> noms des symboles exportés qui l'affichent (directement ou via des clips imbriqués)"""
    memo = {}

    def chars(sid, stack=()):
        if sid in memo:
            return memo[sid]
        found = set()
        if sid in swf.sprites and sid not in stack:
            for ops in swf.sprites[sid].frames:
                for kind, v in ops:
                    c = v.get('char') if kind == 'place' else None
                    if c is not None:
                        found.add(c)
                        found |= chars(c, stack + (sid,))
        memo[sid] = found
        return found

    used = {}
    for sid, name in swf.exports.items():
        for c in chars(sid) | {sid}:
            if c in swf.shapes:
                used.setdefault(c, set()).add(name)
    return used
