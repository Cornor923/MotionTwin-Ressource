"""Découpe des planches (sprite sheets) en ressources séparées, avec les pixels d'origine seulement.

Entrée `sheets` d'un jeu dans games.json :
  file        planche dans le dossier du jeu (elle n'apparaît plus comme une image : ses morceaux la remplacent)
  slices      découpes reprises du code du jeu : {"name", "rect": [x, y, l, h], "cols", "rows"} (images en grille,
              ligne par ligne ; "n" = "cols"), "names" : nom de chaque image (liste, ou {"ods", "sheet", "column"})
  grid        taille de case quand le jeu adresse la planche par cases ; `cells` = nommage des cases (voir CELLS)
  marks       repères de travail peints dans la planche (voir MARKS) : un repère seul est écarté
  background  couleur de fond de la planche (« #ffffff ») que le jeu rend transparente : ignorée pour trouver les
              morceaux et pour reconnaître un morceau déjà présent ailleurs, mais gardée dans les pixels montrés
Le reste des pixels donne des morceaux par groupes de pixels proches ; un groupe de cases alignées sur la grille est
séparé case par case. Aucun pixel n'est modifié ni ajouté. Si des pixels dessinés ne sont dans aucun morceau (bords
qui débordent d'une case…), la planche entière est aussi montrée (collection « · planche entière »).
"""
import os
import numpy as np
from PIL import Image

import galaxy55
from ods import rows as ods_rows
from pixels import components, groups

CELLS = {'galaxy55_blocks': galaxy55.block_cells}
MARKS = {'galaxy55_marks': galaxy55.texture_marks}
OTHER = ' · autres éléments de la planche'


def register(game, ctx):
    """avant le parcours des dossiers : une copie de la planche (.gal, bitmap de SWF) y sera reconnue"""
    game.cutters = [Sheet(game, entry, ctx) for entry in game.cfg.get('sheets', [])]


def add_sheets(game, ctx):
    game.sheets = [s.cut() for s in game.cutters]


def finish(game):
    """copies de la planche ailleurs (bitmap d'un SWF…) : notées sur chacun de ses morceaux"""
    for record, pieces in game.sheets:
        for item in pieces:
            if record.get('dup'):
                item['x']['sheet_dup'] = record['dup']
        if record.get('whole') and record.get('dup'):
            record['whole']['dup'] = record['dup']


class Sheet:
    def __init__(self, game, entry, ctx):
        self.game, self.entry, self.ctx = game, entry, ctx
        self.path = entry['file']
        self.full = os.path.join(game.base, self.path)
        self.img = Image.open(self.full).convert('RGBA')
        self.a = np.asarray(self.img)
        bg = entry.get('background')
        self.bg = np.array([int(bg[i:i + 2], 16) for i in (1, 3, 5)]) if bg else None
        self.taken = np.zeros(self.a.shape[:2], bool)
        self.out = os.path.join(ctx.GEN, game.cfg['id'], 'sheets', os.path.splitext(self.path)[0].replace('/', '_'))
        self.coll = ctx.collection(game.cfg, self.path)
        self.stem = os.path.splitext(os.path.basename(self.path))[0]
        self.pieces = []
        self.ignore = self.lone_marks(MARKS[entry['marks']](self.a)) if 'marks' in entry else np.zeros_like(self.taken)
        self.record = dict(p=self.path, i=self.path)  # la planche elle-même : reçoit ses copies (dup), pas une fiche
        game.by_hash[ctx.pixel_hash(self.img)] = self.record
        game.by_size.setdefault(self.img.size, []).append((self.record, self.full))

    def ink(self, a):
        """pixels dessinés : non transparents et, si la planche a un fond, d'une autre couleur que lui"""
        on = a[..., 3] > 0
        if self.bg is not None:
            on &= ~((a[..., :3] == self.bg).all(axis=-1) & (a[..., 3] == 255))
        return on

    def lone_marks(self, marks):
        """pixels des repères qui ne touchent aucun dessin (peints sur du transparent) : ni ressource ni partie d'une
        ressource. Un repère posé sur un dessin reste dans le morceau, le dessin d'origine n'existant plus dessous."""
        ys = np.nonzero(marks.any(axis=1))[0]
        lone = np.zeros_like(marks)
        if not len(ys):
            return lone
        top, bottom = max(0, ys.min() - 40), ys.max() + 40
        alpha = self.a[top:bottom, :, 3]
        for x0, y0, x1, y1, m in components(alpha > 0):
            mk = marks[top + y0:top + y1 + 1, x0:x1 + 1] & m
            if mk.any() and (m & ~mk & (alpha[y0:y1 + 1, x0:x1 + 1] >= 64)).sum() <= 3:
                lone[top + y0:top + y1 + 1, x0:x1 + 1] |= m
        return lone

    def names(self, s):
        src = s.get('names')
        if isinstance(src, dict):
            return [r[src['column']] for r in ods_rows(os.path.join(self.game.base, src['ods']), src['sheet'])]
        return src

    def cut(self):
        os.makedirs(self.out, exist_ok=True)
        for s in self.entry.get('slices', []):
            x, y, w, h = s['rect']
            cols, rows = s.get('cols', s.get('n', 1)), s.get('rows', 1)
            names = self.names(s) or []
            for k in range(cols * rows):
                label = names[k] if k < len(names) else s['name'] if cols * rows == 1 else '%s (%d)' % (s['name'], k + 1)
                rect = (x + k % cols * w, y + k // cols * h, w, h)
                self.piece(rect, None, label, self.coll, dict(slice=s['name']), [s['name']])
        grid = self.entry.get('grid')
        if 'cells' in self.entry:
            for (cx, cy), uses in sorted(CELLS[self.entry['cells']](self.game.base).items(), key=lambda t: t[0][::-1]):
                self.named_cell(cx, cy, grid, uses)
        for x0, y0, x1, y1, mask in groups(self.ink(self.a) & ~self.taken & ~self.ignore):
            if mask.sum() < 24 and self.taken[max(0, y0 - 1):y1 + 2, max(0, x0 - 1):x1 + 2].any():
                continue  # bord d'un dessin qui déborde d'une case déjà découpée
            if grid and x0 % grid == 0 and y0 % grid == 0 and (x1 + 1) % grid == 0 and (y1 + 1) % grid == 0:
                for cy in range(y0 // grid, (y1 + 1) // grid):
                    for cx in range(x0 // grid, (x1 + 1) // grid):
                        sub = mask[cy * grid - y0:(cy + 1) * grid - y0, cx * grid - x0:(cx + 1) * grid - x0]
                        if sub.any():
                            self.piece((cx * grid, cy * grid, grid, grid), sub, 'case %d,%d' % (cx, cy),
                                       self.coll + OTHER, dict(cell=[cx, cy]))
            else:  # planche à fond : rectangle tel quel, fond compris
                self.piece((x0, y0, x1 - x0 + 1, y1 - y0 + 1), mask if self.bg is None else None,
                           '%s %d,%d' % (self.stem, x0, y0), self.coll + OTHER, {})
        left = int((self.ink(self.a) & ~self.taken & ~self.ignore).sum())
        if left:  # tout n'est pas dans un morceau : la planche telle quelle, en plus
            self.record['whole'] = item = dict(
                i=self.path, t='img', n='%s (planche entière)' % self.stem, s=self.ctx.rel(self.full), p=self.path,
                w=self.img.width, h=self.img.height, f=1, fmt=os.path.splitext(self.path)[1][1:].upper(), px=1,
                z=os.path.getsize(self.full), u=self.game.source_url(self.path), c=self.coll + ' · planche entière',
                x=dict(whole=left, pieces=len(self.pieces)), k=self.ctx.words(self.stem, 'planche'))
            self.game.add(item)
        return self.record, self.pieces

    def named_cell(self, cx, cy, grid, uses):
        names = []
        for bid, role, name in uses:
            label = name or bid
            if label not in names:
                names.append(label)
        roles = sorted({role for _, role, _ in uses})
        label = names[0] + (' (%s)' % roles[0] if len(roles) == 1 else '')
        blocks = ['%s%s (%s)' % (bid, ' « %s »' % name if name else '', role) for bid, role, name in uses]
        words = [w for bid, _, name in uses for w in (bid, name) if w]
        self.piece((cx * grid, cy * grid, grid, grid), None, label, self.coll, dict(cell=[cx, cy], blocks=blocks), words)

    def same_drawing(self, crop, ink):
        """ressource déjà présente avec le même dessin, fonds et marges ôtés (un fruit du site = une case)"""
        index = getattr(self.game, 'drawings', None)
        if index is None:
            index = self.game.drawings = {}
            for entries in list(self.game.by_size.values()):
                for item, full in entries:
                    if item is not self.record and full.lower().endswith(('.png', '.gif')):
                        a = np.asarray(Image.open(full).convert('RGBA'))
                        if a[..., 3].any():
                            index.setdefault(drawing_key(a, a[..., 3] > 0), item)
        return index.get(drawing_key(crop, ink))


    def piece(self, rect, mask, name, coll, extra, words=()):
        x, y, w, h = (int(v) for v in rect)
        crop = self.a[y:y + h, x:x + w].copy()
        crop[self.ignore[y:y + h, x:x + w]] = 0
        if mask is not None:
            crop[~mask] = 0
        ink = self.ink(crop)
        self.taken[y:y + h, x:x + w] |= ink if mask is not None else True
        if not ink.any():
            return
        ref = '%s#%d,%d,%d,%d' % (self.path, x, y, w, h)
        same = self.same_drawing(crop, ink) if self.bg is not None else None
        if same is not None:
            same.setdefault('dup', []).append(ref)
            return
        im = Image.fromarray(crop)
        dst = os.path.join(self.out, '%d_%d_%d_%d.png' % (x, y, w, h))
        im.save(dst, optimize=True)
        item = dict(i=ref, t='img', n=name, s=self.ctx.rel(dst), p=ref, w=w, h=h, f=1, fmt='PNG', c=coll, px=1,
                    z=os.path.getsize(dst), u=self.game.source_url(self.path), o=self.ctx.rel(self.full),
                    x=dict(sheet=self.path, rect=[x, y, w, h], **extra), k=self.ctx.words(name, self.stem, *words))
        before = len(self.game.items)
        self.game.add(item, self.ctx.pixel_hash(im))
        if len(self.game.items) > before:
            self.pieces.append(item)


def drawing_key(a, ink):
    ys, xs = ink.nonzero()
    box = (slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1))
    sub, mask = a[box], ink[box]
    return (sub.shape[:2], mask.tobytes(), sub[mask][:, :3].tobytes())
