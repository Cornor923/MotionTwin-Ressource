"""Symboles exportés d'un SWF dont le dessin diffère d'un autre SWF (même bibliothèque, autre version).

usage : python swf_diff.py <principal.swf> <autre.swf>   -> imprime les id séparés par des virgules
        python swf_diff.py --shapes <principal.swf> <autre.swf>   -> formes de même numéro dessinées autrement
Un symbole diffère si lui-même ou un caractère qu'il affiche (récursivement) a un tag différent (scripts ignorés).
"""
import hashlib, os, struct, sys, zlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flash'))
import swfdump as S

CHARS = (2, 22, 32, 83, 39, 20, 21, 35, 36, 46, 84, 37, 11, 33, 48, 75, 10, 34, 7, 6)
SHAPES = (2, 22, 32, 83, 46, 84)  # DefineShape 1 à 4, DefineMorphShape 1 et 2


def characters(path):
    raw = open(path, 'rb').read()
    data = raw[:8] + (zlib.decompress(raw[8:]) if raw[:3] == b'CWS' else raw[8:])
    b = S.Bits(data, 8)
    b.rect(); b.u16(); b.u16()
    chars, children, exports = {}, {}, {}
    for code, body in S.read_tags(data, b.pos, len(data)):
        if code in CHARS:
            cid = struct.unpack_from('<H', body, 0)[0]
            kids = set()
            if code == 39:
                sub = [(c, bb) for c, bb in S.read_tags(body, 4, len(body)) if c != 12]
                body = body[:4] + b''.join(bytes([c]) + bb for c, bb in sub)
                for c, bb in sub:
                    if c in (4, 26, 70):
                        p = S.parse_place(c, bb)
                        if 'char' in p:
                            kids.add(p['char'])
            chars[cid] = ('S' if code in SHAPES else '') + hashlib.sha1(body).hexdigest()
            children[cid] = kids
        elif code == 56:
            bb = S.Bits(body)
            for _ in range(bb.u16()):
                cid = bb.u16()
                exports[cid] = bb.string()
    return chars, children, exports


def differing(primary, other):
    a, _, _ = characters(primary)
    b, kids, exports = characters(other)
    memo = {}

    def differs(cid, stack=()):
        if cid not in memo:
            memo[cid] = a.get(cid) != b.get(cid) or any(
                differs(k, stack + (cid,)) for k in kids.get(cid, ()) if k not in stack)
        return memo[cid]
    return sorted(cid for cid in exports if differs(cid))


def shapes_differing(primary, other):
    """formes de l'autre version absentes ou différentes dans la principale : ses exports FFDec ne peuvent pas servir"""
    a, _, _ = characters(primary)
    b, _, _ = characters(other)
    return sorted(cid for cid, h in b.items() if h[0] == 'S' and a.get(cid) != h)


if __name__ == '__main__':
    if sys.argv[1] == '--shapes':
        print(','.join(str(c) for c in shapes_differing(sys.argv[2], sys.argv[3])))
    else:
        print(','.join(str(c) for c in differing(sys.argv[1], sys.argv[2])))
