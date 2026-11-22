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
                    (avec sheets.py : planches découpées ; models.py + render3d.py : modèles 3D)
index.html + viewer/*.js ◄── catalog.js, gen/, sources/ (images de l'archive référencées sur place)
```

## 5. Étape par étape

### 5.1 Archive

`git clone --filter=blob:none --depth 1 --sparse` puis `git sparse-checkout set Mush Alphabounce Galaxy55 Muxxu/Kube Muxxu/Kingdom …` (un dossier par
jeu de `games.json`). L'archive complète pèse environ 1,3 Go ; Mush + Alphabounce, environ 110 Mo de fichiers ; Galaxy55,
environ 3 Mo ; les sept jeux Muxxu, environ 190 Mo (dont 94 Mo de `.fla` pour La Brute).

Ce qu'on y trouve :
- Mush : `www/img/**` (site : illustrations, cartes, icônes, habillage, teasing), `clients/iso/gfx/**` (planches du
  client isométrique, animations GraphicsGale `.gal` + leurs exports PNG), 3 SWF AS3 (`iso_deResources.swf` =
  `iso_testResources.swf`, `loading.swf`), des tableurs `.ods` (données, pas de graphismes).
- Alphabounce : `web/img/**` (site), `web/swf/*.swf` (jeu, inventaire, carte des planètes), `client/swf/gfx.swf` et
  `design/fla/inventaire/swf/*.swf` (versions de travail), `design/fla/design.swf` (maquette du site), des `.fla`.
- Galaxy55 (alpha, client 3D Flash compilé absent de l'archive) : `fla/client/gfx/*.png` (atlas des blocs `texture.png`,
  HUD, icônes, rayons laser, halo du vaisseau, particules), `fla/client/sfx/*.wav` (12 bruitages) et leurs `.lch`,
  `fla/explore/gfx/tiles.png` (carte de l'espace), 5 SWF, des modèles 3D (`.bae`, `door.md`), des sources Haxe et un
  tableur `com/data.ods` (définition des blocs). Seule l'archive compte : les blocs et textures ajoutés depuis par les
  portages du jeu (galaxy55-offline…) n'y sont pas et ne sont pas montrés.
- Kube (Muxxu) : `client/bmp/*.png` (une image par face de bloc), `client/game_gfx` (interface), `www/img/**` (site),
  `client/gfx.swf` AS3 (= `client2/gfx.swf`, textures des blocs nommées `BNoel`, `u.BNoel`, `d.BNoel`…, et interface),
  `client2/blocks.ods` (données), `gfx/events/*.jpg` (captures de constructions de joueurs, exclues, §9).
- Kingdom (Muxxu) : `www/img/**` (site, icônes, captures d'aide), `gfx/mapview/img` (éléments de la carte),
  `gfx/puzzle/img`, trois SWF : `gfx/mapview/gfx.swf` et `gfx/battle/gfx.swf` (AS3), `gfx/puzzle/gfx.swf` (AS2),
  des `.fla`.
- CroqueMotel (`Muxxu/Hotel`) : `flash/gfx/**` (décors, personnages, monstres, objets), `art/` (illustrations),
  `www/img/**`, `flash/swf/_gfx.swf` (AS3), des `.fla`, des XML de textes.
- Intrusion : `client/img*`, `client/dockIcons`, `www/img/**`, 49 sons MP3 (`www/sfx`), `client/swf/_gfx.swf` et
  `_cinematics.swf` (AS2). `client/img_faces` (100 portraits), `client/img_cine` et deux autres images sont des
  photographies (visages, objets) venues de banques d'images : montrées à la demande de l'utilisateur.
- La Brute : `www/img/**`, `gfx/*.png`, les arènes (`fla/client/fla/*.png`), trois SWF AS2 (combat, inventaire,
  tournoi). Le corps des brutes n'existe que dans des `.fla` (`perso.fla`, `mini_perso.fla`), non lus.
- Odyssey : `www/img/**`, `design/heroes_HD`, `fla/map/bmp` (dont 16 `.tga`, vues d'un bateau sous 16 angles),
  `fla/client/gfx/icons.png` (planche) et sa source `icons.gal`, dix SWF AS3, plus `all.swf` (mêmes symboles que
  `heroes.swf` + `monsters.swf`), `game.swf` (jeu compilé qui embarque les autres SWF et des données) et deux
  `.mtswf` (SWF ordinaires sous une autre extension) : traités aussi, seul ce qui diffère des autres SWF apparaît, le
  reste est noté comme présent à plusieurs endroits. Neuf `.fla` XFL (§5.9).
- Snake : planches du client `clients/arene/gfx` (fruits, bonus, effets, interface, illustrations des cartes,
  chiffres, tuiles) et `clients/*/gfx`, `www/img/**` (dont chaque fruit et chaque carte en GIF), `docs/`, onze SWF
  de ressources et de clients, des `.gal` (sources des PNG).

### 5.2 Inventaire des SWF

`python tools/swf_inventory.py <fichiers.swf>` liste les balises utiles de chaque SWF : formes, clips (`DefineSprite`),
bitmaps, sons (`DefineSound`), polices, symboles exportés. C'est ce qui a montré :
- qu'il n'y a **aucun son** dans les SWF de Mush et d'Alphabounce (et aucun mp3/wav dans leurs dossiers) ;
- que les graphismes d'Alphabounce sont presque tous vectoriels (`game.swf` : 763 formes, 550 clips, 163 symboles exportés) ;
- que le SWF de ressources de Mush ne contient que 14 bitmaps (les planches du client) et un écran de chargement ;
- que les SWF de Galaxy55 n'apportent rien de neuf : `explore.swf` embarque `texture.png` et `tiles.png` (mêmes octets)
  et des données Haxe, `clientResources.swf` et `exploreResources.swf` une police, `engine.swf` du code, `ui.swf` est vide
  (36 octets).

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
exportés dont le clip ou un caractère affiché diffère ; seuls ceux-là sont rendus, avec les formes de la version
principale quand elles sont identiques. Si la version de travail redessine ou renumérote des formes
(`swf_diff.py --shapes`, cas de `desert.swf` de Hordes), elle a ses propres exports FFDec. Au catalogue, un rendu identique au pixel près à celui de la version principale devient un
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
- **SWF** : clips rendus, formes SVG, bitmaps et sons exportés, copiés dans `gen/<jeu>/swf/<chemin du SWF>/` ;
- **planches d'animation** (clips et `.gal`) : en WebP sans perte quand il est plus léger que le PNG (`compact.py`).
  Le WebP est relu et comparé au PNG pixel à pixel, couleurs sous les pixels transparents comprises (`exact`) ; au
  moindre écart, ou s'il est plus lourd, le PNG reste. L'encodage (méthode 6) est lent : il est gardé dans
  `MT_WORK/webp/<sha1 du PNG>` et une reconstruction ne réencode que les planches nouvelles ;
- **planches** (§5.7) dans `gen/<jeu>/sheets/`, **modèles 3D** et réglages LabChirp (§5.8) ;
- **durée des sons** (`audio.py`, sans dépendance) : WAV = taille du bloc `data` / octets par seconde ; MP3 = somme
  des trames MPEG (ID3 et trame d'en-tête Xing/Info ignorées) ; OGG = position de la dernière page / fréquence Vorbis
  (Opus : 48 kHz). Les 502 sons du catalogue sont mesurés ; la page affiche la durée et trie par elle (« Plus grandes /
  plus longs » : images par surface, puis sons par durée) ;
- **banques d'images CastleDB** (`cdb_images`, `cdb_images.py`) : un `.img` est un JSON {md5 : image en base64} ;
  chaque image est écrite telle quelle dans `gen/<jeu>/cdb/` (octets décodés, base64 de Haxe complété de ses « = »)
  et nommée d'après la ligne du `.cdb` dont une colonne « image » renvoie à son md5 (Monster Hotel :
  `data/goals.img`, objets et distinctions, 146 noms sur 155 images).

Types : `img` (image), `gif` (GIF animé), `anim` (GraphicsGale), `clip` (clip Flash rendu), `svg` (forme vectorielle),
`snd` (son), `lch` (réglage de son LabChirp), `mdl` (modèle 3D).

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

### 5.7 Planches découpées (`sheets.py`, `galaxy55.py`, `pixels.py`)

Une planche (sprite sheet) n'est pas montrée telle quelle : elle mélange des dizaines d'éléments, et celle des blocs de
Galaxy55 porte des repères de travail. Chaque planche déclarée dans `sheets` (games.json) est découpée en morceaux qui
gardent **les pixels d'origine, sans modification ni ajout** ; la planche entière reste téléchargeable depuis chaque
fiche (« Planche d'origine »), et ses copies ailleurs (bitmaps d'un SWF) sont notées sur ses morceaux.

1. **Découpes du jeu** (`slices`) : rectangles repris tels quels du code (`SpriteLib.slice` / `sliceUnit`), avec leur
   nom. Galaxy55 : `tiles.png` d'après `fla/explore/src/exp/Manager.hx` (lock, deleted, unknown, flag, counter,
   system ×3, asteroid, hex, planet ×3, brush), `icons.png` d'après `fla/client/src/Interface.hx` (charge ×4,
   status_unknown, status_power).
2. **Cases nommées** (`grid` + `cells`) : `texture.png` est une grille de 64 × 64 cases de 32 px. Chaque bloc du tableur
   officiel `com/data.ods` (feuille `blocks`) y désigne ses faces : `texture` (côtés), `texUp` (dessus), `texDown`
   (dessous), drapeau `Textures(…)` (faces avant, arrière, gauche, droite), lus comme `com/Block.hx`. Une case utilisée
   donne un morceau au nom français du bloc (colonne `name`, sinon son identifiant) ; la fiche liste tous les blocs qui
   l'utilisent. 250 cases pour 213 blocs.
3. **Reste de la planche** : pixels non transparents restants, regroupés quand 2 px ou moins les séparent ; un fragment
   de moins de 64 px rejoint le morceau le plus proche à 6 px ou moins (dessins en points séparés), deux morceaux plus
   grands ne fusionnent jamais. Un groupe aligné sur la grille est coupé case par case (« case x,y »), sinon il forme un
   morceau nommé par sa position (« texture x,y »). Collection « · autres éléments de la planche ». Un bord de moins de
   24 px collé à une case déjà découpée (dessin qui déborde de sa case) n'est pas un morceau à part.
4. **Planche entière** : si des pixels dessinés (hors repères seuls) ne sont dans aucun morceau, la planche est aussi
   montrée telle quelle (collection « · planche entière ») ; c'est le cas de `texture.png` (46 px de débords),
   `tiles.png` (24 px) de Galaxy55, `fx.png` (2 px) et `elements.png` (16 px) de Snake.

**Planches de Mush** (`slices_from`, `mush.py`) : le client isométrique décrit ses découpes dans
`clients/iso/xml/tiles.xml` (`<sheet src="BmpGfx2">`, `<slice id params="x,y,l,h,nb_x,nb_y">`, lu par
`Data.addToStore`) ; la classe de chaque planche est reliée à son PNG par les bitmaps de `iso_deResources.swf`
(BmpGfx2 = gfx_01, BmpGfxFx = fx, BmpSmallFill, BmpMidFill, BmpMidFill2, BmpBigFill, BmpBigFill2, BmpGfxDev = dev).
Les personnages (`char.png`, BmpGfxChar) sont découpés par `Data.hx` (regChar, cases de 32 × 48) : une ligne par
héros de `data/Data.ods` (feuille `heros`), Derek Hogan et Andie Graham, puis les apparences de `data/DataEco.ods`
(feuille `heroSkins`, nom « HÉROS$n ») ; poses, marches à droite et à gauche, ligoté, couché. Les découpes
retournées (`flipX`, `WALK_DOWN`…) reprennent les mêmes pixels et ne sont pas refaites. `Masks.png`,
`char_flipped.png` (miroir de char.png), `char_02.png`, `raluca.png` et `gfx_02.png`, absents du code, sont découpés
par groupes de pixels. `ShipMap.png` (carte de données), `bg.png`, `starship_map.png` et `vaisseaux.png` restent
entiers.

**Atlas de Rockfaller** (`slices_from: ["texturepacker", "….xml"]`, `atlas.py`) : chaque planche du client
OpenFL est livrée avec son fichier TexturePacker (`<SubTexture name x y width height …>`), qui donne le nom et le
rectangle de chaque image ; le morceau est ce rectangle, sans les marges que TexturePacker avait rognées. Autour de
chaque image, TexturePacker répète ses bords sur 1 à 2 px (extrusion, contre les coutures au rendu) : ces pixels,
tous à 2 px ou moins d'un rectangle, sont ignorés (`bleed: 2`) et ne font ni morceau ni planche entière. Cinq atlas
(`fx`, `fx2`, `taupinotron`, `benchNineFont`, `birminghamFont`) n'ont que leur XML dans `assetsWeb/` : leur image
manque à l'archive (sauf `taupinotron.png`, présent dans `www/img/ss/`), et l'animation Flump `taupiFlump/` n'a que son
`library.json`.

**Planches de Teacher Story** : `characters.png` et `tiles.png` sont découpées d'après `client/src/Manager.hx`
(`mt.deepnight.SpriteLib` : `slice(nom, x, y, l, h, n)` = n images côte à côte, `sliceUnit` en cases de
`setUnit`) ; les deux rangées de numéros de travail (00 à 34) peintes entre les rangées de cheveux et d'yeux sont
déclarées comme bandes de repères (`marks` en rectangles) et écartées. `interface.png` et `pictos.png`, absentes du
code, sont découpées par groupes de pixels ; pour `pictos.png`, `gap: 3` garde entières les annotations manuscrites
du professeur (« peut mieux faire », « non non et non !! ») et `groups` regroupe « du grand art », aux mots plus
espacés. Aucun pixel n'est modifié : seul le cadrage des morceaux change.

**Planches à fond** (`background`, Snake et Odyssey) : le code du jeu rend transparent le blanc pur
(`makeTransp(…, 0xFFFFFFFF)`). Ce blanc est ignoré pour trouver les morceaux et pour sauter les cases vides, mais il
reste dans les pixels montrés. Un morceau dont le dessin (fond ôté) est identique à une ressource déjà présente,
par exemple un fruit du site `www/img/icons/fruits_NNN.gif`, n'est pas montré deux fois : il est noté dans les
« Aussi dans l'archive » de cette ressource. Les noms d'images peuvent venir d'un tableur (`names` : cartes de Snake,
colonne `id` de `clients/com/data.ods`). Les découpes retournées par le code (miroir) ne sont pas reprises : ce ne
sont pas des pixels de la planche.

**Repères de `texture.png`** : Motion Twin a peint dans la planche les numéros de colonne (0 à 63, ligne 5, orange) et
de ligne (1 à 12, colonne 26, bleu), avec contour noir et ombre. Ce sont des repères de travail, pas des ressources :
un repère qui ne touche aucun dessin (peint sur du transparent) n'apparaît dans aucun morceau. Sept dessins hors grille
sont recouverts par un repère (deux dalles de glace, trois parties des lianes, la caisse « 52 53 », les pavés « 11 12 ») :
ils le gardent, car le dessin d'origine n'existe plus sous les chiffres et les retirer laisserait des trous.

### 5.8 Modèles 3D (`models.py`, `render3d.py`) et réglages de son

Entrée `models` de games.json. Formats lus (aucun lecteur dans l'archive, décodés à la main, lecture vérifiée jusqu'au
dernier octet) :
- `.bae` (cosmonaute `cosmo.bae` : objets visi_re, combi, jetpack ; foreuse `foreuse.bae`) : COLLADA binaire,
  structure décrite en tête de `models.py`. Les `<input>` et `<asset>` ne sont pas dans le fichier : les indices de
  `<p>` donnent position puis normale (vérifié par les bornes de chaque source) ; sans `<up_axis>`, COLLADA est en Y
  vers le haut (le cosmonaute a les pieds à y = 0). Matériaux nommés sans couleur ni texture : rendu gris uni.
- `door.md` (porte ouverte, `Model(DoorOpenX)` du bloc `ShipDoorOpen`) : sommets x, y, z, u, v, ombrage (comme
  `Macro.getModel`) puis le script de l'éditeur 3D de Motion Twin qui l'a construite, montré dans la fiche. Texture :
  case 14,2 de `texture.png` (celle du bloc dans data.ods et du script), ombrage du fichier.

Pour chaque modèle : maillage pour la page (`gen/<jeu>/models/<nom>.js`, chargé à la demande), OBJ converti
(géométrie seule) et aperçu PNG (projection orthographique, sans rien ajouter). La fiche montre une vue 3D WebGL
(glisser pour tourner, molette, double-clic pour recadrer) et propose le fichier d'origine, l'OBJ et l'aperçu.

Réglages LabChirp (`.lch`, en-tête `LabChirp100`) : fichiers de paramètres du générateur de sons qui a servi aux
bruitages ; type `lch`, collection « · réglages LabChirp », fiche avec le WAV du même nom. Leurs paramètres ne sont pas
décodés.

### 5.9 Fichiers .fla (`fla_items.py`, `xfl.py`, `fla_bin.py`, `fla_compose.py`, `vector_svg.py`)

Tous les `.fla` du dossier d'un jeu sont lus (sauf `exclude`) : leurs symboles sont rendus en SVG, leurs bitmaps
et leurs sons extraits. Deux formats :
- **XFL** (Flash CS5 et plus, archive ZIP de XML : les `.fla` d'Odyssey) — `xfl.py`. Flash écrit un répertoire
  central ZIP non standard : l'archive est lue par ses en-têtes locaux. Formes `DOMShape` (bords en twips :
  « ! x y », « | x y », « [ cx cy x y », nombres décimaux ou « #hex.hex » sur 24 bits signés, fraction en 256ᵉ),
  instances `DOMSymbolInstance` (par nom, matrice, transformation de couleur), groupes, bitmaps (`bin/*.dat`),
  calques de masque et de guide. Les symboles sont **composés entiers**, première image de chaque calque.
- **Binaire** (Flash 5 à CS4, conteneur OLE : tous les autres) — `fla_bin.py` avec **fla-decoder** (MIT,
  `tools/fla_decoder/`, et olefile, `tools/olefile/`, ajoutés avec l'accord de l'utilisateur). fla-decoder décode
  la sérialisation MFC (`CPicPage`, `CPicLayer`, `CPicFrame`, `CPicShape`). Ce module corrige l'ordre des indices de
  style des bords (trait, remplissage, remplissage : le seul compatible avec la taille des tables sur toutes les
  formes) et retrouve les noms dans le flux `Contents` (chaque flux y est cité, suivi du nom de l'élément de
  bibliothèque, puis de son identifiant = numéro du flux). Limite : fla-decoder ne relie pas les instances
  (`CPicSprite`) à leur symbole et lit mal la structure de certains fichiers CS3/CS4 ; seules les **formes propres**
  de chaque symbole sont dessinées (les symboles qu'il place ne sont pas assemblés, ce que la fiche indique).

Rendu (`vector_svg.py`, `fla_compose.py`, le même pour les deux formats) : chaque remplissage est reconstitué en
enchaînant ses bords (ceux de l'autre côté à l'envers), chaque trait en enchaînant les bords de son style ;
dégradés linéaires et radiaux, remplissages bitmap, transformations de couleur (`feColorMatrix`), masques (`mask`
alpha). Les bitmaps sont incorporés en data URI (un SVG affiché par `<img>` ne charge pas de fichier externe).

Bitmaps (`fla_bitmaps.py`) : même format dans les flux `M n` des binaires et les `bin/*.dat` des XFL — `03 05`
sans perte 32 bits (blocs zlib, A R G B prémultiplié), `03 03` 8 bits à palette A R G B, ou JPEG ; vérifié au pixel
près contre les mêmes bitmaps exportés des SWF par FFDec. Sons : enregistrements `CMediaSound` de `Contents`
(fla-decoder) et flux correspondants, en MP3 ou WAV.

Doublons : un symbole au rendu identique à un autre, un bitmap ou un son identique à une ressource existante devient
un doublon (« Aussi dans l'archive ») ; un symbole du même nom qu'un clip ou une forme d'un SWF du jeu est relié à
celui-ci (« Même nom dans »), sans être fusionné, les deux rendus étant différents.

### 5.10 La page

`index.html` + `viewer/` : scripts classiques sans module ni dépendance (fonctionne aussi en `file://`), espace de noms
`MT`.

| Fichier | Rôle |
|---|---|
| `util.js` | types, création d'éléments, formats, attribution |
| `filters.js` | état des filtres, facettes avec compteurs, tris, adresse (`#…`) |
| `grid.js` | grille par paquets de 160 au défilement, en-têtes de collection, miniatures, animation au survol |
| `player.js` | lecture d'une planche dans un canvas (cadence du SWF ou délais du `.gal`) |
| `model.js` | vue 3D WebGL d'un modèle (sans bibliothèque) |
| `detail.js`, `detail-info.js` | fiche : zoom, lecture, clavier (← → ressource, espace, `,` `.` image), infos, téléchargements |
| `app.js` | barre latérale, barre d'outils, liens |

Une plateforme qui regroupe plusieurs jeux (`parts` de games.json : CaféJeux, KadoKado) déplie ses jeux sous sa ligne
quand on la choisit ; chaque ressource porte son jeu (`sg`, plus long préfixe de chemin, `parts.py`), l'adresse le
garde (`#jeu=cafejeux&sous=anticorps`) et la fiche l'affiche (« CaféJeux · Anticorp's »).

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

Les SWF AS3 (Flash 9+) exposent leurs symboles par `SymbolClass` (balise 76), que `swfrender` ne lit pas :
`tools/swf_symbols.py` la lit et ajoute ces symboles aux exports, pour le rendu comme pour le catalogue. Leurs clips
sont rendus comme les autres, timeline seulement (le code AS3 n'est pas exécuté). Les
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
| `games[].sheets[]` | planches à découper : `file`, `slices` (`name`, `rect`, `cols`, `rows`, `names`), `slices_from`, `grid`, `cells`, `marks`, `gap`, `groups`, `bleed`, `background` (§5.7) |
| `games[].models[]` | modèles 3D : `file`, et pour un `.md` `texture` + `cell` (§5.8) |
| `games[].cdb_images[]` | banques d'images CastleDB : `img` (`.img`) et `cdb` (noms) (§5.6) |
| `games[].collections` | préfixe de chemin → nom de collection |
| `games[].parts`, `root_part` | jeux d'une plateforme (`id`, `name`, `path`) ; nom des ressources hors de ces jeux |
| `games[].fetch` | sous-dossiers à récupérer au lieu de tout `folder` (KadoKado : `KadoKado/Games/Alphabounce`) |

## 8. `catalog.js`

`window.MT_CATALOG = { generated, repo, commit, license, games[], items[] }`. Champs d'une ressource : `i` identifiant
(`<jeu>:<chemin>[#…]`), `g` jeu, `c` collection, `t` type, `n` nom, `s` image affichée, `p` chemin dans l'archive (`#id`,
`#shapeN`, `#bitmapN`, `#soundN` dans un SWF), `u` lien GitHub, `w` `h` taille (clips : pixels du rendu ×2), `f` nombre
d'images, `sh` planche (WebP ou PNG), `cols` colonnes de la planche, `fps` cadence, `d` délais en ms (`.gal`), `fmt` format,
`z` poids, `dur` durée d'un son (s), `k` mots-clés, `sg` jeu d'une plateforme, `dup` autres emplacements, `o` fichier d'origine (`.gal`), `vec` vectoriel, `px` pixel art,
`x` infos SWF (`swf`, `id`, `timeline`, `labels`, `owners`, `same`), de planche (`sheet`, `rect`, `cell`, `slice`,
`blocks`, `sheet_dup`), de banque CastleDB (`cdb`, `md5`, `uses`), de modèle (`objects`, `tris`, `mats`, `up`, `mesh`, `obj`, `texture`, `script`) ou de réglage
(`header`, `snd`, `snd_name`, `snd_id`).

## 9. Exclusions (ce qui n'est pas de Motion Twin)

- Mush : `www/img/jquery/*` (thème jQuery UI) ; dans `www/img/social/`, les logos de sites de presse (Gamalive,
  Game-Guide, Gameblog, Gamer News, GameSphere, Gaminfo, Gamingway, Indie Statik, JeuxCapt, JeuxOnline, jeuxvideo.com,
  IG Magazine, Canard PC, Massively, N-Gamz, Rock Paper Shotgun, RomStation, Selectbutton, USgamer). Gardés : l'image
  Facebook, la boîte et les captures du jeu.
- Alphabounce : `web/img/bank/cat_cb*` (bannières de paiement avec les logos PayPal, Visa et MasterCard).
  `web/swf/adtk.swf` n'a que du code (aucun dessin).
- Kube : `gfx/events/*` (56 captures de constructions de joueurs pour des événements de la communauté, dont des
  personnages d'autres sociétés), dossier non parcouru.
- Odyssey `fla/client/gfx/icons.gal` et Snake `clients/playground/gfx/src/elements.gal` : sources GraphicsGale des
  planches `icons.png` et `elements.png`, déjà découpées (elles les montreraient en entier).
- CaféJeux : rien d'exclu. Quelques accessoires du café, dessinés par Motion Twin, évoquent des marques ou des
  œuvres (`boite_chocapic`, `boite_nesquick`, `flipper_StarWars`, `toile_joconde`, `toile_vanGogh`) sans logo
  lisible : gardés. `games/trigolo/gfx_ani/bg01.RIF` et `PREVIEW.PIX` (fichiers Corel Painter) ne sont pas lus ;
  `bg01.TGA` en est l'export.
- Teacher Story : `www/img/twitter.png` et `www/img/rss.png` (logos de Twitter et du flux RSS).
  `client/obj/classroom.clientResources.swf` et `corrector/obj/ClassCorrectionResources.swf` ne contiennent que des
  polices : non rendus. `client/fla/sprites/eddie.png` est vide dans l'archive (0 octet). Les objets du site
  évoquent parfois des jouets connus (console, poneys, trolls…) : dessins de Motion Twin, gardés.
- Rockfaller : rien d'exclu. Beaucoup d'objets à collectionner (`www/img/goals`) sont des clins d'œil à d'autres
  licences (Pokéball, Triforce, Pac-Man, Tetris, casque de stormtrooper…) : dessins de Motion Twin, gardés. Les
  icônes `assets/ic` sont le cube de Twinoid.
- Monster Hotel : rien d'exclu (`common/obfu.key`, clé d'obfuscation, et les bases `.cdb` ne sont pas des
  ressources). Le fond libre de l'atlas `rooms0.png` est noir opaque : déclaré en `background`.
- Uppercup Football : rien d'exclu ; `obj/uppercupResources.swf` et `obj/wtfootResources.swf` ne contiennent que des
  polices (non rendus).
- Partout : polices embarquées, `Thumbs.db`, tableurs de données.

## 10. Limites connues

- Pas de son pour Mush et Alphabounce (absent de l'archive) ; Galaxy55 a ses 12 bruitages en WAV.
- Galaxy55 : paramètres LabChirp non décodés ; `.bae` sans couleurs de matériaux (gris) ; en `file://` le navigateur
  refuse la texture dans WebGL, la porte s'affiche alors sans texture (l'aperçu PNG la montre) ; données Haxe chiffrées
  de explore.swf non lues ; `ui.fla` / `ui.swf` vides.
- `.fla` binaires : formes propres de chaque symbole seulement (pas d'assemblage des symboles placés, §5.9).
- Les champs texte dynamiques (remplis par le code du jeu) restent vides dans les rendus ; les textes statiques sont là.
- Rendus à 2 px par pixel Flash : agrandir au-delà dans la fiche pixellise ; les formes, elles, sont en SVG.
- Formes animées, voir §6 ; clips AS3 : timeline seulement, sans leur code.
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

Volumes (première version, 2 jeux) : `catalog.js` 1,2 Mo, `gen/` 32 Mo, dossier de travail 60 Mo, archive environ
185 Mo avec git. Avec dix jeux : `catalog.js` 6 Mo, `gen/` 180 Mo (dont 124 Mo pour Odyssey : planches d'animation
des décors, chaque image étant un fond entier), `build_catalog.py` environ 2 à 5 minutes. Avec douze jeux et les
planches d'animation en WebP sans perte (§5.6) : 19 992 ressources, `catalog.js` 11 Mo, `gen/` 264 Mo (Odyssey
130 Mo, Hordes 71 Mo) ; planches d'animation des dix premiers jeux 65,7 Mo au lieu de 112,9 Mo en PNG (Odyssey
47,7 Mo au lieu de 84 Mo), une seule planche reste en PNG ; `build_catalog.py` environ 13 minutes. Le premier
encodage WebP de toutes les planches (méthode 6) prend plusieurs dizaines de minutes ; ensuite le cache sert.

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

**2026-11-15** — Galaxy55 et barre du haut :
1. Ajout de Galaxy55 (dossier `Galaxy55/` de l'archive, même commit épinglé) : images de `fla/client/gfx` et
   `fla/explore/gfx`, 12 sons WAV, `explore.swf` (ses deux bitmaps sont des copies des PNG). Rien des portages du jeu.
   Aucun élément tiers trouvé sur la planche contact.
2. La planche des blocs montrée entière exposait les repères numérotés de Motion Twin et des dizaines d'éléments
   mêlés : planches découpées en morceaux aux pixels d'origine, nommés par le tableur et le code du jeu (§5.7).
3. Tout le matériel officiel, même absent du jeu : modèles 3D `.bae` et porte `door.md` décodés, vue 3D dans la page,
   réglages LabChirp (§5.8).
4. Page : l'en-tête restait en haut du document au lieu de suivre le défilement (`body` de hauteur 100 % : un en-tête
   `sticky` ne colle que dans son parent). `body` prend `min-height: 100vh` et la hauteur réelle de l'en-tête
   (`--top-h`, mesurée par un `ResizeObserver`) cale la barre d'outils et le volet des filtres au lieu de 64 px fixes.

**2026-11-15** — Kube et Kingdom (Muxxu) :
1. Dossiers `Muxxu/Kube` et `Muxxu/Kingdom` de l'archive, même commit épinglé ; images du jeu et du site, SWF.
   Kube : captures de constructions de joueurs (`gfx/events`) exclues (§9) ; rien de tiers dans Kingdom.
2. Symboles AS3 (`SymbolClass`) lus par `tools/swf_symbols.py` : les clips de `client/gfx.swf` (Kube),
   `gfx/mapview/gfx.swf` et `gfx/battle/gfx.swf` (Kingdom) sont rendus, et celui de `loading.swf` de Mush
   (`Mc_whole_loader`) l'est désormais aussi.

**2026-11-15** — reste de Muxxu (sauf Fever) : CroqueMotel, Intrusion, La Brute, Odyssey, Snake :
1. Dossiers `Muxxu/Hotel`, `Muxxu/Intrusion`, `Muxxu/LaBrute`, `Muxxu/Odyssey`, `Muxxu/Snake`. Rien de tiers ni de
   fans ; les photos d'Intrusion (banques d'images) sont montrées à la demande de l'utilisateur.
2. Planches de Snake et d'Odyssey découpées d'après leur code (`Gfx.hx`, `mt.pix.Store.slice`), avec un fond blanc
   ignoré mais gardé (§5.7) ; cartes de Snake nommées d'après `clients/com/data.ods` ; les 301 fruits de la planche
   rattachés aux GIF du site, identiques au dessin près.
3. `.tga` (Odyssey) montrés par une copie PNG ; `.gal` d'une seule image dédoublonnés avec leur PNG ; un clip au
   rendu identique dans un autre SWF du jeu (SWF embarqué) devient un doublon : le chargeur de Mush (dans
   `iso_deResources.swf`) et `quarterAnim` d'Alphabounce (`inv.swf` = `game.swf`) ne sont plus montrés deux fois.

**2026-11-15** — Odyssey complet, planches entières, fichiers .fla :
1. Odyssey : `all.swf`, `game.swf`, `all.mtswf` et `heroes.mtswf` rendus ; seuls 65 clips des `.mtswf`, différents
   de ceux des autres SWF, s'ajoutent, le reste est noté comme présent à plusieurs endroits.
2. Une planche dont des pixels dessinés ne sont dans aucun morceau est aussi montrée entière (§5.7, quatre planches).
3. Nouvelle méthode pour les `.fla` (§5.9) : XFL lus et composés (`xfl.py`), binaires lus avec fla-decoder (MIT,
   ajouté à `tools/` avec l'accord de l'utilisateur) ; rendu SVG commun ; bitmaps décodés au pixel près ; doublons
   et symboles de même nom qu'un clip SWF signalés. 16 293 ressources en tout ; `gen/` environ 226 Mo.

**2026-11-15** — planches de Mush découpées d'après `tiles.xml` et `Data.hx` (mush.py) : 14 planches, 2 323
morceaux dont 1 279 nommés (décor, équipements, effets, personnages et apparences) ; les six planches qui gardent
quelques pixels hors morceaux sont aussi montrées entières.

**2026-11-16** — Hordes, Alphabounce de KadoKado, planches d'animation allégées :
1. Hordes (dossier `Hordes/`) : images de la carte (`fla/map/img`), clients Flash de la carte, de l'exploration des
   ruines (`explo.swf` ; les quatre versions par langue ont les mêmes dessins, `_gfx.swf` / `_code.swf` en version de
   travail), de l'attaque (`attack.swf`, `desert.swf`, `zombie_cool.swf`), chargeurs, prototype DeathGrower, et leurs
   huit `.fla`. Rien de tiers. `desert.swf` reprend les clips d'`attack.swf` avec des formes renumérotées : il a ses
   propres exports et ses rendus, identiques, sont notés comme doublons.
2. Alphabounce : tout le dossier du jeu était déjà couvert (`adtk.swf` = code seul). Sa première version, mini-jeu de
   KadoKado (`KadoKado/Games/Alphabounce`), est ajoutée sous la plateforme KadoKado : 34 clips, 270 formes,
   bitmaps.
3. `variant_of` : `swf_diff.py --shapes` détecte une version de travail aux formes redessinées, qui reçoit alors ses
   propres exports FFDec (§5.4).
4. Planches d'animation en WebP sans perte quand il est plus léger (`compact.py`, §5.6) : 113 Mo → 66 Mo pour les dix
   premiers jeux, pixels vérifiés identiques.

**2026-11-16** — CaféJeux (dossier `CafeJeux/`) : images du café (`bitmaps` : barman, murs, meubles, bornes,
consommations, personnages), images, SWF et `.fla` des treize jeux (Anticorp's, Bandas, Billard, Boum, Grapiz, Hordes,
La Ferme, Marbils, Opalus, Pâturage, Power 4, Trigolo, Utopiz). Bandas et Marbils partagent le même `gfx.swf` ; les
`gfx.swf` de Boum et Trigolo sont des versions de travail aux mêmes dessins ; ceux de La Ferme et Pâturage, aux formes
différentes, sont rendus à part. 2 487 ressources ; 22 479 en tout, `gen/` 317 Mo (CaféJeux 76 Mo, dont 23,5 Mo pour
le clip `mcGradient` du Hordes de CaféJeux : 64 images d'un dégradé plein écran).

**2026-11-16** — plateformes : CaféJeux et KadoKado rangent leurs jeux en sous-lignes (`parts`, §5.10, §7) ;
l'Alphabounce de KadoKado passe sous KadoKado (seul ce dossier est récupéré, `fetch`). Année de CaféJeux corrigée
d'après le README de l'archive (2007).

**2026-11-16** — Teacher Story (dossier `TeacherStory/`) : graphismes et sprites du client, icônes d'actions, site
(objets, compétences, annotations, ancêtres…), 151 sons et musiques, 3 réglages LabChirp (associés à leur son), sept
SWF et sept `.fla`. Planches découpées d'après `Manager.hx` (§5.7), numéros de travail écartés ; nouveaux réglages
de planche `marks` en rectangles, `gap` et `groups`. 3 590 ressources ; 26 069 en tout, `gen/` 331 Mo, `catalog.js`
14 Mo.

**2026-11-16** — Teacher Story : `corrector/gfx` parcouru (`paper.png`, la feuille de copie, manquait). Rockfaller
(dossier `Rockfaller/`, Rockfaller Journey) : atlas TexturePacker découpés d'après leur XML (§5.7, `atlas.py`,
`bleed`), mondes, tutoriel, icônes des applications, site (objets à collectionner, captures, textes par langue),
79 bruitages et 2 musiques, `loading.swf`. 1 116 ressources ; 27 186 en tout, `gen/` 341 Mo, `catalog.js` 15 Mo.

**2026-11-22** — Monster Hotel (dossier `MonsterHotel/`) : dix atlas TexturePacker découpés (décor de la rue,
décoration, monstres, chambres, interface), fonds, icônes des applications (dont celles de Noël), 155 icônes d'objets
et de distinctions tirées de la banque CastleDB `data/goals.img` (`cdb_images.py`, noms d'après `goals.cdb`),
209 sons (bruitages, ambiances, bonheur des clients, musiques). 1 578 ressources. Durée des sons mesurée pour tout le
catalogue (`audio.py`) et prise en compte par le tri par taille.

**2026-11-22** — Uppercup Football (dossier `Uppercup/`) : cinq atlas TexturePacker découpés (terrain, interface,
maillots, joueurs), `misc.png` découpée d'après `src/m/Game.hx` (ballon, fumée, grille de 16 px), `gfx.swf` (41 clips),
captures, 53 sons. 1 268 ressources ; 30 032 en tout, `gen/` 364 Mo, `catalog.js` 17 Mo.
