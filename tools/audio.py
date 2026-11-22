"""Durée des sons (secondes), lue dans les en-têtes, sans dépendance :
- WAV : taille du bloc `data` / octets par seconde du bloc `fmt ` (tout codage, PCM ou non) ;
- MP3 : somme des trames MPEG 1, 2 et 2.5 (couches I à III, débit fixe ou variable), balises ID3 ignorées ;
- OGG : position (granule) de la dernière page / fréquence de l'en-tête Vorbis (48 kHz pour Opus).
"""
import os
import struct

RATES = {3: (44100, 48000, 32000), 2: (22050, 24000, 16000), 0: (11025, 12000, 8000)}  # MPEG 1, 2, 2.5
KBPS = {(3, 3): (0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448),
        (3, 2): (0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384),
        (3, 1): (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320),
        (2, 3): (0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256),
        (2, 2): (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160)}


def measure(item, root):
    if item.get('t') == 'snd':
        try:
            seconds = duration(os.path.join(root, item['s']))
        except (OSError, ValueError, struct.error):
            seconds = None
        if seconds:
            item['dur'] = round(seconds, 2)


def duration(path):
    data = open(path, 'rb').read()
    ext = os.path.splitext(path)[1].lower()
    return wav(data) if ext == '.wav' else mp3(data) if ext == '.mp3' else ogg(data) if ext == '.ogg' else None


def wav(data):
    pos, rate, size = 12, None, None
    while pos + 8 <= len(data):
        tag, n = data[pos:pos + 4], struct.unpack_from('<I', data, pos + 4)[0]
        if tag == b'fmt ':
            rate = struct.unpack_from('<I', data, pos + 16)[0]  # octets par seconde
        elif tag == b'data':
            size = min(n, len(data) - pos - 8)
        pos += 8 + n + (n & 1)
    return size / rate if rate and size else None


def frame(data, pos):
    """(échantillons, longueur en octets) de la trame MPEG qui commence en `pos`, ou None"""
    b1, b2, b3 = data[pos + 1], data[pos + 2], data[pos + 3]
    if data[pos] != 0xFF or b1 & 0xE0 != 0xE0:
        return None
    version, layer, rate_i, br_i = (b1 >> 3) & 3, (b1 >> 1) & 3, (b2 >> 2) & 3, b2 >> 4
    if version == 1 or layer == 0 or rate_i == 3 or br_i in (0, 15):
        return None
    rate = RATES[version][rate_i]
    kbps = KBPS[(3, layer)] if version == 3 else KBPS[(2, 3 if layer == 3 else 2)]
    bitrate, pad = kbps[br_i] * 1000, (b2 >> 1) & 1
    if layer == 3:  # couche I
        return 384, (12 * bitrate // rate + pad) * 4
    samples = 1152 if layer == 2 or version == 3 else 576
    return samples, samples // 8 * bitrate // rate + pad


def mp3(data):
    pos = 0
    if data[:3] == b'ID3':  # balise ID3v2 : taille en entier « synchsafe »
        size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
        pos = 10 + size + (10 if data[5] & 0x10 else 0)
    samples, rate, first = 0, None, True
    while pos + 4 <= len(data):
        f = frame(data, pos)
        if f is None or f[1] <= 0:
            pos += 1
            continue
        if first and (b'Xing' in data[pos:pos + 64] or b'Info' in data[pos:pos + 64]):
            first = False  # trame d'en-tête VBR : pas de son
            pos += f[1]
            continue
        first = False
        rate = rate or RATES[(data[pos + 1] >> 3) & 3][(data[pos + 2] >> 2) & 3]
        samples += f[0]
        pos += f[1]
    return samples / rate if rate else None


def ogg(data):
    head = data[:512]
    if b'OpusHead' in head:
        i = head.index(b'OpusHead')
        rate, skip = 48000, struct.unpack_from('<H', head, i + 10)[0]
    elif b'\x01vorbis' in head:
        rate, skip = struct.unpack_from('<I', head, head.index(b'\x01vorbis') + 12)[0], 0
    else:
        return None
    last = data.rfind(b'OggS')
    granule = struct.unpack_from('<q', data, last + 6)[0]
    return (granule - skip) / rate if rate and granule > 0 else None
