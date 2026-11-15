"""Chaîne complète pour les jeux de games.json : archive, exports FFDec, rendus des clips, catalogue.

usage : python tools/rebuild.py [--fetch] [--force]
  --fetch  récupère seulement l'archive Motion Twin (sparse checkout au commit épinglé) : suffit pour afficher la page,
           catalog.js et gen/ étant versionnés dans le dépôt ;
  --force  refait les exports FFDec et les rendus déjà présents dans MT_WORK.
Sans option :
- ajoute les dossiers des jeux au sparse checkout de l'archive (sources/WebGamesArchives, commit `archive_commit`) ;
- exporte chaque SWF avec FFDec (formes PNG zoom 4 et SVG, bitmaps, sons), comme prepare_game.sh de kadokadeo ;
- rend les clips exportés (render_symbols.py) ; une entrée `variant_of` ne rend que ses clips différents ;
- écrit catalog.js et gen/ (build_catalog.py).
env : MT_WORK (exports et rendus, défaut ~/motiontwin-assets-work),
      FFDEC_TOOLS (dossier avec ffdec/ffdec.jar et jre/*/bin/java, défaut .tools/ à la racine du dépôt, ignoré par git ;
      sans jre/, `java` du PATH), FFDEC_JAR (chemin direct de ffdec.jar)
Python 3.11+ avec numpy et Pillow (requirements.txt).
"""
import glob, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORK = os.environ.get('MT_WORK', os.path.join(os.path.expanduser('~'), 'motiontwin-assets-work'))
TOOLS = os.environ.get('FFDEC_TOOLS', os.path.join(ROOT, '.tools'))
FORCE = '--force' in sys.argv
PY = [sys.executable, '-E', '-P']  # sans le dossier courant dans sys.path ; garde les paquets utilisateur


def run(*cmd, **kw):
    print('  $', ' '.join(str(c) for c in cmd), flush=True)
    return subprocess.run([str(c) for c in cmd], check=True, **kw)


def java():
    found = glob.glob(os.path.join(TOOLS, 'jre', '*', 'bin', 'java.exe')) + \
        glob.glob(os.path.join(TOOLS, 'jre', '*', 'bin', 'java'))
    return found[0] if found else 'java'


def ffdec_jar():
    jar = os.environ.get('FFDEC_JAR') or os.path.join(TOOLS, 'ffdec', 'ffdec.jar')
    if not os.path.exists(jar):
        sys.exit('FFDec introuvable (%s) : définir FFDEC_TOOLS ou FFDEC_JAR, voir docs/METHODE.md' % jar)
    return jar


def archive(cfg):
    path = os.path.join(ROOT, cfg['archive'])
    commit = cfg.get('archive_commit')
    if not os.path.isdir(path):
        run('git', 'clone', '--filter=blob:none', '--depth', '1', '--sparse', cfg['repo'] + '.git', path)
    run('git', '-C', path, 'sparse-checkout', 'set', *[g['folder'] for g in cfg['games']])
    head = subprocess.run(['git', '-C', path, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    if commit and head != commit:  # l'archive a bougé depuis la construction du catalogue : revenir au commit épinglé
        run('git', '-C', path, 'fetch', '--depth', '1', '--filter=blob:none', 'origin', commit)
        run('git', '-C', path, 'checkout', '--detach', commit)
    return path


def ffdec_export(swf, work):
    os.makedirs(work, exist_ok=True)
    shutil.copy(swf, os.path.join(work, 'src.swf'))
    jar = ffdec_jar()
    jobs = [('shp4', ['-format', 'shape:png', '-zoom', '4', '-export', 'shape']),
            ('svg', ['-format', 'shape:svg', '-export', 'shape']),
            ('img', ['-export', 'image']),
            ('snd', ['-format', 'sound:mp3_wav', '-export', 'sound'])]
    for out, args in jobs:
        with open(os.path.join(work, 'ff_%s.log' % out), 'w') as log:
            run(java(), '-jar', jar, '-onerror', 'ignore', *args, out, 'src.swf', cwd=work, stdout=log,
                stderr=subprocess.STDOUT)


def prepare_swf(game_dir, entry, entries):
    swf = os.path.join(game_dir, entry['file'])
    work = os.path.join(WORK, entry['work'])
    render = os.path.join(WORK, 'render', entry['work'])
    if FORCE:
        shutil.rmtree(work, ignore_errors=True)
        shutil.rmtree(render, ignore_errors=True)
    if os.path.exists(os.path.join(render, 'symbols.json')):
        return
    print('==', entry['file'])
    if 'variant_of' in entry:
        primary = next(e for e in entries if e['file'] == entry['variant_of'])
        pwork = os.path.join(WORK, primary['work'])
        os.makedirs(work, exist_ok=True)
        shutil.copy(swf, os.path.join(work, 'src.swf'))
        for sub in ('shp4', 'svg'):  # mêmes formes que la version principale
            if not os.path.isdir(os.path.join(work, sub)):
                shutil.copytree(os.path.join(pwork, sub), os.path.join(work, sub))
        ids = subprocess.run(PY + [os.path.join(HERE, 'swf_diff.py'), os.path.join(pwork, 'src.swf'), swf],
                             check=True, capture_output=True, text=True).stdout.strip()
        if ids:
            run(*PY, os.path.join(HERE, 'render_symbols.py'), work, render, ids)
        else:
            os.makedirs(render, exist_ok=True)
            json.dump(dict(fps=0, symbols=[], errors=[]), open(os.path.join(render, 'symbols.json'), 'w'))
        return
    if not os.path.isdir(os.path.join(work, 'shp4')):
        ffdec_export(swf, work)
    run(*PY, os.path.join(HERE, 'render_symbols.py'), work, render)


def main():
    if sys.version_info < (3, 11):
        sys.exit('Python 3.11 ou plus requis')
    cfg = json.load(open(os.path.join(ROOT, 'games.json'), encoding='utf-8'))
    path = archive(cfg)
    if '--fetch' in sys.argv:
        return
    for game in cfg['games']:
        for entry in game.get('swf', []):
            prepare_swf(os.path.join(path, game['folder']), entry, game['swf'])
    run(*PY, os.path.join(HERE, 'build_catalog.py'))


if __name__ == '__main__':
    main()
