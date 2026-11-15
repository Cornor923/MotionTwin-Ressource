# Méthode : comment le catalogue est construit

Ce document décrit tout ce qui a été fait et comment le refaire sur une autre machine : sources, outils, chaîne de
traitement, choix et formats, ajout d'un jeu, limites et dépannage.

## 1. But et règles

- Montrer **toutes** les ressources graphiques et sonores existantes de jeux Motion Twin, proprement, avec recherche,
  tri et organisation, pour s'en servir dans d'autres projets non commerciaux (Galaxy55 notamment).
- **Uniquement du matériel officiel Motion Twin**, tel que publié par Motion Twin. Pas de remake, pas de création de fans
  (eMush, EternalTwin…), pas d'éléments tiers même s'ils sont dans l'archive (voir §9).
- Les graphismes Flash sont extraits **avec la même méthode que les portages de jeux Flash de
  [kadokadeo](https://github.com/eternaltwin/kadokadeo)** (skill `flash-port`) : formes rastérisées par FFDec, composition
  des clips par `swfrender.py`. Rien n'est émulé : on dessine ce que contiennent les SWF.

## 2. Source et licence

- Archive : [motion-twin/WebGamesArchives](https://github.com/motion-twin/WebGamesArchives), publiée par Motion Twin
  (sources et données de leurs jeux web 2001-2015), licence **CC BY-NC-SA 4.0** (`LICENSE.txt` de l'archive).
- Commit utilisé : `8b8e2f202e1fa8cdf1d96e4140dad0cba458054e` (2023-11-02), épinglé dans `games.json`
  (`archive_commit`) : `rebuild.py` revient toujours à ce commit, même si l'archive bouge.
- Ce dépôt reprend la même licence (comme Galaxy55) ; `tools/flash/` reste sous AGPL-3.0 (repris de kadokadeo).
  Voir `NOTICE`.

## 3. Prérequis

| Outil | Pour | Version utilisée |
|---|---|---|
| Git | sparse checkout de l'archive | récente (sparse-checkout en mode cone) |
| Python | tous les scripts | 3.12 (3.11 minimum : option `-P`) |
| numpy, Pillow | rendus, décodage, catalogue (`requirements.txt`) | numpy 2.x, Pillow 10+ |
| JPEXS FFDec | exports des SWF | 26.2.0 (toute 26.x convient) |
| Java | lancer FFDec | JRE Temurin 21 |
| Navigateur récent | la page | Chrome / Edge / Firefox |

Afficher la page ne demande que Git et Python (`rebuild.py --fetch` n'importe ni numpy ni Pillow).

**FFDec et Java** (seulement pour reconstruire) : télécharger FFDec depuis
[jindrapetrik/jpexs-decompiler](https://github.com/jindrapetrik/jpexs-decompiler/releases) (`ffdec_26.x.zip`) et un JRE 21
(par exemple [Adoptium Temurin](https://adoptium.net/)), puis les ranger ainsi, à la racine du dépôt :

```
.tools/ffdec/ffdec.jar          (contenu du zip FFDec)
.tools/jre/<dossier du JRE>/bin/java(.exe)
```

`.tools/` est ignoré par git. Sinon : `FFDEC_TOOLS=<dossier contenant ffdec/ et jre/>`, ou `FFDEC_JAR=<chemin de
ffdec.jar>` avec `java` dans le PATH.

**Python** : `python -m venv .venv` puis `.venv/Scripts/pip install -r requirements.txt` (Windows) ou
`.venv/bin/pip …` (Linux, macOS), et lancer les scripts avec ce Python.

**Dossier de travail** : `MT_WORK` (défaut `~/motiontwin-assets-work`) reçoit les exports FFDec et les rendus bruts
(environ 60 Mo pour Mush + Alphabounce). Il peut être supprimé : tout se régénère.

## 4. Vue d'ensemble

```
games.json ──► rebuild.py
                 1. archive : git sparse checkout des dossiers des jeux au commit épinglé → sources/WebGamesArchives/
                 2. pour chaque SWF listé : FFDec → MT_WORK/<work>/ {shp4/ svg/ img/ snd/ src.swf}
                 3. render_symbols.py (swfrender) → MT_WORK/render/<work>/ {<id>.png, <id>_sheet.png, symbols.json}
                    (version de travail d'un SWF : swf_diff.py, seuls les clips différents sont rendus)
                 4. build_catalog.py → gen/ (fichiers dérivés) + catalog.js
index.html + viewer/*.js ◄── catalog.js, gen/, sources/ (images de l'archive référencées sur place)
```

## 5. Étape par étape

### 5.1 Archive

`git clone --filter=blob:none --depth 1 --sparse` puis `git sparse-checkout set Mush Alphabounce` (un dossier par jeu
de `games.json`). L'archive complète pèse environ 1,3 Go ; Mush + Alphabounce, environ 110 Mo de fichiers.

Ce qu'on y trouve (Mush / Alphabounce) :
- Mush : `www/img/**` (site : illustrations, cartes, icônes, habillage, teasing), `clients/iso/gfx/**` (planches du
  client isométrique, animations GraphicsGale `.gal` + leurs exports PNG), 3 SWF AS3 (`iso_deResources.swf` =
  `iso_testResources.swf`, `loading.swf`), des tableurs `.ods` (données, pas de graphismes).
- Alphabounce : `web/img/**` (site), `web/swf/*.swf` (jeu, inventaire, carte des planètes), `client/swf/gfx.swf` et
  `design/fla/inventaire/swf/*.swf` (versions de travail), `design/fla/design.swf` (maquette du site), des `.fla`.

### 5.2 Inventaire des SWF

`python tools/swf_inventory.py <fichiers.swf>` liste les balises utiles de chaque SWF : formes, clips (`DefineSprite`),
bitmaps, sons (`DefineSound`), polices, symboles exportés. C'est ce qui a montré :
- qu'il n'y a **aucun son** dans les SWF de Mush et d'Alphabounce (et aucun mp3/wav dans leurs dossiers) ;
- que les graphismes d'Alphabounce sont presque tous vectoriels (`game.swf` : 763 formes, 550 clips, 163 symboles exportés) ;
- que le SWF de ressources de Mush ne contient que 14 bitmaps (les planches du client) et un écran de chargement.

Doublons de SWF : comparer les empreintes (`md5sum`). `iso_deResources.swf` = `iso_testResources.swf` et
`web/swf/inv.swf` = `design/fla/inventaire/swf/client.swf` (champ `also` de `games.json`). Les versions de travail
`client/swf/gfx.swf` et `design/fla/inventaire/swf/gfx.swf` ont les mêmes formes et bitmaps mais quelques clips
différents (33 et 6) : champ `variant_of`, voir §5.4.

### 5.3 Exports FFDec

Pour chaque SWF (comme `prepare_game.sh` de kadokadeo), dans `MT_WORK/<work>/` :

```bash
java -jar ffdec.jar -onerror ignore -format shape:png -zoom 4 -export shape shp4 src.swf   # formes, lues par swfrender
java -jar ffdec.jar -onerror ignore -format shape:svg -export shape svg src.swf            # formes en SVG (catalogue)
java -jar ffdec.jar -onerror ignore -export image img src.swf                               # bitmaps
java -jar ffdec.jar -onerror ignore -format sound:mp3_wav -export sound snd src.swf         # sons
```

Les polices embarquées ne sont pas exportées (polices commerciales, pas des créations Motion Twin), ni les scripts.

### 5.4 Rendu des clips (`render_symbols.py`)

Chaque **symbole exporté** (nom de liaison Flash) qui est un clip est rendu avec `tools/flash/swfrender.py` :
- `SWF(src.swf, shp4/, Z=4)` : composition à partir des formes rastérisées par FFDec au zoom 4, réduite à **2 px par
  pixel Flash** (`Renderer(out_scale=2)`) ; options `flash_replace`, `blur_filters`, `inner_filters` activées (filtres
  Flash 8 dessinés : flou, lueur intérieure…).
- **Images montrées** : un clip de N > 1 images montre chacune de ses images (ses propres scripts sont ignorés, pour tout
  voir : variantes d'icônes, étapes d'animation), ses clips imbriqués jouent leur timeline et leurs scripts
  (stop / play / goto). Un clip d'une seule image montre autant d'images que sa plus longue timeline imbriquée
  (animations internes). Plafonds : 120 images (60 pour les animations imbriquées). Si toutes les images sont
  identiques, une seule est gardée.
- Sorties : `<id>.png` (première image), `<id>_sheet.png` (planche en grille à peu près carrée, 8192 px maximum),
  `symbols.json` (dimensions, nombre d'images, colonnes, cadence = celle de l'en-tête du SWF).
- Une forme de largeur ou hauteur nulle n'a pas de PNG chez FFDec : elle est remplacée par une image vide (sinon
  `mcBlock` et `mcEditorBrush` d'Alphabounce échouaient).
- Rendu partiel : `python tools/render_symbols.py <MT_WORK/work> <MT_WORK/render/work> 758,760` ne refait que ces
  identifiants et met `symbols.json` à jour.

**Versions de travail** (`variant_of`) : `swf_diff.py` compare les balises (scripts ignorés) et liste les symboles
exportés dont le clip ou un caractère affiché diffère ; seuls ceux-là sont rendus (avec les formes de la version
principale, identiques). Au catalogue, un rendu identique au pixel près à celui de la version principale devient un
doublon. Résultat pour Alphabounce : les 33 + 6 clips différents donnent des rendus identiques (seule la structure
interne change), donc aucune ressource en plus, mais les fiches indiquent ces copies.

### 5.5 Animations GraphicsGale (`gal.py`)

Mush garde ses animations de personnages au format GraphicsGale (`.gal`, en-tête `Gale106`). Le format a été lu
à la main et vérifié contre les exports PNG faits par Motion Twin :
- en-tête : entiers 32 bits petit-boutistes à l'octet 15 (largeur), 19 (hauteur), 23 (bits par pixel, seul 24 est
  géré), 27 (nombre d'images) ;
- image : `[u32 longueur][nom ASCII][u32 couleur transparente][u32 délai en ms]` (noms jusqu'à 66 caractères,
  `Copy_Copy_…_Frame1`) ;
- calque : `[u8 visible][u32 couleur transparente 0x00BBGGRR, 0xFFFFFFFF = aucune][u8 opacité][u32][u32 longueur][nom]
  [u32 taille][données zlib]`, pixels BGR ligne par ligne de haut en bas, lignes alignées sur 4 octets ;
- composition : calques visibles, couleur transparente du calque (ou de l'image), un calque uni sans transparence est
  un fond et n'est pas dessiné.

Le lecteur cherche ces enregistrements dans le fichier et vérifie le nombre d'images. Résultat : 50 fichiers sur 50
décodés ; 39 identiques au pixel près aux PNG de Motion Twin, les autres viennent d'une version un peu différente du
fichier (les deux sont montrés). Chaque animation garde ses délais, sa planche et un lien vers le `.gal` d'origine.

### 5.6 Catalogue (`build_catalog.py`, `swf_items.py`)

`gen/` est vidé puis reconstruit à chaque fois. Pour chaque jeu de `games.json` :
- **fichiers de l'archive** sous les dossiers `scan` (moins `exclude`) : images (png, jpg, gif, bmp, ico, webp),
  SVG, sons (mp3, wav, ogg) et `.gal` ; les images sont référencées sur place (`sources/…`), rien n'est copié ;
- **SWF** : clips rendus, formes SVG, bitmaps et sons exportés, copiés dans `gen/<jeu>/swf/<chemin du SWF>/`.

Types : `img` (image), `gif` (GIF animé), `anim` (GraphicsGale), `clip` (clip Flash rendu), `svg` (forme vectorielle),
`snd` (son).

Dédoublonnage :
- images : pixels décodés identiques (RGBA + taille) → une seule fiche, les autres chemins dans `dup` ;
- bitmaps de SWF : identiques à une image de l'archive de même taille à 1 près en alpha prémultiplié (Flash stocke
  l'alpha prémultiplié, FFDec le défait avec un autre arrondi) → doublon (12 des 13 bitmaps de Mush) ;
- formes SVG : fichier identique → dans le même SWF, numéros listés sous « Formes identiques » ; dans un autre SWF,
  doublon ;
- formes dégénérées (largeur ou hauteur nulle) et clips entièrement vides (repère AS3 `Sharepoint__` de Mush) ignorés ;
- miniature d'un clip : sa première image non vide.

Collections : le plus long préfixe de chemin trouvé dans `collections` de `games.json` (sinon le dossier). Les formes,
bitmaps et sons d'un SWF ont la collection du SWF suivie de « · formes vectorielles », « · bitmaps », « · sons ».

Mots-clés de recherche : nom entier et morceaux (`mcHeroRun` → `mcherorun`, `mc`, `hero`, `run`), étiquettes des
clips, et pour une forme les noms des clips exportés qui l'affichent (« Utilisée par »).

### 5.7 La page

`index.html` + `viewer/` : scripts classiques sans module ni dépendance (fonctionne aussi en `file://`), espace de noms
`MT`.

| Fichier | Rôle |
|---|---|
| `util.js` | types, création d'éléments, formats, attribution |
| `filters.js` | état des filtres, facettes avec compteurs, tris, adresse (`#…`) |
| `grid.js` | grille par paquets de 160 au défilement, en-têtes de collection, miniatures, animation au survol |
| `player.js` | lecture d'une planche dans un canvas (cadence du SWF ou délais du `.gal`) |
| `detail.js`, `detail-info.js` | fiche : zoom, lecture, clavier (← → ressource, espace, `,` `.` image), infos, téléchargements |
| `app.js` | barre latérale, barre d'outils, liens |

Miniatures : agrandissement entier en pixels nets pour les petites images matricielles, lissé pour le reste. Thèmes
clair et sombre selon le système ; mise en page mobile avec volet de filtres.

## 6. Ajouter un jeu

1. Repérer le dossier du jeu dans l'archive (`git -C sources/WebGamesArchives ls-tree -d --name-only HEAD`).
2. Ajouter une entrée dans `games.json` (voir §7) avec `scan` larges au départ, puis lancer `rebuild.py --fetch`.
3. Lister ce qu'il y a : types de fichiers par dossier, SWF (`tools/swf_inventory.py`), doublons de SWF (`md5sum`,
   `tools/swf_diff.py <principal> <autre>` pour une version de travail).
4. Regarder les images (planche contact, ou directement la page) et **exclure tout ce qui n'est pas de Motion Twin**
   (bibliothèques, logos de tiers, captures d'autres sites…). En cas de doute, demander.
5. Déclarer les SWF : `file`, `work` (nom du dossier de travail), `also` (copies identiques), `variant_of` (version
   de travail).
6. Nommer les collections (`collections`) et écrire les `notes` (ce qui manque, ce qui est exclu).
7. `python tools/rebuild.py`, relire les erreurs « clip non rendu », vérifier la page, puis versionner `games.json`,
   `catalog.js` et `gen/`.

Les SWF AS3 (Flash 9+) exposent leurs symboles par `SymbolClass` (balise 76), que `swfrender` ne lit pas encore :
leurs bitmaps, formes et sons sont extraits, mais leurs clips ne sont pas rendus (cas de `loading.swf` de Mush). Les
formes animées (`DefineMorphShape`) ne sont pas exportées en PNG par FFDec : un clip qui en contient est signalé « non
rendu » ; la solution de kadokadeo est de faire rendre ce clip image par image par FFDec
(`-format sprite:png -selectid <id> -export sprite`).

## 7. `games.json`

| Champ | Rôle |
|---|---|
| `archive`, `repo`, `archive_commit` | dossier local, dépôt et commit de l'archive |
| `license` | nom, adresse et texte d'attribution affichés |
| `games[].id`, `name`, `year`, `folder`, `summary`, `notes` | identité du jeu, dossier dans l'archive, textes de la page |
| `games[].scan` | dossiers parcourus (relatifs au dossier du jeu) |
| `games[].exclude` | motifs `fnmatch` exclus (éléments tiers) |
| `games[].swf[]` | `file`, `work`, et au besoin `also` (copies identiques) ou `variant_of` (autre version) |
| `games[].collections` | préfixe de chemin → nom de collection |

## 8. `catalog.js`

`window.MT_CATALOG = { generated, repo, commit, license, games[], items[] }`. Champs d'une ressource : `i` identifiant
(`<jeu>:<chemin>[#…]`), `g` jeu, `c` collection, `t` type, `n` nom, `s` image affichée, `p` chemin dans l'archive (`#id`,
`#shapeN`, `#bitmapN`, `#soundN` dans un SWF), `u` lien GitHub, `w` `h` taille (clips : pixels du rendu ×2), `f` nombre
d'images, `sh` planche, `cols` colonnes de la planche, `fps` cadence, `d` délais en ms (`.gal`), `fmt` format,
`z` poids, `k` mots-clés, `dup` autres emplacements, `o` fichier d'origine (`.gal`), `vec` vectoriel, `px` pixel art,
`x` infos SWF (`swf`, `id`, `timeline`, `labels`, `owners`, `same`).

## 9. Exclusions (ce qui n'est pas de Motion Twin)

- Mush : `www/img/jquery/*` (thème jQuery UI) ; dans `www/img/social/`, les logos de sites de presse (Gamalive,
  Game-Guide, Gameblog, Gamer News, GameSphere, Gaminfo, Gamingway, Indie Statik, JeuxCapt, JeuxOnline, jeuxvideo.com,
  IG Magazine, Canard PC, Massively, N-Gamz, Rock Paper Shotgun, RomStation, Selectbutton, USgamer). Gardés : l'image
  Facebook, la boîte et les captures du jeu.
- Alphabounce : `web/img/bank/cat_cb*` (bannières de paiement avec les logos PayPal, Visa et MasterCard).
- Partout : polices embarquées, `Thumbs.db`, tableurs de données.

## 10. Limites connues

- Pas de son pour Mush et Alphabounce (absent de l'archive).
- Les `.fla` d'Alphabounce (Flash 8, format binaire OLE) ne sont pas lus ; leur contenu est dans les SWF compilés.
- Les champs texte dynamiques (remplis par le code du jeu) restent vides dans les rendus ; les textes statiques sont là.
- Rendus à 2 px par pixel Flash : agrandir au-delà dans la fiche pixellise ; les formes, elles, sont en SVG.
- Clips AS3 non rendus et formes animées, voir §6.
- « Image courante (PNG) » ne marche pas en `file://` (sécurité du canvas) : passer par `tools/serve.py`.

## 11. Dépannage

| Symptôme | Cause et solution |
|---|---|
| La page affiche un ancien catalogue | cache du navigateur : `tools/serve.py` (sans cache) ou Ctrl+F5 |
| Images de l'archive manquantes (cases vides) | `sources/` absent ou incomplet : `python tools/rebuild.py --fetch` |
| `FFDec introuvable` | ranger FFDec dans `.tools/ffdec/` ou définir `FFDEC_TOOLS` / `FFDEC_JAR` (§3) |
| `ModuleNotFoundError: numpy` / `PIL` | `pip install -r requirements.txt` dans le Python utilisé |
| `clip non rendu … shp4/N.png` | forme absente des exports FFDec (forme animée) : voir §6 |
| Un clip est vide ou incomplet | regarder ses étiquettes et `ctrl` de `swfrender` ; certains clips n'existent qu'une fois remplis par le code |

## 12. Temps et volumes mesurés

| Étape | Durée mesurée lors de la première construction |
|---|---|
| `rebuild.py --fetch` (première fois) | quelques minutes selon la connexion |
| Exports FFDec des 6 SWF | quelques minutes |
| Rendu des clips de `game.swf` (163 symboles) | environ 35 minutes (`kit dev planet` 6 min, `mcTable` 3 min) |
| Rendu des 33 clips de la version de travail | environ 15 minutes |
| `build_catalog.py` | 30 à 50 secondes |

Volumes : `catalog.js` 1,2 Mo, `gen/` 32 Mo, dossier de travail 60 Mo, archive (2 jeux) environ 185 Mo avec git.

## 13. Historique

**2026-11-15** — première version :
1. Recherche de la source légale : l'archive `motion-twin/WebGamesArchives` (CC BY-NC-SA 4.0) contient Mush et
   Alphabounce ; sparse checkout de ces deux dossiers.
2. Inventaire des fichiers et des SWF (§5.2) : pas de son ; Alphabounce surtout vectoriel dans les SWF.
3. Extraction des SWF avec la méthode kadokadeo (FFDec + `swfrender`), sans nouvel outil ; rendu des 189 clips.
4. Décodeur GraphicsGale écrit et validé contre les exports PNG de Motion Twin.
5. Tri du matériel tiers (planches contact des dossiers suspects) et exclusions (§9).
6. Contrôle des versions de travail des SWF : rendus identiques, notés comme doublons.
7. Page de visualisation, testée sur bureau, mobile, thème sombre et en `file://`.
8. Chaîne rendue reproductible (`rebuild.py`, commit d'archive épinglé, `--fetch`) et documentée ; publication dans
   ce dépôt sous la licence de Galaxy55 (CC BY-NC-SA 4.0).
