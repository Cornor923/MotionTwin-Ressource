# MotionTwin-Ressource

Page web locale pour parcourir les **ressources graphiques et sonores officielles des jeux Motion Twin**, telles que
Motion Twin les a publiées dans son archive [motion-twin/WebGamesArchives](https://github.com/motion-twin/WebGamesArchives)
(licence CC BY-NC-SA 4.0). Uniquement du matériel d'origine : rien de refait après coup (pas de remake, pas de création
de fans), et les éléments tiers présents dans l'archive (images jQuery UI, logos de presse, logos de paiement) sont exclus.

Premiers jeux : **Mush** (2012) et **Alphabounce** (2007).

![Clips Flash d'Alphabounce](docs/img/apercu.png)

## Contenu

| Jeu | Images | GIF animés | Animations GraphicsGale | Clips Flash rendus | Formes vectorielles (SVG) | Sons |
|---|---:|---:|---:|---:|---:|---:|
| Mush | 1 337 | 22 | 50 | 1 | 3 | 0 |
| Alphabounce | 200 | 1 | 0 | 188 | 916 | 0 |

Ni Mush ni Alphabounce n'ont de son dans l'archive officielle ; la page sait les lire pour les jeux suivants.

La page permet de :
- chercher par nom, chemin dans l'archive, nom de symbole Flash ou étiquette d'animation (sans tenir compte des accents) ;
- filtrer par jeu, type et collection (compteurs à jour selon les autres filtres) et trier (collection, nom, taille,
  nombre d'images, poids) ;
- régler la taille des miniatures et le fond (damier, sombre, clair) ; les animations se jouent au survol ;
- ouvrir une fiche : zoom (ajusté, 1× à 8×, Ctrl + molette), lecture image par image, vitesse, métadonnées (dimensions,
  images, SWF, n° de caractère, étiquettes, clips qui utilisent une forme), doublons dans l'archive, téléchargements
  (fichier, SVG, planche d'animation, image courante), attribution prête à copier, lien vers le fichier source sur GitHub ;
- partager l'état de la page : filtres, recherche et ressource ouverte sont dans l'adresse (`#jeu=mush&q=…&res=…`).

![Icônes d'objets de Mush](docs/img/apercu-mush.png)

## Afficher la page

Il faut seulement Git et Python 3.11 ou plus. Le catalogue (`catalog.js`) et les fichiers dérivés (`gen/`) sont versionnés ;
seules les images de l'archive Motion Twin sont à récupérer (sparse checkout de Mush et Alphabounce, environ 110 Mo) :

```bash
git clone https://github.com/Cornor923/MotionTwin-Ressource.git
cd MotionTwin-Ressource
python tools/rebuild.py --fetch
python tools/serve.py
```

Puis ouvrir http://127.0.0.1:8642/. Ouvrir `index.html` directement (double-clic) marche aussi, sauf le bouton
« Image courante (PNG) » (le navigateur interdit de lire un canvas en `file://`). `serve.py` désactive le cache du
navigateur, utile après une reconstruction du catalogue.

## Reconstruire le catalogue ou ajouter un jeu

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # Linux / macOS : .venv/bin/pip
# FFDec + Java : dans .tools/ (ignoré par git) ou via FFDEC_TOOLS / FFDEC_JAR, voir docs/METHODE.md
.venv/Scripts/python tools/rebuild.py
```

La première reconstruction complète prend environ 45 minutes (rendu des clips de `game.swf` d'Alphabounce) ; ensuite
seuls les SWF nouveaux sont exportés et rendus. Pour ajouter un jeu : une entrée dans [games.json](games.json), puis
`rebuild.py`. Tout le détail (méthode, choix, formats, limites, dépannage) est dans [docs/METHODE.md](docs/METHODE.md).

## Organisation

```
index.html, viewer/        page (HTML/CSS/JS sans dépendance ni compilation)
catalog.js                 catalogue généré (window.MT_CATALOG)
gen/                       fichiers dérivés générés : clips rendus, SVG, bitmaps de SWF, animations .gal décodées
games.json                 configuration des jeux : dossiers, exclusions, SWF, collections, notes
tools/rebuild.py           chaîne complète (archive, FFDec, rendus, catalogue)
tools/build_catalog.py     catalogue + gen/ (avec swf_items.py et gal.py)
tools/render_symbols.py    rendu des clips exportés d'un SWF
tools/swf_diff.py          clips qui diffèrent entre deux versions d'un SWF
tools/swf_inventory.py     inventaire rapide des balises d'un SWF (sons, bitmaps, symboles exportés…)
tools/serve.py             serveur local sans cache
tools/flash/               lecteur et compositeur SWF repris de kadokadeo (AGPL-3.0)
docs/METHODE.md            documentation complète
sources/                   archive Motion Twin (récupérée, ignorée par git)
```

## Licence et crédits

Les ressources sont © **Motion Twin**, publiées sous [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).
Ce dépôt est partagé sous la **même licence** (texte dans [LICENSE](LICENSE)) : pas d'usage commercial, crédit à Motion Twin,
partage dans les mêmes conditions. Exception : `tools/flash/`, repris de [eternaltwin/kadokadeo](https://github.com/eternaltwin/kadokadeo),
reste sous AGPL-3.0. Détails dans [NOTICE](NOTICE). Ce projet n'est ni affilié à Motion Twin ni approuvé par Motion Twin.
