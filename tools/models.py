"""Modèles 3D d'un jeu (entrée `models` de games.json) : lecture, maillage pour la page (script .js, lisible aussi
en file://), OBJ et aperçu PNG.

Formats lus (Galaxy55) :
- `.bae` : COLLADA binaire. "BAE\\0" puis un nœud : u8 genre (2 = élément, 3 = élément avec attributs, 4 = donnée),
  nom (u8 longueur + octets) ; genre 3 : u8 nombre d'attributs, chacun nom + valeur ; genres 2 et 3 : u16 nombre
  d'enfants. Valeur : u8 type (1 entier, 2 flottant, 5 chaîne u8 + octets, 6 / 7 tableau d'entiers / de flottants :
  u8 pas, u24 nombre, valeurs 32 bits). Les `<input>` ne sont pas gardés : dans `<p>`, position puis normale, puis
  des indices vers des sources absentes du fichier (seules position et normale servent).
- `.md` (porte) : u8, u32 nombre de sommets, puis par sommet x, y, z, u, v, ombrage en flottants 32 bits (lu par
  Macro.getModel / Builder.load) ; u, v se placent dans la case du bloc (`cell` : la case de `texture` du bloc dans
  data.ods), v depuis le haut. À la suite : u32 longueur + script de l'éditeur 3D de Motion Twin.
"""
import json, os, struct

import render3d


def parse_bae(data):
    if data[:4] != b'BAE\0':
        raise ValueError('pas un fichier BAE')
    pos = [4]

    def take(n):
        pos[0] += n
        return data[pos[0] - n:pos[0]]

    def value():
        t = take(1)[0]
        if t in (1, 2):
            return struct.unpack('<i' if t == 1 else '<f', take(4))[0]
        if t == 5:
            return take(take(1)[0]).decode('latin-1')
        if t in (6, 7):
            take(1)
            n = int.from_bytes(take(3), 'little')
            return list(struct.unpack('<%d%s' % (n, 'i' if t == 6 else 'f'), take(4 * n)))
        raise ValueError('type de valeur %d inconnu' % t)

    def node():
        kind, name = take(1)[0], None
        name = take(take(1)[0]).decode('latin-1')
        attrs, kids, val = {}, [], None
        if kind == 3:
            for _ in range(take(1)[0]):
                key = take(take(1)[0]).decode('latin-1')
                attrs[key] = value()
        if kind in (2, 3):
            kids = [node() for _ in range(struct.unpack('<H', take(2))[0])]
        elif kind == 4:
            val = value()
        else:
            raise ValueError('nœud de genre %d inconnu' % kind)
        return dict(tag=name, attrs=attrs, kids=kids, value=val)

    root = node()
    if pos[0] != len(data):
        raise ValueError('octets en trop')
    return root


def bae_objects(root):
    out = []
    for geo in root['kids'][0]['kids']:
        mesh = geo['kids'][0]
        src = {k['attrs']['name']: k['kids'][0]['value'] for k in mesh['kids'] if k['tag'] == 'source'}
        obj = dict(name=geo['attrs']['name'], pos=[], nrm=[], mat=[])
        for pl in (k for k in mesh['kids'] if k['tag'] == 'polylist'):
            vcount, p = pl['kids'][0]['value'], pl['kids'][1]['value']
            step = len(p) // sum(vcount)
            start, at = len(obj['pos']) // 3, 0
            for n in vcount:
                corners = [p[(at + c) * step:(at + c) * step + 2] for c in range(n)]
                at += n
                for c in range(1, n - 1):
                    for pi, ni in (corners[0], corners[c], corners[c + 1]):
                        obj['pos'] += src['positions'][pi * 3:pi * 3 + 3]
                        obj['nrm'] += src['normals'][ni * 3:ni * 3 + 3]
            obj['mat'].append(dict(name=pl['attrs']['material'], start=start, count=len(obj['pos']) // 3 - start))
        out.append(obj)
    return out


def parse_md(data, cell):
    n = struct.unpack_from('<I', data, 1)[0]
    v = struct.unpack_from('<%df' % (n * 6), data, 5)
    end = 5 + n * 24
    script = ''
    if len(data) >= end + 4:
        size = struct.unpack_from('<I', data, end)[0]
        script = data[end + 4:end + 4 + size].decode('utf-8', 'replace')
    obj = dict(name='door', pos=[], uv=[], shade=[], mat=[])
    for q in range(n // 4):  # quadrilatères : sommets 0 1 2 3 -> triangles (0, 1, 2) et (2, 1, 3)
        for k in (0, 1, 2, 2, 1, 3):
            s = v[(q * 4 + k) * 6:(q * 4 + k) * 6 + 6]
            obj['pos'] += s[:3]
            obj['uv'] += [s[3] + cell[0] / 64, s[4] + cell[1] / 64]
            obj['shade'].append(s[5])
    obj['mat'].append(dict(name='texture.png', start=0, count=len(obj['pos']) // 3))
    return [obj], script


def write_obj(objects, path, up):
    lines, base = ['# converti depuis le fichier d\'origine de Motion Twin (géométrie seule), axe %s vers le haut' % up], 1
    for o in objects:
        lines.append('o %s' % o['name'])
        n = len(o['pos']) // 3
        lines += ['v %.6g %.6g %.6g' % tuple(o['pos'][i * 3:i * 3 + 3]) for i in range(n)]
        if o.get('nrm'):
            lines += ['vn %.6g %.6g %.6g' % tuple(o['nrm'][i * 3:i * 3 + 3]) for i in range(n)]
        if o.get('uv'):
            lines += ['vt %.6g %.6g' % (o['uv'][i * 2], 1 - o['uv'][i * 2 + 1]) for i in range(n)]
        uv, nrm = bool(o.get('uv')), bool(o.get('nrm'))
        corner = '{0}/{0}/{0}' if uv and nrm else '{0}/{0}' if uv else '{0}//{0}' if nrm else '{0}'
        for m in o['mat']:
            lines.append('usemtl %s' % m['name'])
            for t in range(m['start'], m['start'] + m['count'], 3):
                lines.append('f ' + ' '.join(corner.format(base + t + k) for k in range(3)))
        base += n
    open(path, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')


def add_models(game, ctx):
    for entry in game.cfg.get('models', []):
        path = entry['file']
        full = os.path.join(game.base, path)
        data = open(full, 'rb').read()
        script = ''
        if path.endswith('.bae'):
            objects, up = bae_objects(parse_bae(data)), 'y'  # COLLADA sans <up_axis> : Y vers le haut
        else:
            (objects, script), up = parse_md(data, entry.get('cell', [0, 0])), 'z'
        stem = os.path.splitext(os.path.basename(path))[0]
        out = os.path.join(ctx.GEN, game.cfg['id'], 'models', stem)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        tex = os.path.join(game.base, entry['texture']) if entry.get('texture') else None
        mesh = dict(up=up, objects=[{k: [round(x, 5) for x in v] if isinstance(v, list) and k != 'mat' else v
                              for k, v in o.items()} for o in objects])
        if tex:
            mesh['texture'] = ctx.rel(tex)
        with open(out + '.js', 'w', encoding='utf-8', newline='\n') as f:
            f.write('(window.MT_MESH = window.MT_MESH || {})[%s] = ' % json.dumps('%s:%s' % (game.cfg['id'], path)))
            json.dump(mesh, f, separators=(',', ':'))
            f.write(';\n')
        write_obj(objects, out + '.obj', up)
        render3d.thumbnail(objects, tex, out + '.png', 384, up)
        tris = sum(len(o['pos']) for o in objects) // 9
        mats = sorted({m['name'] for o in objects for m in o['mat']})
        x = dict(up=up, objects=[o['name'] for o in objects], tris=tris, mats=mats, mesh=ctx.rel(out + '.js'),
                 obj=ctx.rel(out + '.obj'))
        if entry.get('texture'):
            x['texture'] = '%s, case %d,%d' % (entry['texture'], *entry.get('cell', [0, 0]))
        if script:
            x['script'] = script
        game.add(dict(i=path, t='mdl', n=stem, s=ctx.rel(out + '.png'), p=path, z=len(data),
                      fmt=os.path.splitext(path)[1][1:].upper(), u=game.source_url(path), o=ctx.rel(full), x=x,
                      k=ctx.words(stem, *x['objects'], *mats)))
