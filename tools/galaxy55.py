"""Données propres à Galaxy55 : noms des cases de texture.png (tableur officiel com/data.ods) et repères numérotés.

texture.png est une grille de 64 × 64 cases de 32 px ; un bloc y désigne ses faces par `texture`, `texUp`, `texDown`
(colonne, ligne) et le drapeau `Textures(…)` (faces avant, arrière, gauche, droite), comme le lit `com/Block.hx`.
Motion Twin a peint dans la planche des numéros de colonne (0 à 63, ligne 5, orange) et de ligne (1 à 12, colonne 26,
bleu) : des repères de travail, pas des ressources. Un repère seul est écarté ; un dessin que Motion Twin a recouvert
d'un repère le garde, car le dessin d'origine n'existe plus sous les chiffres.
"""
import os, re, zipfile
import xml.etree.ElementTree as ET
import numpy as np

from pixels import components

T = '{urn:oasis:names:tc:opendocument:xmlns:table:1.0}'
P = '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p'
ROLES = {'texture': 'côtés', 'texUp': 'dessus', 'texDown': 'dessous'}
FACES = ['face avant', 'face arrière', 'face gauche', 'face droite']


def ods_rows(path, sheet):
    root = ET.fromstring(zipfile.ZipFile(path).read('content.xml'))
    for table in root.iter(T + 'table'):
        if table.get(T + 'name') != sheet:
            continue
        rows = []
        for r in table.iter(T + 'table-row'):
            cells = []
            for c in r.findall(T + 'table-cell'):
                n = min(int(c.get(T + 'number-columns-repeated', '1')), 64)
                cells += ['\n'.join(''.join(p.itertext()) for p in c.findall(P))] * n
            while cells and cells[-1] == '':
                cells.pop()
            if cells:
                rows.append(cells)
        head = rows[0]
        out = []
        for r in rows[1:]:
            if r[0].startswith('$'):  # fin de table du format ods.Data de Motion Twin
                break
            out.append(dict(zip(head, r + [''] * (len(head) - len(r)))))
        return out
    raise KeyError(sheet)


def block_cells(game_dir):
    """(colonne, ligne) -> [(identifiant du bloc, face, nom français ou '')] d'après com/data.ods"""
    cells = {}
    for d in ods_rows(os.path.join(game_dir, 'com', 'data.ods'), 'blocks'):
        name = '' if d['name'] in ('', '-') else d['name']
        uses = [(d[k], ROLES[k]) for k in ROLES if d[k]]
        m = re.search(r'Textures\(([^)]*)\)', d['flags'])
        if m:
            v = [int(t) for t in re.findall(r'\d+', m.group(1))]
            uses += [('%d,%d' % (v[i], v[i + 1]), FACES[i // 2]) for i in range(0, len(v) - 1, 2)]
        for cell, role in uses:
            x, y = (int(t) for t in cell.split(','))
            cells.setdefault((x, y), []).append((d['id'], role, name))
    return cells


def texture_marks(rgba):
    """masque des repères numérotés : chiffres (remplissage orange ou bleu), leur contour noir et leur ombre lissée"""
    r, g, b, a = (rgba[..., i].astype(int) for i in range(4))
    orange = (r == 255) & (b == 0) & (g >= 120) & (a == 255)
    blue = (b == 255) & (r <= 40) & (g >= 120) & (a == 255)
    zone = np.zeros(a.shape, bool)
    for x0, y0, x1, y1, _ in components(orange):
        if 160 <= y0 and y1 <= 180 and x1 - x0 <= 11 and y1 - y0 <= 7:  # nombres de la ligne 5 (1 ou 2 chiffres)
            zone[y0 - 2:y1 + 3, x0 - 2:x1 + 3] = True
    for x0, y0, x1, y1, _ in components(blue):
        if 832 <= x0 and x1 < 864 and x1 - x0 <= 11 and y1 - y0 <= 7:  # nombres de la colonne 26
            zone[y0 - 2:y1 + 3, x0 - 2:x1 + 3] = True
    black = (r == 0) & (g == 0) & (b == 0) & (a > 0)
    return zone & (orange | blue | black)
