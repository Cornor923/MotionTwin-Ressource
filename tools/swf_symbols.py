"""Symboles AS3 d'un SWF : balise SymbolClass (76), que swfrender ne lit pas (il ne lit que ExportAssets).

Ajoutés aux exports d'un `swfrender.SWF` pour que les clips des SWF AS3 soient rendus et nommés comme les autres.
L'identifiant 0 (classe du document) n'est pas un symbole.
"""
import struct, zlib


def symbol_classes(path):
    raw = open(path, 'rb').read()
    data = zlib.decompress(raw[8:]) if raw[:3] == b'CWS' else raw[8:]
    pos = (5 + 4 * (data[0] >> 3) + 7) // 8 + 4
    out = {}
    while pos + 2 <= len(data):
        code_len = struct.unpack_from('<H', data, pos)[0]
        pos += 2
        code, size = code_len >> 6, code_len & 0x3f
        if size == 0x3f:
            size = struct.unpack_from('<I', data, pos)[0]
            pos += 4
        if code == 76:
            p = pos + 2
            for _ in range(struct.unpack_from('<H', data, pos)[0]):
                cid = struct.unpack_from('<H', data, p)[0]
                end = data.index(b'\0', p + 2)
                if cid:
                    out[cid] = data[p + 2:end].decode('utf-8', 'replace')
                p = end + 1
        if code == 0:
            break
        pos += size
    return out


def add_symbol_classes(swf, path):
    for cid, name in symbol_classes(path).items():
        if cid not in swf.exports:
            swf.exports[cid] = name
            swf.names[name] = cid
