"""Découpes des atlas TexturePacker (format Sparrow / Starling) livrés avec un jeu : le XML à côté de la planche donne
chaque image, `<SubTexture name x y width height [frameX frameY frameWidth frameHeight]>`. Le morceau est le
rectangle stocké (les marges ôtées par TexturePacker, `frame*`, ne sont pas rajoutées). Rockfaller.
"""
import os
from xml.etree import ElementTree


def texturepacker(game_dir, xml_path):
    root = ElementTree.parse(os.path.join(game_dir, xml_path)).getroot()
    out = []
    for sub in root.iter('SubTexture'):
        if sub.get('rotated') == 'true':
            raise ValueError('%s : image tournée dans l\'atlas, non gérée (%s)' % (xml_path, sub.get('name')))
        out.append(dict(name=sub.get('name'), rect=[int(float(sub.get(k))) for k in ('x', 'y', 'width', 'height')]))
    return out
