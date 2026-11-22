"""Banques d'images CastleDB : un `.img` est un JSON {md5: "data:image/png;base64,…"} ; les colonnes « image » du
`.cdb` (type 7) y renvoient par ce md5. Chaque image est écrite telle quelle (octets décodés, sans réencodage) et
nommée d'après la ligne du `.cdb` qui l'utilise (champ name, title, tag ou id). Monster Hotel : data/goals.img.

Entrée `cdb_images` d'un jeu dans games.json : [{"img": "data/goals.img", "cdb": "data/goals.cdb"}].
"""
import base64, io, json, os

from PIL import Image


def labels(cdb_path, keys):
    """md5 -> noms des lignes qui affichent cette image (sous-listes comprises)"""
    data = json.load(open(cdb_path, encoding='utf-8'))
    out = {}

    def walk(line, parent):
        label = line.get('name') or line.get('title') or line.get('tag') or line.get('id') or parent
        for value in line.values():
            if isinstance(value, str) and value in keys:
                out.setdefault(value, []).append(label)
            elif isinstance(value, list):
                for sub in value:
                    if isinstance(sub, dict):
                        walk(sub, label)

    for sheet in data['sheets']:
        if '@' not in sheet['name']:  # les feuilles « A@b » sont les sous-listes, rangées dans les lignes de A
            for line in sheet['lines']:
                walk(line, sheet['name'])
    return out


def add(game, ctx):
    for entry in game.cfg.get('cdb_images', []):
        path = entry['img']
        bank = json.load(open(os.path.join(game.base, path), encoding='utf-8'))
        names = labels(os.path.join(game.base, entry['cdb']), set(bank)) if entry.get('cdb') else {}
        out = os.path.join(ctx.GEN, game.cfg['id'], 'cdb', path.replace('/', '_'))
        os.makedirs(out, exist_ok=True)
        coll = ctx.collection(game.cfg, path)
        for md5, uri in bank.items():
            head, b64 = uri.split(',', 1)
            raw = base64.b64decode(b64 + '=' * (-len(b64) % 4))  # base64 de Haxe, souvent sans « = » final
            ext = head.split('/')[1].split(';')[0]
            dst = os.path.join(out, '%s.%s' % (md5, 'jpg' if ext == 'jpeg' else ext))
            open(dst, 'wb').write(raw)
            im = Image.open(io.BytesIO(raw))
            found = names.get(md5, [])
            ref = '%s#%s' % (path, md5)
            item = dict(i=ref, t='img', n=found[0] if found else md5[:8], s=ctx.rel(dst), p=ref, w=im.width, h=im.height,
                        f=1, fmt=ext.upper(), z=len(raw), u=game.source_url(path), c=coll,
                        x=dict(cdb=entry.get('cdb'), md5=md5, uses=found), k=ctx.words(*found, md5))
            game.add(item, ctx.pixel_hash(im))
