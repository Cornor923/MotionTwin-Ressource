"""Ressources des .fla d'un jeu : tous les .fla de son dossier (moins `exclude`), symboles en SVG, bitmaps, sons.

XFL (ZIP, CS5+) : xfl.py. Binaire (OLE, Flash 5 à CS4) : fla_bin.py (fla-decoder, corrigé par fla_patch.py,
fla_archive.py, fla_filters.py). Dans les deux cas les symboles sont composés entiers (instances, bitmaps posés,
masques, filtres, modes de fusion), première image de chaque calque. Un symbole au rendu identique à un autre
(même .fla recopié ailleurs…) devient un doublon ; un symbole du même nom qu'un clip d'un SWF du jeu est relié à ce
clip (« Même nom dans »). Bitmaps et sons identiques à une ressource existante deviennent des doublons.
"""
import hashlib, os, re

import fla_bin, fla_compose, xfl


def add_fla(game, ctx):
    for root, _, files in os.walk(game.base):
        for fn in sorted(files):
            path = os.path.relpath(os.path.join(root, fn), game.base).replace(os.sep, '/')
            if fn.lower().endswith('.fla') and not game.excluded(path):
                add_one(game, ctx, os.path.join(root, fn), path)


def add_one(game, ctx, full, path):
    out = os.path.join(ctx.GEN, game.cfg['id'], 'fla', os.path.splitext(path)[0].replace('/', '_'))
    is_xfl = open(full, 'rb').read(2) == b'PK'
    try:
        doc = xfl.load(full) if is_xfl else fla_bin.load(full, os.path.join(out, 'sons'))
    except Exception as e:  # .fla illisible : signalé, les autres continuent
        print('  .fla illisible', path, type(e).__name__, e)
        return
    coll, label, kind = ctx.collection(game.cfg, path), os.path.basename(path), 'XFL' if is_xfl else 'binaire'
    base = dict(u=game.source_url(path), o=ctx.rel(full))
    os.makedirs(os.path.join(out, 'bitmaps'), exist_ok=True)
    for k, (name, im) in enumerate(sorted(doc['raw_bitmaps'].items())):
        ref = '%s#%s' % (path, name)
        same = game.by_hash.get(ctx.pixel_hash(im)) or game.same_as_file(im)
        if same is not None:
            same.setdefault('dup', []).append(ref)
            continue
        dst = os.path.join(out, 'bitmaps', '%03d.png' % k)
        im.save(dst, optimize=True)
        game.add(dict(i=ref, t='img', n=os.path.splitext(name)[0], s=ctx.rel(dst), p=ref, w=im.width, h=im.height,
                      f=1, fmt='PNG', z=os.path.getsize(dst), c=coll + ' · bitmaps (%s)' % label,
                      x=dict(fla=path, kind=kind), **base), ctx.pixel_hash(im))
    sounds = sound_index(game)
    for snd in doc.get('sounds', []):
        ref = '%s#%s' % (path, snd['name'])
        h = hashlib.sha1(open(snd['path'], 'rb').read()).hexdigest()
        if h in sounds:
            sounds[h].setdefault('dup', []).append(ref)
            continue
        item = dict(i=ref, t='snd', n=os.path.splitext(snd['name'])[0], s=ctx.rel(snd['path']), p=ref,
                    z=os.path.getsize(snd['path']), fmt=snd['path'][-3:].upper(), c=coll + ' · sons (%s)' % label,
                    x=dict(fla=path, kind=kind), **base)
        game.add(item)
        sounds[h] = item
    add_symbols(game, ctx, doc, path, out, coll + ' · symboles (%s)' % label, kind, base)


def add_symbols(game, ctx, doc, path, out, coll, kind, base):
    seen = game.__dict__.setdefault('fla_svg_seen', {})
    swf_names = game.__dict__.setdefault('swf_names', {})
    if not swf_names:
        for it in game.items:
            if (it.get('x') or {}).get('swf') and it['t'] in ('clip', 'svg'):
                swf_names.setdefault(it['n'], []).append(it['p'])
    os.makedirs(os.path.join(out, 'symboles'), exist_ok=True)
    for k, name in enumerate(sorted(doc['symbols'])):
        try:
            svg = fla_compose.render(doc, name)
        except RecursionError:
            svg = None
        if not svg:
            continue
        ref = '%s#%s' % (path, name)
        h = hashlib.sha1(svg.encode('utf-8')).hexdigest()
        if h in seen:
            seen[h].setdefault('dup', []).append(ref)
            continue
        dst = os.path.join(out, 'symboles', '%04d.svg' % k)
        open(dst, 'w', encoding='utf-8', newline='\n').write(svg)
        w, hh = (float(v) for v in re.search(r'width="([\d.]+)" height="([\d.]+)"', svg).groups())
        x = dict(fla=path, kind=kind, symbol=name)
        short = name.rsplit('/', 1)[-1].strip()
        if swf_names.get(short):
            x['same_swf'] = swf_names[short]
        item = dict(i=ref, t='svg', n=short, s=ctx.rel(dst), p=ref, w=round(w, 2), h=round(hh, 2),
                    z=os.path.getsize(dst), c=coll, vec=1, x=x, k=ctx.words(name, os.path.basename(path)), **base)
        game.add(item)
        seen[h] = item


def sound_index(game):
    index = game.__dict__.get('sound_hashes')
    if index is None:
        index = game.sound_hashes = {}
        for it in game.items:
            if it['t'] == 'snd' and os.path.exists(it['s']):
                index.setdefault(hashlib.sha1(open(it['s'], 'rb').read()).hexdigest(), it)
    return index
