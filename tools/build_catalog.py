"""Construit catalog.js : toutes les ressources graphiques et sonores officielles des jeux listés dans games.json.

usage : python build_catalog.py            (depuis n'importe où ; MT_WORK = dossier des exports FFDec et rendus)
Sources : fichiers de l'archive Motion Twin (référencés sur place), animations GraphicsGale décodées, clips Flash
rendus par render_symbols.py, formes SVG / bitmaps / sons exportés par FFDec (rebuild.py), copiés dans gen/, morceaux
des planches découpées (sheets.py), modèles 3D (models.py), réglages de son LabChirp (.lch, avec le son du même nom),
symboles, bitmaps et sons des .fla (fla_items.py).
"""
import fnmatch, hashlib, json, os, re, shutil, subprocess, sys, time
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'flash'))
import fla_items, gal, models, presets, sheets, swf_items

WORK = os.environ.get('MT_WORK', os.path.join(os.path.expanduser('~'), 'motiontwin-assets-work'))
GEN = os.path.join(ROOT, 'gen')
RASTER = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.webp', '.tga'}  # .tga : copie PNG dans gen/
AUDIO = {'.mp3', '.wav', '.ogg'}


def rel(p):
    return os.path.relpath(p, ROOT).replace(os.sep, '/')


def pixel_hash(im):
    im = im.convert('RGBA')
    return hashlib.sha1(b'%dx%d' % im.size + im.tobytes()).hexdigest()


def premultiplied(im):
    a = np.asarray(im.convert('RGBA'), dtype=np.int32)
    return np.dstack([a[..., :3] * a[..., 3:] // 255, a[..., 3:]])


def collection(game, path):
    best = ''
    for prefix in game['collections']:
        if (path == prefix or path.startswith(prefix + '/')) and len(prefix) > len(best):
            best = prefix
    return game['collections'][best] if best else os.path.dirname(path) or 'Racine'


def words(*parts):
    """mots-clés de recherche : chaque nom entier et ses morceaux (mcHeroRun -> mcherorun, mc, hero, run)"""
    out = []
    for p in parts:
        out.append(str(p))
        out += [w for w in re.split(r'[^0-9A-Za-zÀ-ÿ]+|(?<=[a-z])(?=[A-Z])', str(p)) if w]
    return sorted({w.lower() for w in out})


class Game:
    def __init__(self, cfg, archive, repo):
        self.cfg = cfg
        self.base = os.path.join(archive, cfg['folder'])
        self.repo = repo
        self.items = []
        self.by_hash = {}
        self.by_size = {}
        self.clips = {}  # chemin du SWF -> id -> (ressource, empreinte du rendu)
        self.svg_seen = {}  # empreinte d'un SVG -> ressource

    def source_url(self, path):
        return '%s/blob/main/%s/%s' % (self.repo, self.cfg['folder'], path)

    def excluded(self, path):
        return any(fnmatch.fnmatch(path, pat) for pat in self.cfg.get('exclude', []))

    def add(self, item, phash=None):
        item.setdefault('c', collection(self.cfg, item['p'].split('#')[0]))
        item['g'] = self.cfg['id']
        item['i'] = '%s:%s' % (self.cfg['id'], item['i'])
        if phash:
            first = self.by_hash.get(phash)
            if first is not None:
                first.setdefault('dup', []).append(item['p'])
                return
            self.by_hash[phash] = item
        self.items.append(item)

    def scan(self):
        own = {e['file'] for e in self.cfg.get('sheets', []) + self.cfg.get('models', [])}  # traités à part
        for top in self.cfg['scan']:
            for dirpath, _, files in os.walk(os.path.join(self.base, top)):
                for fn in sorted(files, key=lambda f: (f.lower().endswith('.gal'), f)):  # .gal après son PNG
                    full = os.path.join(dirpath, fn)
                    path = os.path.relpath(full, self.base).replace(os.sep, '/')
                    ext = os.path.splitext(fn)[1].lower()
                    if self.excluded(path) or path in own:
                        continue
                    if ext in RASTER:
                        self.raster(full, path)
                    elif ext == '.svg':
                        self.add(dict(i=path, t='svg', n=os.path.splitext(fn)[0], s=rel(full), p=path,
                                      z=os.path.getsize(full), u=self.source_url(path)))
                    elif ext in AUDIO:
                        self.add(dict(i=path, t='snd', n=os.path.splitext(fn)[0], s=rel(full), p=path,
                                      z=os.path.getsize(full), u=self.source_url(path)))
                    elif ext == '.gal':
                        self.gal(full, path)
                    elif ext == '.lch':
                        self.add(presets.item(self, full, path, sys.modules[__name__]))

    def raster(self, full, path):
        try:
            im = Image.open(full)
            n = getattr(im, 'n_frames', 1)
            w, h = im.size
            ph = pixel_hash(im)
        except Exception as e:
            print('  illisible', path, e)
            return
        t = 'gif' if n > 1 else 'img'
        item = dict(i=path, t=t, n=os.path.splitext(os.path.basename(path))[0], s=rel(full), p=path, w=w, h=h,
                    f=n, z=os.path.getsize(full), fmt=os.path.splitext(path)[1][1:].upper(), u=self.source_url(path))
        if path.lower().endswith('.tga'):  # le navigateur ne lit pas le TGA : copie PNG, fichier d'origine en `o`
            out = os.path.join(GEN, self.cfg['id'], 'conv', path + '.png')
            os.makedirs(os.path.dirname(out), exist_ok=True)
            im.convert('RGBA').save(out, optimize=True)
            item.update(s=rel(out), o=rel(full))
        if ph not in self.by_hash:
            self.by_size.setdefault((w, h), []).append((item, full))
        self.add(item, ph)

    def same_as_file(self, im):
        """image d'archive identique à `im` (bitmap Flash : alpha prémultiplié, arrondi à 1 près)"""
        mine = premultiplied(im)
        for item, full in self.by_size.get(im.size, []):
            if int(np.abs(premultiplied(Image.open(full)) - mine).max()) <= 1:
                return item
        return None

    def gal(self, full, path):
        frames, delays = gal.frames(full)
        out = os.path.join(GEN, self.cfg['id'], 'gal', os.path.splitext(path)[0])
        os.makedirs(os.path.dirname(out), exist_ok=True)
        frames[0].save(out + '.png', optimize=True)
        item = dict(i=path, t='anim', n=os.path.splitext(os.path.basename(path))[0], s=rel(out + '.png'), p=path,
                    w=frames[0].width, h=frames[0].height, f=len(frames), z=os.path.getsize(full), fmt='GAL',
                    u=self.source_url(path), px=1, o=rel(full))
        if len(frames) > 1:
            item['cols'] = gal.save_sheet(frames, out + '_sheet.png')
            item['sh'] = rel(out + '_sheet.png')
            item['d'] = delays
        self.add(item, pixel_hash(frames[0]) if len(frames) == 1 else None)


def git_commit(path):
    try:
        return subprocess.check_output(['git', '-C', path, 'rev-parse', 'HEAD'], text=True).strip()
    except Exception:
        return None


def main():
    t0 = time.time()
    cfg = json.load(open(os.path.join(ROOT, 'games.json'), encoding='utf-8'))
    archive = os.path.join(ROOT, cfg['archive'])
    shutil.rmtree(GEN, ignore_errors=True)  # gen/ ne contient que ce que ce catalogue référence
    games, items = [], []
    for gcfg in cfg['games']:
        g = Game(gcfg, archive, cfg['repo'])
        print('==', gcfg['name'])
        sheets.register(g, sys.modules[__name__])
        g.scan()
        presets.pair(g)
        sheets.add_sheets(g, sys.modules[__name__])
        models.add_models(g, sys.modules[__name__])
        for entry in gcfg.get('swf', []):
            swf_items.add_swf(g, entry, sys.modules[__name__])
        fla_items.add_fla(g, sys.modules[__name__])
        sheets.finish(g)
        for it in g.items:
            it.setdefault('k', words(it['n']))
        games.append(dict(id=gcfg['id'], name=gcfg['name'], year=gcfg['year'], folder=gcfg['folder'],
                          summary=gcfg['summary'], notes=gcfg.get('notes', []), count=len(g.items),
                          swf=[dict(file=e['file'], also=e.get('also', [])) for e in gcfg.get('swf', [])]))
        items += g.items
        kinds = {}
        for it in g.items:
            kinds[it['t']] = kinds.get(it['t'], 0) + 1
        print('  %d ressources %s' % (len(g.items), kinds))
    catalog = dict(generated=time.strftime('%Y-%m-%d'), repo=cfg['repo'], commit=git_commit(archive),
                   license=cfg['license'], games=games, items=items)
    with open(os.path.join(ROOT, 'catalog.js'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('window.MT_CATALOG = ')
        json.dump(catalog, f, ensure_ascii=False, separators=(',', ':'))
        f.write(';\n')
    print('%d ressources, %.1fs' % (len(items), time.time() - t0))


if __name__ == '__main__':
    main()
