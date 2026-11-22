"""Numérotation des objets MFC et lecture des calques des .fla binaires (corrections de fla-decoder, à l'import).

Numéros : dans une archive MFC (CArchive), chaque classe nouvelle et chaque objet créé prennent un numéro, dans
l'ordre de lecture (l'objet avant ses enfants). Un renvoi « n | 0x8000 » crée un objet de la classe n, un renvoi
« n » sans ce bit désigne l'objet n déjà lu (0x7FFF : numéro sur 32 bits à la suite). fla-decoder ne comptait que
les classes (deux numéros par classe) : un renvoi vers une classe déclarée après des objets créés par renvoi
tombait hors de sa table et la lecture de la page s'arrêtait là (calques suivants perdus).

Calques (CPicLayer, schéma 11 dans l'archive) : u8 schéma, nom, u8, u8 verrouillé, u8 visible, couleur, 3 × u32,
puis u8 type de calque (0 normal, 1 guide, 4 masque : relevé sur l'archive, voir `KINDS`), un objet parent
(ReadObject : aucun, renvoi vers un calque déjà lu, ou calque parent sérialisé là s'il n'a pas encore été lu :
un masque est écrit dans le premier calque qu'il masque), puis des u8 selon le schéma. Un calque masqué ou guidé
a pour parent son masque ou son guide ; le premier u8 après le nom n'est pas le type (fla-decoder le croyait).
"""
from fla_decoder import decoder

KINDS = {0: 'normal', 1: 'guide', 3: 'dossier', 4: 'masque'}


def read_class_tag(self):
    if not hasattr(self, 'mfc'):
        self.mfc, self.new = [None], None
    r = self.r
    tag = r.u16()
    if tag == 0:
        return ('null', {})
    if tag == 0xFFFF:
        schema, n = r.u16(), r.u16()
        name = r.bytes(n).decode('ascii', 'replace')
        self.register_class(name, schema)
        self.mfc.append(('class', name))
        return created(self, name, 'new_class', {'name': name, 'schema': schema, 'idx': len(self.classes)})
    if tag == 0x7FFF:
        big = r.u32()
        is_class, idx = bool(big & 0x80000000), big & 0x7FFFFFFF
    else:
        is_class, idx = bool(tag & 0x8000), tag & 0x7FFF
    entry = self.mfc[idx] if 0 < idx < len(self.mfc) else None
    if not is_class:
        return ('object', {'idx': idx})
    if not entry or entry[0] != 'class':
        return ('backref', {'idx': idx})
    return created(self, entry[1], 'backref', {'idx': idx, 'name': entry[1]})


def created(ar, name, kind, info):
    ar.mfc.append(('object', name))
    ar.new = len(ar.mfc) - 1
    return (kind, info)


def deserialize(clsname, r, ar):
    idx, ar.new = getattr(ar, 'new', None), None
    out = _deserialize(clsname, r, ar)
    if idx is not None and isinstance(out, dict):
        out['_mfc'] = idx
    return out


def read_object(r, ar):
    """(numéro, objet lu ici ou None) d'un ReadObject"""
    tag = ar.read_class_tag()
    if tag[0] == 'object':
        return tag[1]['idx'], None
    if tag[0] in ('new_class', 'backref') and tag[1].get('name'):
        obj = decoder.deserialize_known(tag[1]['name'], r, ar)
        return obj.get('_mfc'), obj
    return None, None


def read_layer(r, ar):
    out = decoder.read_cpicobj_fields(r, ar)
    ls = out['layer_schema'] = r.u8()
    out['layer_name'] = decoder._read_flash_cstring(r)
    if ls <= 3:
        out['layer_field_type'] = r.u8()
    if 4 <= ls <= 30:
        out['layer_field_0'], out['layer_locked'], out['layer_visible'] = r.u8(), r.u8(), r.u8()
    if 5 <= ls <= 30:
        out['layer_color'] = r.u32()
    if 6 <= ls <= 30:
        out['layer_field_8c'], out['layer_field_90'] = r.u32(), r.u32()
    if 8 <= ls <= 30:
        out['layer_field_98'] = r.u32()
    out['layer_kind'] = KINDS.get(r.u8(), 'normal')
    out['parent_idx'], out['parent_obj'] = read_object(r, ar)
    if 7 <= ls < 9:
        read_object(r, ar)
    for lo, hi in ((2, 6), (3, 9), (9, 99), (10, 99), (12, 99)):  # 12 et après (CS4 : 13) : un u8 de plus
        if lo <= ls < hi:
            r.u8()
    return out


def read_bitmap(r, ar):
    """bitmap posé (CPicBitmap) : u8 schéma, matrice (a b c d en 16.16, tx ty en twips), u16 numéro du flux « M n »
    de l'image, u8 (schéma 2 et après, nul dans l'archive). fla-decoder sautait ensuite au premier marqueur de fin
    venu, ce qui perdait la suite de l'image (autres éléments du calque)."""
    out = decoder.read_cpicobj_fields(r, ar)
    schema = out['bitmap_schema'] = r.u8()
    out['bitmap_matrix'] = decoder.read_matrix_6(r)
    out['bitmap_media_id'] = r.u16()
    if schema >= 2:
        out['bitmap_filter_flag'] = r.u8()
    return out


_deserialize = decoder.deserialize_known
decoder.ArchiveReader.read_class_tag = read_class_tag
decoder.deserialize_known = deserialize
decoder.read_cpiclayer = read_layer
decoder.read_cpicbitmap = read_bitmap
