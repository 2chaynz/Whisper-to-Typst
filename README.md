<img width="1160" height="197" alt="damn" src="https://github.com/user-attachments/assets/634ac298-396c-4411-a524-c64db2922abe" />

**Dicter des mathématiques à voix haute et obtenir un document Typst (.typ + pdf).**

Parler en français, en mêlant explications et formules dites à l'oral. On
récupère un `.typ` structuré, en syntaxe Typst native, et son PDF.

```
« la somme des 1 sur k carré, avec k qui va de 1 à l'infini,
   est égale à pi carré sur 6 »
                    ↓
$ sum_(k=1)^infinity 1/k^2 = pi^2/6 $
```

Les outils de dictée existants visent tous LaTeX. Aucun ne gère
un document entier mêlant prose et maths avec Typst.

La reconnaissance de maths parlées reste un problème difficile, les meilleurs
modèles publiés en 2025 affichent encore 27 à 40 % d'erreur caractère sur des
équations isolées. Ce projet en tient compte : la correction humaine est prévue
à chaque étape plutôt qu'ajoutée après coup.

## Installation 

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Le compilateur Typst arrive par pip. Pas de
clé API, la structuration passe par le CLI `claude`, donc par un abonnement
Claude Code.  

> Si la variable `ANTHROPIC_API_KEY` existe dans ton
> environnement, Claude Code bascule en facturation par token au lieu d'utiliser
> ton abonnement.

Il faut aussi `ffmpeg` pour les formats audio autres que le WAV
(`sudo apt install ffmpeg`). 

## Cas d'usage

### Enregistrer au téléphone puis traiter ensuite

Le mode principal. Enregistre avec le dictaphone de ton téléphone, transfère le
fichier, lance :

```bash
.venv/bin/audio2typst importer download/Cl13.m4a --session CL
```

Tous les formats passent : m4a, mp3, opus, wav ,la conversion est automatique.
Le fichier est découpé aux silences et envoyé paragraphe par paragraphe.

Sans contrainte de temps réel, autant prendre le modèle le plus précis :

```bash
.venv/bin/audio2typst importer download/Cl13.m4a --session CL --model large-v3-turbo
```

### Dicter en direct au micro

```bash
.venv/bin/audio2typst live --session CL
```

Le document se remplit pendant qu'on parle. Une pause de 2,5 s envoie le bloc
accumulé. **Entrée** met le micro en pause, **Ctrl-C** termine.

### Retoucher le `.typ` à la main

Le document est un fichier Typst ordinaire, éditable dans n'importe quel
éditeur. Les corrections sont détectées et **font autorité** : la dictée
suivante ne les écrasera pas.

Mais une retouche manuelle ne recompile pas le PDF. Pour qu'il suive :

```bash
.venv/bin/audio2typst compiler --session CL --suivre
```

Lancer ça dans un second terminal, garder le lecteur de PDF ouvert à côté, et le
rendu se met à jour à chaque sauvegarde.

### Enchaîne plusieurs enregistrements

Réutilise le même `--session`. Le document existant est réinjecté, le nouveau
contenu s'ajoute.

```bash
.venv/bin/audio2typst importer download/Cl14.m4a --session CL
.venv/bin/audio2typst importer download/Cl15.m4a --session CL
```

### Voir ce que Whisper entend

```bash
.venv/bin/audio2typst transcribe fichier.m4a    # transcription seule
.venv/bin/audio2typst bench fichier.m4a         # compare les modèles
```

Ni Claude ni PDF : aucun quota consommé.

## Les sessions

Une session est un dossier de travail. On la nomme, elle persiste, on y
revient.

```
sessions/CL/
├── document.typ          le document courant
├── document.pdf          sa compilation
├── transcriptions.jsonl  le texte brut horodaté, avant interprétation
└── .empreinte            signature du document (détection d'édition manuelle)
```

**Elle est créée automatiquement** au premier `--session CL`. Sans l'option, une
session horodatée est créée.

**Elle se reprend** en redonnant le même nom, même des jours plus tard et depuis
un terminal neuf : le document existant est réinjecté dans le contexte avant le
nouveau passage.

**`transcriptions.jsonl` est le filet.** Il conserve ce que Whisper a réellement
entendu, avant toute interprétation par Claude. Si une structuration part de
travers, on retrouve la source.

Le dossier `sessions/` est ignoré par git.

## Le glossaire

`glossaire-maths.txt`, un terme par ligne, chargé automatiquement. Il est passé
à Whisper pour biaiser la reconnaissance vers ton vocabulaire.

 Mesuré sur le modèle `small` :

| Ce quei est dit | Sans glossaire | Avec |
|---|---|---|
| « pi carré sur 6 » | `p² sur 6` ✗ | `pi carré sur 6` ✓ |
| « à l'infini » | `l'infinie` ✗ | `l'infini` ✓ |

Sans lui, les formules sont **silencieusement fausses**, Claude reçoit « p carré
sur 6 » et compose consciencieusement $p^2/6$. Ajouter le vocabulaire avant
chaque nouveau sujet.

## Sous le capot

```
micro / fichier → VAD → Whisper → Claude → Typst → PDF
                   │       │        │        │
              webrtcvad  local    CLI     bindings
                                claude     Python
```

Tout tourne **en local** sauf l'étape de structuration. L'audio ne quitte
jamais la machine ; seul le texte transcrit part chez Claude.

| Étape | Outil | Choix |
|---|---|---|
| Découpage | `webrtcvad` | deux seuils : 0,8 s pour Whisper, 2,5 s pour Claude |
| Transcription | `faster-whisper` | modèle `small` en int8, ~x0,5 du temps réel sur CPU |
| Structuration | CLI `claude` | un processus persistant, la conversation *est* le document |
| Composition | bindings Python `typst` | pas de toolchain Rust |

Le code fait environ 1 000 lignes réparties en six modules, dans
`src/audio2typst/`.

## Pour aller plus loin

**[`explications.md`](explications.md)** : le document détaillé : ce qu'est
chaque pièce, pourquoi elle est là, tous les cas d'usage pas à pas, les réglages,
le dépannage, et les mesures qui ont servi à trancher chaque décision technique.

## Licence

MIT.
