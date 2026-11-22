"""Corrections de lecture des .fla binaires, appliquées à fla-decoder à l'import (sans modifier ses fichiers).

Calques (CPicLayer) et numéros des objets MFC : voir fla_archive.py (fla-decoder terminait chaque calque en sautant
au dernier marqueur de fin de la page : seul le premier calque d'un symbole était lu).

Formes : l'en-tête donne le nombre de bords (`edge_hint`) ; au schéma de données 5 dans une forme de schéma 3 et
plus (Flash 8 et après), un bord droit (pas de point de contrôle) est suivi d'un octet nul (pas dans les formes de
schéma 2 de Flash MX). fla-decoder prenait cet octet pour la fin de la liste, puis lisait la
suite des bords comme le compteur de courbes cubiques et avalait le reste du flux. Un 0 à la place d'un bord avant
`edge_hint` bords lus reste sauté (enregistrement vide).

Courbes cubiques des formes (schéma de forme 5, après les bords : s32 nombre puis données de longueur variable,
non décodées) : elles doublent les bords déjà lus, seule leur fin compte. fla-decoder les lisait par blocs de 32
octets et avalait la suite. `after_cubics` cherche la suite : champs de l'image pour la forme propre d'une image
(schéma 26 : 1a, u16, 00|01 06, 00 00), élément suivant ou fin de liste pour une forme enfant.

Images (CPicFrame) de schéma 26 (Flash CS3) : fla-decoder ne lit pas 10 octets finaux (u16, u32, u32, toujours
00 00 01 00 00 00 00 00 00 00 dans l'archive) ; sans eux la lecture du calque se décale et les images et calques
suivants sont perdus.

Instances de symboles (CPicSprite = clip, CPicSymbol = graphique, inconnu de fla-decoder qui s'arrêtait là,
CPicButton) : fla-decoder lit les champs de symbole au mauvais endroit pour ces fichiers (schéma 19, de Flash 8 à CS4) puis saute
la fin de l'instance au premier marqueur venu : la référence au symbole est fausse et la suite de la page (autres
calques) se perd. Disposition relevée dans les .fla de l'archive, après la base CPicObj :
  u8 schéma (19), matrice 6 × i32 (a b c d en 16.16, tx ty en twips), u16, u16, u8,
  transformation de couleur 8 × i16 (alpha, rouge, vert, bleu : multiplicateur en 8.8 puis décalage),
  8 octets d'options de l'effet de couleur, CString Unicode, u32 = numéro du flux « S n » du symbole posé ;
  puis, pour un clip : 3 octets, u8 drapeau de filtres (si 1 : u32 nombre puis les filtres, lus par fla_filters.py),
  24 octets, CString, CString nom d'instance, 22 octets,
  CString métadonnées de composant ; pour un graphique : 7 octets. L'image parente reprend ensuite (marqueur END : fin de sa liste d'éléments et
  sa position indéfinie). Filtre de type inconnu, ou bouton : la fin est cherchée au marqueur END.
"""
import re, struct

from fla_decoder import decoder

import fla_filters

CSTRING_W = bytes((0xFF, 0xFE, 0xFF))  # début d'une chaîne MFC Unicode
END = bytes.fromhex('00000000008000000080')
_read_obj = decoder.read_cpicobj_fields
_fallback = {'CPicSprite': decoder.read_cpicsprite, 'CPicButton': decoder.read_cpicbutton,
             'CPicSymbol': lambda r, ar: decoder.read_cpicobj_fallback('CPicSymbol', r, ar)}


def cstring(buf, k):
    """(texte, position suivante) de la CString Unicode en `k`, ou (None, k)"""
    if buf[k:k + 3] != CSTRING_W:
        return None, k
    n, k = buf[k + 3], k + 4
    if n == 0xFF:
        n, k = struct.unpack_from('<H', buf, k)[0], k + 2
    return buf[k:k + 2 * n].decode('utf-16le', 'replace'), k + 2 * n


FAIL = (None,) * 4
BLOCK = {19: 24, 22: 126}  # après les filtres : u8 mode de fusion (numéros SWF), u8 cache bitmap, … (CS4 : 22)


def clip_tail(buf, p, schema):
    """(position de la suite, nom d'instance, filtres actifs, mode de fusion) d'un clip, ou FAIL si la fin n'est pas
    reconnue"""
    if p + 28 > len(buf):
        return FAIL
    q, filters = p + 4, []
    if buf[p + 3]:
        filters, q = fla_filters.parse(buf, q + 4, struct.unpack_from('<I', buf, q)[0])
        if filters is None:
            return FAIL
    blend = buf[q] if q < len(buf) else 0
    _, q = cstring(buf, q + BLOCK[schema])
    name, q = cstring(buf, q)
    meta, q = cstring(buf, q + 22) if name is not None else (None, q)
    if meta is None or not (buf[q:q + 10] == END or buf[q + 1:q + 2] in (b'\x80', b'\xff')):
        return FAIL
    return q, name, filters, blend


def read(kind):
    def reader(r, ar):
        start = r.pos
        out = _read_obj(r, ar)
        buf, e = r.buf, r.pos
        if e + 62 > len(buf) or buf[e] not in BLOCK or buf[e + 54:e + 57] != CSTRING_W:
            if out.get('children'):
                return out
            r.pos = start
            return _fallback[kind](r, ar)
        a, b, c, d, tx, ty = struct.unpack_from('<6i', buf, e + 1)
        am, ao, rm, ro, gm, go, bm, bo = struct.unpack_from('<8h', buf, e + 30)
        _, p = cstring(buf, e + 54)
        ref = struct.unpack_from('<I', buf, p)[0]
        end, name, filters, blend = clip_tail(buf, p + 4, buf[e]) if kind == 'CPicSprite' else \
            (p + 11, None, None, None) if kind == 'CPicSymbol' else FAIL
        if end is None:
            end = buf.find(END, p + 4)
            end = len(buf) if end < 0 else end
        r.pos = end
        out['use'] = (ref, (a / 65536, b / 65536, c / 65536, d / 65536, tx / 20, ty / 20),
                      (rm / 256, gm / 256, bm / 256, am / 256, ro, go, bo, ao), filters or None, blend)
        out['instance_name'] = name
        return out
    return reader


LIMIT = 10_000_000  # ultra-twips (environ 3 900 px) : au-delà, le dessin des bords a déraillé


def read_edges(r, schema, hint, fills=1 << 15, lines=1 << 15, pad=False):
    """bords, même encodage que fla-decoder (drapeaux, changement de style, 3 déplacements), sans s'arrêter aux
    enregistrements vides tant que les bords annoncés (hint) ne sont pas lus. Tous les octets sont lus ; après un
    style hors des tables (schéma 5) ou une coordonnée hors limite, les bords ne sont plus gardés (dessin faux)."""
    edges, x, y, f0, f1, line, bad, count = [], 0, 0, 0, 0, 0, False, 0
    while not r.eof():
        flags = r.u8()
        if flags == 0:
            if count >= hint:
                break
            continue
        change = None
        if flags & 0x40:
            v = (r.u8(), r.u8(), r.u8()) if flags & 0x80 else (r.u16(), r.u16(), r.u16())
            change = dict(v1=v[0], v2=v[1], v3=v[2])
            f0, f1, line = v[0] & 0x7FFF, v[1] & 0x7FFF, v[2] & 0x7FFF
            if schema == 5 and (v[0] & 0x7FFF > lines or f1 > fills or line > fills):  # trait, remplissages
                r.derailed = True
                return edges
        t1, t2, t3 = flags & 3, (flags >> 2) & 3, (flags >> 4) & 3
        (dx1, dy1), (dx2, dy2), (dx3, dy3) = (decoder.read_coord_delta(r, t) for t in (t1, t2, t3))
        if pad and t2 == 0:
            r.u8()  # bord droit : un octet de plus (toujours 0), pris par fla-decoder pour la fin de la liste
        fx, fy = x + dx1, y + dy1
        tx, ty = fx + dx3, fy + dy3
        cx, cy = ((fx + tx) // 2, (fy + ty) // 2) if t2 == 0 else (fx + dx2, fy + dy2)
        bad = bad or max(abs(fx), abs(fy), abs(tx), abs(ty), abs(cx), abs(cy)) > LIMIT
        count += 1
        if not bad:
            edges.append(dict(flags=flags, style_change=change, fill0=f0, fill1=f1, line_style=line, **{'from': (fx, fy)},
                              ctrl=(cx, cy), to=(tx, ty), kind='line' if t2 == 0 else 'curve', delta_types=(t1, t2, t3)))
        x, y = tx, ty
    return edges


FRAME_FIELDS = re.compile(rb'[\x18\x1a\x1d][\x00-\xff]{2}[\x00\x01][\x06\x26]\x00\x00', re.S)  # 1d : CS4
NEXT_OBJECT = re.compile(rb'\x00{5}\x80\x00{3}\x80|[\x01-\x3f]\x80\x05[\x00\x02]|\xff\xff\x01\x00[\x05-\x10]\x00CPic', re.S)


def after_cubics(buf, p, own):
    m = (FRAME_FIELDS if own else NEXT_OBJECT).search(buf, p)
    return m.start() if m else len(buf)


def read_fill(r, caps_flag):
    """dégradé des formes de schéma 5 (Flash 8 et après) : après le nombre d'arrêts, 8 octets (i32 point focal en
    1/256, puis 4 octets, nuls dans l'archive) et non 3 comme le lit fla-decoder ; arrêts : u8 position, u32 couleur"""
    p = r.pos
    color, sub, more = r.u32(), r.u8(), r.u8()
    if _data_schema[-1] < 5 or not sub & 0x10:
        r.pos = p
        return _read_fill(r, caps_flag)
    m, n = decoder.read_matrix_6(r), r.u8()
    focal = struct.unpack('<i', r.bytes(8)[:4])[0]
    stops = [dict(position=r.u8(), color_u32=r.u32()) for _ in range(n)]
    return dict(color_u32=color, subtype_flags=sub, more_flags=more, kind='gradient', matrix=m, num_stops=n,
                stops=stops, focal=focal)


def read_shape_data(r, caps_flag):
    schema, hint, n = r.u8(), r.u32(), r.u16()
    _data_schema.append(schema)
    try:
        return shape_body(r, caps_flag, schema, hint, n)
    finally:
        _data_schema.pop()


def shape_body(r, caps_flag, schema, hint, n):
    fills = [decoder.read_fill_style(r, caps_flag) if schema >= 3 else dict(kind='solid_old', color_u32=r.u32(),
             flags16=r.u16()) for _ in range(n)]
    lines = [decoder.read_line_style(r, caps_flag) for _ in range(r.u16())]
    r.derailed = False
    edges = read_edges(r, schema, hint, len(fills), len(lines), schema >= 5 and caps_flag) if schema >= 2 else []
    if r.derailed or (schema > 4 and r.remaining() >= 4 and r.s32()):
        r.pos = after_cubics(r.buf, r.pos, bool(_shape_stack and _shape_stack[-1]))
    return dict(shape_data_schema=schema, edge_hint=hint, fills=fills, lines=lines, byte_edges=edges, cubic_edges=[],
                reader_pos_after_edges=r.pos)


def read_shape(r, ar):  # la première forme lue par une image est sa forme propre, les autres sont ses enfants
    _shape_stack.append(_frame_pending.pop() if _frame_pending else False)
    try:
        return _read_shape(r, ar)
    finally:
        _shape_stack.pop()


def read_frame(r, ar):
    _frame_pending.append(True)
    out = _read_frame(r, ar)
    if (out.get('frame_schema') or 0) >= 26 and r.pos + 10 <= len(r.buf):  # CS3 (26) et CS4 (29)
        r.pos += 10
    return out


_read_frame = decoder.read_cpicframe
_read_fill, _data_schema = decoder.read_fill_style, [0]
_read_shape = decoder.read_cpicshape
_shape_stack, _frame_pending = [], []
_deserialize = decoder.deserialize_known
_read_symbol = read('CPicSymbol')


def deserialize(clsname, r, ar):
    if clsname == 'CPicSymbol':
        try:
            return {'class': clsname, **_read_symbol(r, ar)}
        except decoder.EOFReader as e:
            return {'class': clsname, 'eof_at_pos': r.pos, 'truncated': str(e)}
    return _deserialize(clsname, r, ar)


decoder.deserialize_known = deserialize
decoder.read_cpicsprite = read('CPicSprite')
decoder.read_cpicbutton = read('CPicButton')
decoder.read_cpicframe = read_frame
decoder.read_shape_data = read_shape_data
decoder.read_fill_style = read_fill
decoder.read_cpicshape = read_shape

import fla_archive  # noqa: E402,F401 (après les remplacements ci-dessus : il enrobe deserialize)
