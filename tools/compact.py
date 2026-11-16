"""Planches d'animation en WebP sans perte quand il est plus léger que le PNG.

Aucun pixel ne change : le WebP est relu et comparé au PNG (RGBA, couleurs sous les pixels transparents comprises,
`exact`), sinon le PNG reste. Le WebP sans perte gagne environ 45 % sur les grands décors d'Odyssey ; sur quelques
planches il est plus lourd, le PNG est alors gardé. L'encodage (méthode 6, la plus serrée) est lent : le résultat est
mis en cache dans MT_WORK/webp/<sha1 du PNG>, et une reconstruction du catalogue ne réencode que les planches neuves.
"""
import hashlib, io, os, shutil

import numpy as np
from PIL import Image


def sheet(src, dst_base, work):
    """copie la planche PNG `src` en `dst_base`.webp ou `dst_base`.png (le plus léger) ; renvoie le chemin écrit"""
    data = open(src, 'rb').read()
    cache = os.path.join(work, 'webp')
    key = os.path.join(cache, hashlib.sha1(data).hexdigest())
    if not os.path.exists(key + '.webp') and not os.path.exists(key + '.png'):
        os.makedirs(cache, exist_ok=True)
        webp = encode(data)
        if webp is not None and len(webp) < len(data):
            tmp = '%s.%d.tmp' % (key, os.getpid())
            open(tmp, 'wb').write(webp)
            try:
                os.replace(tmp, key + '.webp')
            except PermissionError:  # la même planche vient d'être écrite par un autre processus
                os.remove(tmp)
        else:
            open(key + '.png', 'wb').close()  # marque « PNG plus léger » (fichier vide)
    dst = dst_base + ('.webp' if os.path.exists(key + '.webp') else '.png')
    if os.path.abspath(dst) != os.path.abspath(src):
        shutil.copy(key + '.webp' if dst.endswith('.webp') else src, dst)
    return dst


def encode(data):
    im = Image.open(io.BytesIO(data)).convert('RGBA')
    if max(im.size) > 16383:  # limite du format WebP
        return None
    out = io.BytesIO()
    im.save(out, 'WEBP', lossless=True, quality=100, method=6, exact=True)
    back = Image.open(io.BytesIO(out.getvalue())).convert('RGBA')
    return out.getvalue() if np.array_equal(np.asarray(back), np.asarray(im)) else None
