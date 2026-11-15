"""Bitmaps des .fla (flux « M n » des .fla binaires, fichiers bin/*.dat des XFL) : même format dans les deux cas.

`03 05` : sans perte 32 bits — u16 octets par ligne, u16 largeur, u16 hauteur, 4 × i32 cadre (twips), u8 alpha,
u8 compressé, puis blocs [u16 longueur][données] jusqu'à une longueur nulle ; zlib ; pixels A R G B prémultipliés.
`03 03` : 8 bits à palette — même en-tête, u8, u16 nombre de couleurs, palette A R G B, u8 compressé, blocs zlib.
JPEG brut sinon (FF D8). Vérifié au pixel près contre les mêmes bitmaps exportés des SWF par FFDec.
"""
import io, struct, zlib
import numpy as np
from PIL import Image


def chunks(b, pos):
    out = []
    while pos + 2 <= len(b):
        n = struct.unpack_from('<H', b, pos)[0]
        pos += 2
        if n == 0:
            break
        out.append(b[pos:pos + n])
        pos += n
    return b''.join(out)


def unpremultiply(argb):
    a = argb[..., 0:1].astype(np.int32)
    rgb = argb[..., 1:4].astype(np.int32)
    rgb = np.where(a > 0, np.minimum(255, rgb * 255 // np.maximum(a, 1)), 0)
    return Image.fromarray(np.concatenate([rgb, a], -1).astype(np.uint8), 'RGBA')


def decode(b):
    """octets d'un bitmap de .fla -> image RGBA, ou None si le format n'est pas reconnu"""
    try:
        if b[:2] == b'\xff\xd8':
            return Image.open(io.BytesIO(b)).convert('RGBA')
        if b[:2] not in (b'\x03\x05', b'\x03\x03'):
            return None
        rb, w, h = struct.unpack_from('<3H', b, 2)
        if b[1] == 5:
            raw = zlib.decompress(chunks(b, 26)) if b[25] else b[26:]
            px = np.frombuffer(raw[:rb * h], np.uint8).reshape(h, rb)[:, :w * 4].reshape(h, w, 4)
            return unpremultiply(px)
        ncol = struct.unpack_from('<H', b, 25)[0]
        pal = np.frombuffer(b[27:27 + 4 * ncol], np.uint8).reshape(ncol, 4)
        start = 27 + 4 * ncol
        data = zlib.decompress(chunks(b, start + 1)) if b[start] else b[start + 1:]
        idx = np.frombuffer(data[:rb * h], np.uint8).reshape(h, rb)[:, :w]
        return unpremultiply(pal[np.minimum(idx, ncol - 1)])
    except Exception:
        return None
