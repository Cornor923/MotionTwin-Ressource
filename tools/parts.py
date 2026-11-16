"""Sous-jeux d'une plateforme (CaféJeux, KadoKado) : `parts` dans games.json.

  "parts": [{"id": "anticorps", "name": "Anticorp's", "path": "games/anticorps"}, …]
  "root_part": "Le café"     nom des ressources de la plateforme hors de tout sous-jeu (facultatif)

Chaque ressource reçoit `sg` = id du sous-jeu dont le chemin est le plus long préfixe de son chemin dans l'archive, et
`sgx` = les autres sous-jeux où elle a une copie (`dup`, « - » = hors sous-jeu) : Bandas et Marbils partagent leurs
dessins, chacun les montre. La page range les sous-jeux sous la ligne de leur plateforme.
"""


def part_of(parts, path):
    path, best = path.split('#')[0], None
    for part in parts:
        if (path == part['path'] or path.startswith(part['path'] + '/')) and (
                best is None or len(part['path']) > len(best['path'])):
            best = part
    return best['id'] if best else '-'


def assign(cfg, items):
    parts = cfg.get('parts', [])
    if not parts:
        return
    for item in items:
        main = part_of(parts, item['p'])
        if main != '-':
            item['sg'] = main
        other = sorted({part_of(parts, d) for d in item.get('dup', [])} - {main})
        if other:
            item['sgx'] = other


def summary(cfg, items):
    """liste des sous-jeux pour catalog.js (ordre de games.json, nombre de ressources)"""
    if not cfg.get('parts'):
        return {}
    counts = {}
    for item in items:
        for key in [item.get('sg', '-')] + item.get('sgx', []):
            counts[key] = counts.get(key, 0) + 1
    out = dict(parts=[dict(id=p['id'], name=p['name'], count=counts.get(p['id'], 0)) for p in cfg['parts']])
    if cfg.get('root_part'):
        out['root'] = dict(name=cfg['root_part'], count=counts.get('-', 0))
    return out
