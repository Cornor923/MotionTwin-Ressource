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
- SWF AS3 : symboles dans `SymbolClass`, non lus par `swfrender` : `tools/swf_symbols.py` les ajoute aux exports
  (rendu et catalogue). Les scripts lancés avec `-P` doivent ajouter `tools/` à `sys.path` eux-mêmes.
- Bitmaps Flash = alpha prémultiplié : comparer avec une tolérance de 1 (fait par `build_catalog.py`).
- Le navigateur garde `catalog.js` en cache : tester avec `tools/serve.py`.
- Lancer Python sans `-I` quand Pillow est dans les paquets utilisateur : `rebuild.py` utilise `-E -P`.
- Ne jamais rien ajouter ni modifier dans une ressource : une planche se découpe (`sheets` de games.json, pixels
  d'origine seulement), on ne retouche pas ses pixels. Les repères de travail de Motion Twin seuls sur du transparent
  ne sont pas des ressources ; un repère posé sur un dessin reste (voir docs/METHODE.md §5.7).
- `git grep` ou `ls-tree -l` sur un dossier de l'archive hors sparse checkout télécharge ses blobs (plusieurs minutes) :
  ajouter le dossier au sparse checkout d'abord.
- Modèles `.bae` : COLLADA binaire décodé à la main dans `models.py` (aucun lecteur dans l'archive).
- Planches d'animation en WebP sans perte (`compact.py`, cache `MT_WORK/webp/`) : après de nouveaux rendus, la
  première reconstruction encode les planches neuves (méthode 6, lente sur les grands décors).
- `variant_of` : si la version de travail redessine des formes (`swf_diff.py --shapes`), `rebuild.py` lui fait ses
  propres exports FFDec (sinon les formes de la version principale seraient prises par erreur).
- Plateformes (CaféJeux, KadoKado) : un seul jeu dans games.json, ses jeux dans `parts` (chemins), `fetch` pour ne
  récupérer qu'une partie du dossier (KadoKado : `Games/Alphabounce` ; ajouter les autres jeux là quand on les intègre).
- Atlas TexturePacker (Rockfaller) : `slices_from: ["texturepacker", "x.xml"]` + `bleed: 2` (bords répétés par
  l'empaqueteur, ignorés).
- Banques d'images CastleDB (`.img`, Monster Hotel) : `cdb_images` de games.json, `cdb_images.py` (noms tirés du
  `.cdb`). Un atlas au fond opaque (rooms0 de Monster Hotel) prend `background`.
- `.xcf` (GIMP 2.8 et avant) : `xcf.py`, image composée + un calque par fiche ; XCF 2.10+ (version > 2) refusé.
- Planche sans découpe dans le code : `gap` (écart de regroupement) et `groups` (rectangles = un morceau) règlent
  les morceaux ; `marks` peut lister des rectangles qui ne contiennent que des repères (Teacher Story).
- Découpes lues dans le code d'un jeu : `slices_from` de games.json -> registre `SLICES` de `sheets.py` (Mush :
  `mush.py`, tiles.xml et Data.hx/Data.ods ; Galaxy55 : `galaxy55.py`).
- `.fla` : XFL lus par `xfl.py` ; binaires par `tools/fla_decoder/` (MIT, ne pas modifier) corrigé à l'import par
  `fla_patch.py` (formes, instances), `fla_archive.py` (numéros MFC, calques, bitmaps posés) et `fla_filters.py`
  (filtres) ; dans les deux cas symboles composés (`fla_compose.py`), animés image par image (`fla_timeline.py`,
  planche SVG `_planche.svg`). Une correction se vérifie contre un SWF compilé depuis le même `.fla` (FFDec
  `-swf2xml` : filtres, modes de fusion, matrices de chaque image des `DefineSprite`). Ne jamais lancer
  `build_catalog.py` derrière `| grep | head` : il vide `gen/` d'abord.
