# Notes pour les sessions d'agent

Catalogue web des ressources graphiques et sonores **officielles** de jeux Motion Twin (archive
`motion-twin/WebGamesArchives`, CC BY-NC-SA 4.0). Lire `README.md` puis `docs/METHODE.md` avant de toucher à la chaîne.

## Règles

- Seulement du matériel publié par Motion Twin. Jamais de remake ni de création de fans ; exclure les éléments tiers
  de l'archive (bibliothèques, logos d'autres sociétés). En cas de doute sur un fichier, le montrer et demander.
- Extraction des SWF : méthode kadokadeo (FFDec + `tools/flash/swfrender.py`). Ne pas émuler Flash ni installer d'autre
  outil sans le demander.
- Rien de privé ni de propre à une machine dans le dépôt : pas de chemin absolu, de nom d'utilisateur, d'adresse mail,
  de nom de PC. Les outils locaux vont dans `.tools/` (ignoré) ou passent par `FFDEC_TOOLS` / `FFDEC_JAR` / `MT_WORK`.
  Vérifier avant chaque commit : `git grep -n -i -E 'c:[/\\]users|/home/|/users/|noreply|@[a-z0-9.-]+\.[a-z]{2,}'`
  puis relire les résultats.
- Licence : CC BY-NC-SA 4.0 pour le dépôt (`LICENSE`, `NOTICE`) ; `tools/flash/` reste AGPL-3.0, ne pas le modifier
  (adapter depuis les scripts de `tools/`, comme `render_symbols.py` le fait pour les formes de largeur nulle).
- Documentation, messages de commit et commentaires en français ; commits au format `<emoji> (<portée>) message`
  (`✨` fonctionnalité, `🐛` correction, `🍱` ressources, `📝` docs, `🔧` config). Jamais de mention d'IA ni de
  `Co-Authored-By` dans un commit.

## Commandes

```bash
python tools/rebuild.py --fetch     # archive seule : suffit pour afficher la page
python tools/serve.py               # http://127.0.0.1:8642/ sans cache
python tools/rebuild.py             # chaîne complète (numpy + Pillow, FFDec + Java), ~45 min la première fois
python tools/build_catalog.py       # catalogue seul, si les exports et rendus de MT_WORK existent
python tools/render_symbols.py <MT_WORK/x> <MT_WORK/render/x> id,id   # refaire quelques clips
python tools/swf_inventory.py <f.swf>   # que contient un SWF (sons, bitmaps, symboles exportés)
python tools/swf_diff.py <principal.swf> <autre.swf>   # clips différents entre deux versions
```

Après une reconstruction, versionner `catalog.js` et `gen/` avec `games.json` (la page doit marcher après
`--fetch` seul).

## Pièges connus

- `game.swf` d'Alphabounce : environ 35 min de rendu ; lancer `rebuild.py` en arrière-plan.
- FFDec n'écrit pas de PNG pour une forme de largeur nulle ni pour une forme animée (morph) : la première est gérée,
  la seconde donne « clip non rendu ».
- SWF AS3 : symboles dans `SymbolClass`, non lus par `swfrender` ; seuls bitmaps, formes et sons sont extraits.
- Bitmaps Flash = alpha prémultiplié : comparer avec une tolérance de 1 (fait par `build_catalog.py`).
- Le navigateur garde `catalog.js` en cache : tester avec `tools/serve.py`.
- Lancer Python sans `-I` quand Pillow est dans les paquets utilisateur : `rebuild.py` utilise `-E -P`.
