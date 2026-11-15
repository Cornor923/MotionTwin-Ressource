"""Découpes des planches du client isométrique de Mush, reprises du code et des données officielles.

- `tiles.xml` (clients/iso/xml) : `<sheet src="BmpGfx2">` puis `<slice id params="x,y,l,h,nb_x,nb_y">` (lu par
  Data.addToStore -> mt.pix.Store.slice). Les attributs flipX / flipY / rot redessinent les mêmes pixels : pas de
  découpe en plus.
- `char.png` (BmpGfxChar) : Data.hx, regChar, cases de 32 × 48, une ligne par héros de data/Data.ods (feuille
  `heros`, jusqu'à ADMIN), puis DEREK_HOGAN (y 1776), ANDIE_GRAHAM (y 1824) et les apparences de data/DataEco.ods
  (feuille `heroSkins` : héros, numéro, ligne y ; nom « HÉROS$n » comme dans le code). Par héros : 4 poses, marche à
  droite (6 images), marche à gauche (6), ligoté, couché (64 × 48 en x 544) ; les variantes retournées sont omises.
"""
import os, re

from ods import rows as ods_rows

W, H = 32, 48


def tile_slices(game_dir, sheet):
    x = open(os.path.join(game_dir, 'clients', 'iso', 'xml', 'tiles.xml'), encoding='utf-8').read()
    x = re.sub(r'<!--.*?-->', '', x, flags=re.S)
    m = re.search(r'<sheet src="%s"[^>]*>(.*?)</sheet>' % re.escape(sheet), x, re.S)
    out = []
    for s in re.finditer(r'<slice\s+id="([^"]+)"\s+params\s*=\s*"([^"]+)"', m.group(1) if m else ''):
        p = [int(v) if v.strip().lstrip('-').isdigit() else 1 for v in s.group(2).split(',')]
        p += [1] * (6 - len(p))
        out.append(dict(name=s.group(1), rect=p[:4], cols=p[4], rows=p[5]))
    return out


def hero(name, y):
    return [dict(name=name, rect=[0, y, W, H], cols=4),
            dict(name=name + '_WALK_RIGHT', rect=[4 * W, y, W, H], cols=6),
            dict(name=name + '_WALK_LEFT', rect=[10 * W, y, W, H], cols=6),
            dict(name=name + '_TIED', rect=[16 * W, y, W, H]),
            dict(name=name + '_LAID', rect=[544, y, 64, 48])]


def char_slices(game_dir):
    data = os.path.join(game_dir, 'data')
    out = []
    for i, h in enumerate(ods_rows(os.path.join(data, 'Data.ods'), 'heros')):
        if h['id'] == 'ADMIN':
            break
        out += hero(h['id'], i * H)
    out += hero('DEREK_HOGAN', 1776) + hero('ANDIE_GRAHAM', 1824)
    for s in ods_rows(os.path.join(data, 'DataEco.ods'), 'heroSkins'):
        out += hero('%s$%s' % (s['hid'], s['sk']), int(s['y']))
    return out
