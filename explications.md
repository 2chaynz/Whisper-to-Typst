# audio2typst — explications détaillées

Ce document explique **ce qu'est chaque pièce du projet, comment s'en servir dans
chaque situation, et pourquoi elle est faite ainsi**. Le [README](README.md)
suffit pour démarrer ; celui-ci est fait pour être lu une fois en entier, puis
consulté par morceaux.

## Sommaire

**Partie I — Comprendre**
[1. Ce que fait le projet](#1-ce-que-fait-le-projet) ·
[2. Pourquoi deux cerveaux](#2-pourquoi-deux-cerveaux-et-pas-un-seul) ·
[3. Comment fonctionne une session](#3-comment-fonctionne-une-session)

**Partie II — Les cas d'usage**
[4. J'enregistre au téléphone](#4-jenregistre-au-téléphone) ·
[5. Je dicte en direct](#5-je-dicte-en-direct-au-micro) ·
[6. Je me reprends à voix haute](#6-je-me-reprends-à-voix-haute) ·
[7. Je fais une pause](#7-je-fais-une-pause) ·
[8. Je retouche le `.typ`](#8-je-retouche-le-typ-et-je-veux-voir-le-pdf-suivre) ·
[9. J'enchaîne plusieurs enregistrements](#9-jenchaîne-plusieurs-enregistrements) ·
[10. Je veux juste vérifier](#10-je-veux-juste-vérifier-sans-consommer-de-quota) ·
[Où intervenir quand ça ne va pas](#récapitulatif--où-intervenir-quand-quelque-chose-ne-va-pas)

**Partie III — Les réglages**
[11. Le glossaire](#11-le-glossaire--la-pièce-à-ne-pas-négliger) ·
[12. Les seuils de silence](#12-les-seuils-de-silence) ·
[13. Le choix du modèle](#13-le-choix-du-modèle-whisper)

**Partie IV — Sous le capot**
[14. L'environnement virtuel](#14-lenvironnement-virtuel-venv) ·
[15. Le cache Hugging Face](#15-le-cache-hugging-face) ·
[16. Les six modules](#16-les-six-modules) ·
[17. Les deux mécanismes clés](#17-les-deux-mécanismes-clés)

**Partie V — Référence**
[18. Les sept commandes](#18-les-sept-commandes) ·
[19. Dépannage](#19-dépannage) ·
[20. Ce qui reste à faire](#20-ce-qui-reste-à-faire) ·
[21. Résumé](#21-résumé-en-une-page)

---
---

# Partie I — Comprendre

## 1. Ce que fait le projet

Tu parles en français, en mêlant des explications et des formules dites à voix
haute. Un document Typst structuré se remplit, et un PDF se recompile.

```
  ta voix (micro ou fichier)
     │
     ▼
  [1] capture ──────────── capture.py      micro en continu, ou lecture de fichier
     │
     ▼
  [2] VAD ──────────────── capture.py      découpe aux silences
     │
     ▼
  [3] Whisper ─────────── transcribe.py    son → texte français brut
     │
     ▼
  [4] Claude ──────────── structure.py     texte brut → syntaxe Typst
     │
     ▼
  [5] Typst ───────────── compile.py       .typ → PDF
```

Les étapes 1, 2, 3 et 5 tournent **entièrement sur ta machine**, sans réseau.
Seule l'étape 4 sort de chez toi, et elle ne reçoit que du texte — **ton audio
ne quitte jamais l'ordinateur**.

## 2. Pourquoi deux cerveaux et pas un seul

C'est la décision structurante du projet.

**Whisper transcrit, il ne comprend pas.** Il convertit un signal sonore en suite
de mots. Quand tu dis « x carré plus un sur x moins un », il écrit exactement ces
mots. Il ne sait pas que c'est une fraction.

**Claude interprète.** Il reçoit cette phrase et doit décider si elle signifie
$(x^2+1)/(x-1)$ ou $x^2 + 1/(x-1)$. Les deux lectures sont grammaticalement
valables ; seul le sens mathématique les départage.

Séparer les deux met chaque outil là où il est bon, et surtout permet de faire
tourner le premier **gratuitement sur ton processeur**, en n'envoyant au second
que du texte.

## 3. Comment fonctionne une session

Une session est un **dossier de travail nommé**. C'est l'unité qui porte un
document du début à la fin, sur plusieurs enregistrements et plusieurs jours.

```
sessions/CL/
├── document.typ          le document courant
├── document.pdf          sa compilation
├── transcriptions.jsonl  le texte brut horodaté, avant interprétation
└── .empreinte            signature du document (voir §17)
```

**Elle se crée toute seule.** Le premier `--session CL` crée le dossier. Sans
l'option, une session horodatée est créée (`2026-09-26_14-30-12`).

**Elle se reprend en redonnant le même nom**, même des jours plus tard, même
depuis un terminal neuf. Le mécanisme est expliqué en §17 : le document existant
est réinjecté dans le contexte de Claude avant le nouveau passage, donc rien
n'est perdu et rien n'est dupliqué.

**Chaque passage écrit trois choses** : le document mis à jour, le PDF
recompilé, et une ligne dans le journal.

**`transcriptions.jsonl` est ton filet de sécurité.** Une ligne JSON par
paragraphe, horodatée, contenant le texte brut **avant toute interprétation** :

```json
{"horodatage": "2026-09-25T19:22:07", "texte_brut": "la somme des 1 sur k carré…"}
```

Si Claude part de travers sur un passage, tu y retrouves ce que Whisper avait
réellement entendu, et tu peux repartir de là.

**`sessions/` est ignoré par git.** Ce sont tes documents, pas du code. Si tu
veux les versionner, fais-en un dépôt séparé.

---
---

# Partie II — Les cas d'usage

> **Le réflexe avant chaque session, quel que soit le mode.** Ouvre
> `glossaire-maths.txt` et ajoute le vocabulaire du jour. C'est le geste qui
> détermine la qualité de tout le reste — voir le §11 pour comprendre pourquoi.

## 4. J'enregistre au téléphone

Le mode principal si tu n'as pas envie de dicter devant ton PC.

**Il n'y a aucune étape manuelle en plus.** Ni conversion de format, ni création
de session.

1. Enregistre avec le dictaphone de ton téléphone. Parle comme en direct, en
   **marquant tes pauses entre les idées** — ce sont elles qui découperont le
   document.
2. Transfère le fichier sur le PC, par le moyen que tu veux. Le projet prévoit
   un dossier `download/` pour les déposer, ignoré par git.
3. Lance l'import :

```bash
.venv/bin/audio2typst importer download/Cl13.m4a --session CL
```

**Tous les formats passent** — m4a, mp3, opus, ogg, wav — et n'importe quelle
fréquence d'échantillonnage. Si le fichier n'est pas déjà du WAV 16 kHz mono,
ffmpeg le convertit dans un dossier temporaire ; **ton fichier d'origine n'est
jamais modifié**.

**L'avancement s'affiche** en pourcentage, parce qu'un enregistrement de dix
minutes demande environ cinq minutes de transcription :

```
[ 28%] La somme des 1 sur k carré, avec k qui va de 1 à l'infini…
  ▸ 5 lignes · PDF sessions/CL/document.pdf
[ 56%] On peut ensuite ajouter des contraintes…
  ▸ 9 lignes · PDF sessions/CL/document.pdf
```

### L'avantage que tu ne soupçonnes peut-être pas

Sans contrainte de temps réel, **la vitesse de transcription ne compte plus**.
En direct, le gros modèle prendrait du retard sur ta parole. Sur un fichier, il
prend seulement plus longtemps :

```bash
.venv/bin/audio2typst importer download/Cl13.m4a --session CL --model large-v3-turbo
```

C'est le meilleur choix pour un enregistrement que tu ne referas pas.

### Le garde-fou sur les longs monologues

Si tu parles sans jamais marquer de vraie pause, aucun paragraphe ne se
déclencherait et Claude recevrait un pavé. Au-delà de **1 200 caractères**
accumulés, l'envoi se fait quand même, avec la mention
`(pas de pause détectée — envoi sur volume)`.

### Ce que tu perds, ce que tu gagnes

| | Téléphone | Direct au micro |
|---|---|---|
| Voir la transcription défiler | non | oui |
| Te corriger en voyant l'erreur | non | oui |
| Contrainte de vitesse | aucune | le modèle doit tenir le temps réel |
| Qualité accessible | la meilleure | limitée par la vitesse |

Te reprendre **à voix haute** pendant l'enregistrement fonctionne exactement
pareil dans les deux cas (§6) : Claude reçoit la même chose au final.

## 5. Je dicte en direct au micro

```bash
.venv/bin/audio2typst live --session CL
```

**Parle comme tu expliquerais à quelqu'un**, et marque tes pauses naturelles
entre les idées — ce sont elles qui découpent le document.

Le micro s'ouvre et reste ouvert. Chaque bout de phrase reconnu s'affiche
pendant que tu continues à parler, donc garde un œil sur le terminal : tu y vois
ce que Whisper comprend, en direct. Une pause de plus de 2,5 s envoie le bloc
accumulé à Claude : le document se met à jour, le PDF se recompile.

```
Entrée = pause / reprise · Ctrl-C = terminer
```

**Entrée** met en pause — voir §7, c'est important. **Ctrl-C** termine et envoie
ce qui restait en tampon.

Si la segmentation ne colle pas à ton rythme, c'est le §12.

## 6. Je me reprends à voix haute

**Oui, ça marche, et ça modifie ce qui précède.** Claude traite ces phrases
comme des **instructions sur le document**, jamais comme du contenu — elles
n'atterrissent pas dans le texte.

Comportements vérifiés :

| Ce que tu dis | Ce qui se passe |
|---|---|
| « non, j'ai fait une erreur, c'est x carré **moins** trois x » | l'expression déjà écrite est corrigée |
| « enlève la dernière phrase, elle ne sert à rien » | la phrase disparaît |
| « mets un titre au-dessus, appelle ça Fonction d'étude » | `= Fonction d'étude` est ajouté |
| « sa dérivée vaut deux x moins trois » | ajout normal à la suite |

**Le moment où tu te reprends change peu de chose.** Avant ta pause, la
correction part avec l'erreur dans le même bloc. Après, l'erreur est déjà écrite
et compilée — Claude revient dessus au passage suivant. Le document final est
identique ; simplement, un PDF intermédiaire aura brièvement porté l'erreur.

**Une correction ne change que ce qu'elle nomme.** Si le document porte
$f(x) = x^2 + 3x - 2$ et que tu dis « c'est x carré moins trois x », le terme
`- 2` est conservé : tu ne l'as pas mentionné. Pour tout remplacer, redis
l'expression entière.

**Claude peut te corriger sans que tu demandes.** Si tu dictes quelque chose qui
ressemble à une erreur de transcription, il écrit la version qu'il juge correcte
et le signale en commentaire :

```typst
// ambigu : nom transcrit « Louise and Shaman », lu Luiz Chamon
```

C'est voulu — le plus souvent, c'est Whisper qui a mal entendu. Mais si tu
voulais vraiment ce que tu as dit, **redis-le** : une reprise explicite prime sur
son jugement, et il retire son commentaire.

**Ce qu'il ne fait jamais :** te poser une question et attendre. La dictée ne
s'interrompt pas. Quand une ambiguïté résiste, il tranche et laisse un
commentaire `//`. **Relis ces commentaires en fin de session** : ils marquent
exactement les endroits où il a dû deviner.

## 7. Je fais une pause

**Tu n'as pas besoin d'arrêter la session.** Le VAD ne produit rien tant que tu
ne parles pas : une pause ne consomme aucun quota et n'écrit rien.

**Mais le micro reste physiquement ouvert.** Si quelqu'un te parle, si tu prends
un appel, si la radio tourne — c'est de la vraie parole, le VAD la détecte,
Whisper la transcrit, et elle part dans ton document. D'où la touche de pause :

```
Entrée → ⏸  en pause — le micro est ignoré. Entrée pour reprendre.
```

En pause, ce que capte le micro est **jeté**. Ton tampon en cours reste intact :
si tu t'interromps au milieu d'un paragraphe, tu reprends dessus.

### Ce que coûte une pause longue

Mesuré sur 5 minutes d'inactivité, processus laissé vivant :

| | dictée continue | après 5 min d'inactivité |
|---|---|---|
| Contexte à recréer | 151 tokens | **7 303 tokens** |
| Processus survit | — | oui |
| Document conservé | — | oui |

Rien ne casse, mais le cache de contexte se dégrade vite. En pratique :

- **Pause courte** (quelques minutes) : Entrée, puis reprends. Le réamorçage est
  un coût ponctuel.
- **Pause longue** (déjeuner, fin de journée) : `Ctrl-C`. Relance ensuite avec le
  **même** `--session` — pour le même coût, et sans laisser un processus tourner.

## 8. Je retouche le `.typ` et je veux voir le PDF suivre

**La règle à retenir : une dictée recompile le PDF, une retouche de ta main
non.** Rien ne surveille le fichier pendant que tu l'édites. Si tu corriges une
formule et que tu regardes le PDF, tu verras encore l'ancienne version, **sans
aucun avertissement**. C'est le piège à connaître.

### Cas 1 — une correction vite faite

```bash
.venv/bin/audio2typst compiler --session CL
```

Affiche `✓` suivi du chemin du PDF, ou l'erreur de Typst si la syntaxe ne passe
pas.

### Cas 2 — tu travailles le document

Relancer la commande à chaque sauvegarde est vite pénible. Mets la surveillance
en place, une fois :

**1.** Ouvre un **second terminal** :

```bash
cd ~/Desktop/Projets/whisper-typst
.venv/bin/audio2typst compiler --session CL --suivre
```

Laisse-le tourner — il vérifie le fichier deux fois par seconde.

**2.** Ouvre `sessions/CL/document.pdf` dans ton lecteur. Evince, Okular et
Zathura rechargent tout seuls quand le fichier change.

**3.** Édite `sessions/CL/document.typ` normalement. À chaque sauvegarde :

```
17:49:42   ✓ sessions/CL/document.pdf
```

**4.** `Ctrl-C` quand tu as fini.

### Si tu casses la syntaxe

La surveillance ne s'arrête pas :

```
17:49:44   ✗ unknown variable: fonction_qui_nexiste_pas
17:49:46   ✓ sessions/CL/document.pdf
```

Tu corriges, tu sauvegardes, ça repart. Le PDF précédent reste sur le disque
entre-temps.

### Viser un fichier hors session

```bash
.venv/bin/audio2typst compiler ~/Documents/rapport.typ --suivre
```

### Tu peux continuer à dicter en même temps

Les deux mécanismes sont indépendants : `--suivre` met à jour ton **PDF**,
l'empreinte SHA-256 (§17) protège ton **texte** contre l'écrasement. Laisse la
surveillance tourner pendant un `live` ou un `importer` — elle recompilera aussi
bien les modifications de Claude que les tiennes.

## 9. J'enchaîne plusieurs enregistrements

Réutilise le même `--session`. C'est le seul geste.

```bash
.venv/bin/audio2typst importer download/Cl13.m4a --session CL
.venv/bin/audio2typst importer download/Cl14.m4a --session CL
.venv/bin/audio2typst importer download/Cl15.m4a --session CL
```

Tu verras passer, au premier passage de chaque commande :

```
▸ session reprise — document existant réinjecté
```

**C'est un ajout pur.** Vérifié par `diff` sur un document réel : zéro ligne
perdue, titres conservés, notations conservées, commentaires d'ambiguïté
conservés. Le nouveau contenu s'insère dans la structure existante, sous une
nouvelle section si le sujet diffère.

Ça marche aussi **après une édition manuelle** entre deux imports : tes
corrections priment (§17).

## 10. Je veux juste vérifier, sans consommer de quota

```bash
.venv/bin/audio2typst transcribe download/Cl13.m4a
```

Transcription seule : ni Claude, ni PDF, aucun quota. Utile pour voir ce que
Whisper entend avant de lancer le traitement complet.

```bash
.venv/bin/audio2typst bench download/Cl13.m4a
```

Passe le même fichier dans `small` et `large-v3-turbo` et affiche, pour chacun,
le temps, le rapport au temps réel et la transcription. C'est ce qui a servi à
choisir le modèle par défaut — relance-le quand tu changes de type de contenu.

## Récapitulatif : où intervenir quand quelque chose ne va pas

**Quand quelque chose est faux.** Deux points d'entrée selon la gravité.

*Une formule mal interprétée* → ouvre `sessions/CL/document.typ`
dans ton éditeur, corrige, sauvegarde. Continue à dicter : ta correction est
détectée et fait autorité.

*Whisper a mal entendu un mot* → ajoute-le au glossaire pour la suite, et
corrige le `.typ`.

*Un passage entier part de travers* → `transcriptions.jsonl` contient le texte
brut d'origine. Tu peux repartir de là.

**Après.** Le PDF est dans le dossier de session. Le `.typ` est un fichier
Typst ordinaire : tu peux le reprendre, l'inclure ailleurs, le recompiler.

**Reprendre plus tard.** Même `--session`, le document existant est réinjecté.

---

---
---

# Partie III — Les réglages

## 11. Le glossaire — la pièce à ne pas négliger

`glossaire-maths.txt`, à la racine. Un terme par ligne, `#` pour commenter,
chargé **automatiquement** sans rien demander.

Il est passé à Whisper comme `initial_prompt` : un texte de contexte que le
modèle traite comme « ce qui vient d'être dit ». Ça ne lui donne pas d'ordre —
ça **biaise son décodage** vers ce vocabulaire. Lui montrer le mot « pi » avant
de décoder rend « pi » plus probable que « p ».

Ce n'est pas un confort. Mesuré sur le modèle `small`, même enregistrement :

| Ce que tu dis | Sans glossaire | Avec glossaire |
|---|---|---|
| « pi carré sur 6 » | **`p² sur 6`** | `pi carré sur 6` |
| « k carré » | `k²` | `k carré` |
| « à l'infini » | `l'infinie` | `l'infini` |

**L'erreur sur π est la plus grave, et pas parce qu'elle est fausse : parce
qu'elle est silencieuse.** Claude reçoit « p carré sur 6 », n'a aucune raison de
douter, et écrit consciencieusement $p^2/6$. Tu obtiens un PDF impeccable qui
dit une bêtise.

**Ajoutes-y ton vocabulaire avant chaque nouveau sujet.** Si tu attaques les
distributions, écris « lagrangien », « convolution », « support compact ».
Whisper ne connaît pas ton domaine ; ce fichier le lui apprend.

## 12. Les seuils de silence

Deux seuils, parce que Whisper et Claude veulent des choses opposées.

```
  … parole parole parole silence silence silence …
                          └────── 0,8 s ──────┘
                          → fin de SEGMENT : envoi à Whisper

  … silence silence silence silence silence silence …
    └──────────────── 2,5 s ────────────────────┘
                          → fin de PARAGRAPHE : envoi à Claude
```

Whisper travaille mieux sur des bouts courts — une phrase, pas un monologue.
Claude a besoin de **contexte** : une phrase isolée est ambiguë
mathématiquement, un paragraphe ne l'est presque plus. Un seuil unique aurait
sacrifié l'un des deux.

**Régler selon ton rythme** (fonctionne sur `live` comme sur `importer`) :

| Symptôme | Correctif |
|---|---|
| Claude coupe au milieu de tes phrases | `--silence-paragraphe 3.5` |
| Claude attend trop, avale trois idées | `--silence-paragraphe 1.8` |
| Des bouts de phrase sont mal découpés | `--silence-segment 0.5` |

Comportement validé : une pause de 1 s produit deux segments mais **un seul**
envoi à Claude ; une pause de 4 s produit **deux** envois.

## 13. Le choix du modèle Whisper

Deux modèles sont installés.

| | `small` | `large-v3-turbo` |
|---|---|---|
| Poids | 483 Mo | ~1,5 Go |
| Vitesse sur cette machine | **~x0,5** du temps réel | x1,73 |
| Précision mathématique | égale, **avec le glossaire** | égale |

Sur un processeur 4 threads sans GPU, `small` est deux fois plus rapide que le
temps réel : il ne prendra jamais de retard sur ta dictée. C'est le défaut.

**Quand prendre `turbo`** : à l'import d'un fichier, où la vitesse n'a aucune
importance, ou pour re-transcrire un passage difficile.

```bash
.venv/bin/audio2typst importer fichier.m4a --model large-v3-turbo --session CL
```

Le modèle `medium` a été écarté : environ 2 à 3 fois le temps réel sur cette
machine, pour une précision que `turbo` atteint plus vite.

Le **modèle Claude** se choisit séparément avec `--claude-model`. Le défaut est
Sonnet : la tâche est contrainte et la syntaxe Typst est fournie dans le prompt,
Opus consommerait plus de quota pour un gain marginal.

---
---

# Partie IV — Sous le capot

## 14. L'environnement virtuel (`.venv/`)


### Qu'est-ce que c'est

Un **environnement virtuel** est une installation de Python isolée, rangée dans
un dossier du projet. Sans lui, `pip install` déposerait les bibliothèques dans
le Python du système, où elles se mélangeraient à celles d'autres projets — avec
le risque classique que deux projets réclament deux versions incompatibles de la
même bibliothèque.

Ici il pèse **513 Mo** et vit dans `.venv/`. Il est exclu de git (`.gitignore`),
parce qu'il se reconstruit en une commande et n'a rien à faire dans l'historique.

### Comment on s'en sert

Deux façons équivalentes. Soit tu préfixes chaque commande :

```bash
.venv/bin/audio2typst live
```

Soit tu « actives » l'environnement une fois pour la durée du terminal :

```bash
source .venv/bin/activate
audio2typst live          # plus besoin de préfixer
deactivate                # pour en sortir
```

La première forme est plus explicite et ne peut pas t'induire en erreur sur
l'environnement réellement utilisé. Ce document l'emploie partout.

### Ce qu'il y a dedans

Tu as installé cinq bibliothèques. Elles en ont amené une vingtaine d'autres.

**Ce que tu as demandé :**

| Paquet | Version | À quoi ça sert |
|---|---|---|
| `sounddevice` | 0.5.6 | Parle au micro. C'est une passerelle Python vers PortAudio, la bibliothèque C qui gère les cartes son sous Linux, macOS et Windows. |
| `numpy` | 2.5.3 | Manipule le son sous forme de tableaux de nombres. Un son, informatiquement, c'est une longue liste de mesures d'amplitude — 16 000 par seconde ici. |
| `webrtcvad-wheels` | 2.0.14 | Détecte si une tranche de 30 ms contient de la parole ou du silence. C'est le détecteur d'activité vocale extrait de WebRTC, le moteur audio de Google Meet. La variante `-wheels` est fournie précompilée, donc rien à compiler à l'installation. |
| `faster-whisper` | 1.2.1 | Fait tourner Whisper, le modèle de reconnaissance vocale d'OpenAI. |
| `typst` | 0.15.0 | Le compilateur Typst lui-même, empaqueté en module Python. C'est du Rust compilé : tu obtiens le vrai compilateur sans installer Rust. |

**Ce qui est venu avec, et qui compte :**

| Paquet | Pourquoi il est là |
|---|---|
| `ctranslate2` | **Le moteur d'inférence.** C'est lui qui fait tourner le réseau de neurones. Écrit en C++ et optimisé pour processeur — c'est la raison pour laquelle `faster-whisper` est plus rapide que l'implémentation d'origine. |
| `onnxruntime` | Un second moteur d'inférence, utilisé pour le VAD intégré de faster-whisper (nous n'utilisons pas celui-là, mais il est installé d'office). |
| `av` | Décode les formats audio et vidéo. C'est une passerelle vers FFmpeg. |
| `tokenizers` | Découpe le texte en unités que le modèle manipule. |
| `huggingface_hub`, `hf-xet` | Téléchargent les modèles depuis Hugging Face et gèrent le cache (section suivante). |
| `numpy`, `tqdm`, `PyYAML`, `filelock`… | Utilitaires : calcul, barres de progression, configuration, verrous de fichiers. |

### Le reconstruire de zéro

Si tu casses quelque chose, ou sur une autre machine :

```bash
rm -rf .venv
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Le `-e` installe le projet en **mode éditable** : la commande `audio2typst`
pointe vers tes fichiers sources plutôt que vers une copie. Tu modifies
`src/audio2typst/cli.py`, la commande change immédiatement, sans réinstaller.

---

## 15. Le cache Hugging Face


### Ce que c'est

**Hugging Face** est la plateforme où sont publiés la plupart des modèles
d'intelligence artificielle ouverts — un dépôt public, comme GitHub l'est pour
le code. Whisper y est hébergé, dans des versions converties pour CTranslate2.

Quand `faster-whisper` charge le modèle `small` pour la première fois, il le
télécharge depuis Hugging Face et le range dans un **cache partagé** :

```
~/.cache/huggingface/hub/
```

Ce dossier est **en dehors du projet**, dans ton répertoire personnel. C'est
voulu : si tu crées demain un autre projet qui utilise Whisper, il réutilisera
le même fichier au lieu de retélécharger 500 Mo.

### Ce qu'il y a dedans

```
~/.cache/huggingface/hub/
├── models--Systran--faster-whisper-small/          ← le modèle rapide
│   ├── blobs/       les fichiers réels
│   ├── snapshots/   des liens vers une version précise
│   └── refs/        quelle version est la « courante »
└── models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/
```

Le nom du dossier encode l'adresse du modèle : `Systran/faster-whisper-small`
devient `models--Systran--faster-whisper-small`.

Chaque modèle se compose de quatre fichiers :

| Fichier | Taille (modèle `small`) | Rôle |
|---|---|---|
| `model.bin` | **483 Mo** | Les poids du réseau de neurones. C'est le modèle. |
| `tokenizer.json` | 2,2 Mo | La table qui convertit le texte en nombres et inversement. |
| `vocabulary.txt` | 460 Ko | Le vocabulaire connu du modèle. |
| `config.json` | 2 Ko | Les dimensions du réseau. |

La séparation `blobs` / `snapshots` permet de garder plusieurs versions d'un
modèle sans dupliquer les fichiers identiques : les snapshots sont des liens
symboliques vers les blobs.

Les deux modèles occupent **2 Go au total** chez toi.

### L'inspecter et le vider

```bash
du -sh ~/.cache/huggingface                    # ce qu'il pèse
ls ~/.cache/huggingface/hub/                   # quels modèles sont là
rm -rf ~/.cache/huggingface/hub/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo
```

Supprimer un modèle est sans danger : il sera retéléchargé au besoin. Le
supprimer fait juste perdre les 2 minutes de téléchargement initial.

### Les deux modèles, et pourquoi on garde le lent

| | `small` | `large-v3-turbo` |
|---|---|---|
| Poids | 483 Mo | ~1,5 Go |
| Vitesse sur ta machine | **~x0,5** du temps réel | x1,73 |
| Précision mathématique | égale, **avec le glossaire** | égale |

`small` est le modèle de travail : deux fois plus rapide que le temps réel, il
ne prendra jamais de retard sur ta dictée. `turbo` est conservé comme recours :
si un passage difficile résiste, tu peux le re-transcrire avec
`--model large-v3-turbo` en acceptant d'attendre.

---

## 16. Les six modules


Tout le code vit dans `src/audio2typst/`. Environ 1024 lignes au total.
Chaque module fait **une** chose.

### `capture.py` — le son (218 lignes)

Il fait trois choses.

**Enregistrer au micro.** `record_until_enter()` ouvre le micro et accumule le
son jusqu'à ce que tu appuies sur Entrée. Le son arrive par un *callback* :
la carte son appelle notre fonction toutes les 30 ms avec un nouveau morceau,
qu'on empile dans une file d'attente. C'est nécessaire parce que l'audio ne
peut pas attendre — si on ne vide pas le tampon assez vite, des morceaux sont
perdus.

**Lire et écrire des fichiers WAV.** `load_wav()` et `save_wav()`. Le WAV est
imposé à 16 000 Hz, mono, 16 bits — c'est exactement ce que Whisper attend, et
la fonction refuse tout autre format plutôt que de convertir en silence.

**Découper aux silences.** C'est la partie intéressante. `webrtcvad` répond à
une seule question : « cette tranche de 30 ms contient-elle de la parole ? ».
À partir de ça, un petit automate compte les tranches silencieuses consécutives
et applique **deux seuils différents** :

```
  … parole parole parole silence silence silence …
                          └────── 0,8 s ──────┘
                          → fin de SEGMENT : on l'envoie à Whisper

  … silence silence silence silence silence silence …
    └──────────────── 2,5 s ────────────────────┘
                          → fin de PARAGRAPHE : on envoie à Claude
```

Pourquoi deux seuils ? Parce que les deux outils veulent des choses opposées.
Whisper travaille mieux sur des bouts courts — une phrase, pas un monologue.
Claude, lui, a besoin de **contexte** : une phrase isolée est ambiguë
mathématiquement, un paragraphe entier ne l'est presque plus. Un seul seuil
aurait forcé à sacrifier l'un des deux.

L'automate est isolé dans une fonction (`_automate`) utilisée par deux
entrées : `segments_vad()` pour le micro, `segments_depuis_audio()` pour un
fichier. Cette seconde porte sert à **régler les seuils sans micro** — tu
rejoues un enregistrement autant de fois que nécessaire.

### `transcribe.py` — la reconnaissance vocale (128 lignes)

Il enveloppe `faster-whisper` et ajoute deux choses qui ne vont pas de soi.

**Le glossaire, passé en `initial_prompt`.** Whisper accepte un texte de
contexte qu'il traite comme « ce qui vient d'être dit ». Ça ne lui donne pas
d'ordre — ça biaise son décodage vers ce vocabulaire. Lui montrer le mot « pi »
avant de décoder rend « pi » plus probable que « p ». C'est tout le mécanisme,
et c'est ce qui rend le petit modèle utilisable (voir §6).

**Le filtre d'hallucination.** Whisper ne se tait jamais. Sur du silence ou du
bruit, il produit des phrases vues pendant son entraînement — et comme il a été
entraîné sur des sous-titres de vidéos, ce sont des génériques. Constaté ici sur
4 secondes de bruit rose :

> « Sous-titres réalisés par la communauté d'Amara.org »

`est_hallucination()` reconnaît ces motifs et vide le texte. Il est prudent :
une phrase **longue** contenant « sous-titrage » est conservée, parce qu'elle
peut être du vrai contenu que tu as dicté.

La classe `Transcriber` charge le modèle **une fois** et le réutilise. Le
chargement prend quelques secondes ; le refaire à chaque segment serait absurde.

### `structure.py` — le pont vers Claude (143 lignes)

C'est le module le moins évident, alors voici le mécanisme complet.

**On ne passe pas par l'API Claude.** On lance le programme `claude` — le même
que tu utilises dans ton terminal — en mode « sans interface » :

```bash
claude --print --input-format stream-json --output-format stream-json …
```

Il lit des messages JSON sur son entrée standard et répond en JSON sur sa
sortie. C'est un tuyau : on écrit une ligne, on lit la réponse.

**Le processus ne meurt jamais.** C'est le point crucial, et il a été établi par
la mesure. Chaque démarrage de `claude` coûte environ 10 000 tokens de contexte
d'amorçage. En gardant **un seul processus** vivant pour toute la session :

| | amorçage à payer |
|---|---|
| 1ᵉʳ paragraphe | 8 866 tokens |
| 2ᵉ paragraphe | 1 370 |
| 3ᵉ paragraphe | **151** |

Relancer le processus à chaque paragraphe, ou reprendre la session avec
`--resume`, repaie les 10 000 à chaque fois. C'est pour ça que `SessionClaude`
s'utilise comme un gestionnaire de contexte (`with …`) qui englobe toute la
dictée.

**La conversation *est* le document.** Conséquence directe : on n'envoie que le
nouveau passage, jamais le document. Claude se souvient de ce qu'il a écrit
parce que c'est dans l'historique de la conversation.

**Sauf quand tu as édité le fichier à la main.** Là, la mémoire de Claude et le
disque divergent, et sans rien faire le passage suivant écraserait ta
correction. D'où le mécanisme d'autorité, décrit en §7.

### `session.py` — l'état sur le disque (70 lignes)

Une session, c'est un dossier :

```
sessions/cours-optimisation/
├── document.typ          le document courant
├── document.pdf          sa compilation
├── transcriptions.jsonl  le texte brut horodaté
└── .empreinte            une signature du document (voir §7)
```

`transcriptions.jsonl` mérite une explication : il garde **le texte brut avant
toute interprétation**, une ligne JSON par paragraphe, horodatée. C'est ton
filet. Si Claude part de travers sur un passage, tu retrouves ce que Whisper
avait réellement entendu, et tu peux repartir de là.

### `compile.py` — Typst vers PDF (30 lignes)

Trente lignes, mais un choix de conception : la fonction **ne lève jamais
d'erreur**. Elle retourne un objet qui contient soit le PDF, soit le message
d'erreur du compilateur.

Pourquoi ? Parce que ce message est une donnée utile. Quand Typst dit
`unknown variable: fonction_inexistante`, on peut renvoyer ça à Claude pour
qu'il corrige lui-même. Une exception aurait interrompu la dictée ; une valeur
de retour permet de rattraper.

### `cli.py` — l'interface (430 lignes)

Il assemble tout et expose sept commandes (§18). C'est aussi lui qui contient la
boucle de dictée continue et la logique de resynchronisation.

---

## 17. Les deux mécanismes clés


Le document vit dans la conversation Claude. Tu peux pourtant l'éditer à la
main. Voici comment les deux cohabitent.

**À chaque écriture**, on calcule une empreinte SHA-256 du document et on la
range dans `.empreinte`. C'est une signature : si un seul caractère change,
l'empreinte change du tout au tout.

**Avant chaque envoi**, on recalcule l'empreinte du fichier sur le disque et on
la compare à celle qu'on avait rangée.

- **Identiques** → personne n'a touché au fichier. On envoie juste le nouveau
  passage. Rapide et peu coûteux.
- **Différentes** → tu as édité. On envoie alors le document réel dans un bloc
  `<document_autoritaire>`, avec une consigne claire dans le prompt système :
  *ce bloc remplace ta mémoire, même là où il te contredit*.

Un troisième cas est couvert : **reprendre une session plus tard**. Le fichier
n'a pas changé, donc l'empreinte correspond — mais le nouveau processus Claude
a une conversation vide et ne connaît pas le document. On le réinjecte donc
d'office au premier passage d'une session reprise.

Vérifié en pratique : après avoir remplacé à la main une somme par la notation
`zeta(2)` et ajouté un titre, le passage suivant a conservé les deux et **n'est
pas revenu** à la notation que Claude avait choisie.

---

---
---

# Partie V — Référence

## 18. Les sept commandes


### `importer` — un enregistrement déjà fait

C'est la commande à utiliser si tu dictes au téléphone plutôt qu'au micro du PC.

```bash
.venv/bin/audio2typst importer "New Recording 3.m4a" --session cours-3
```

Elle fait exactement ce que fait `live`, mais sur un fichier : conversion du
format, découpage aux silences, transcription, envoi à Claude paragraphe par
paragraphe, compilation du PDF. **Tu n'as rien à préparer** — ni à convertir le
fichier, ni à créer la session.

**Tous les formats passent.** m4a, mp3, wav, opus, ogg… et n'importe quelle
fréquence d'échantillonnage. Si le fichier n'est pas déjà du WAV 16 kHz mono,
ffmpeg le convertit en arrière-plan, dans un dossier temporaire — ton fichier
d'origine n'est jamais modifié.

**L'avancement s'affiche** en pourcentage de la durée, parce qu'un enregistrement
de dix minutes demande environ cinq minutes de transcription.

**Garde-fou sur les longs monologues.** Si tu parles sans marquer de vraie pause,
aucun paragraphe ne se déclenche et Claude recevrait un pavé. Au-delà de
1 200 caractères accumulés, l'envoi se fait quand même, avec la mention
`(pas de pause détectée — envoi sur volume)`.

Mêmes options que `live` : `--silence-paragraphe`, `--model`, `--claude-model`.

### `live` — la dictée continue

La même chose, en direct depuis le micro du PC.

```bash
.venv/bin/audio2typst live --session cours-optimisation
```

Le micro s'ouvre et reste ouvert. Tu parles normalement. Chaque bout de phrase
reconnu s'affiche au terminal pendant que tu continues à parler. Quand tu
marques une pause de plus de 2,5 secondes, le bloc accumulé part chez Claude,
le document se met à jour, le PDF se recompile.

**Entrée** met en pause : le micro est ignoré jusqu'à ce que tu appuies de
nouveau, et ton tampon en cours reste intact. **Ctrl-C** termine et envoie ce
qui restait en tampon.

| Option | Effet |
|---|---|
| `--session NOM` | nom du dossier de session (défaut : horodaté) |
| `--silence-paragraphe 3.5` | attendre plus longtemps avant d'envoyer à Claude |
| `--silence-segment 0.5` | découper plus finement pour Whisper |
| `--model large-v3-turbo` | modèle Whisper plus précis, plus lent |
| `--claude-model opus` | modèle Claude plus puissant, consomme plus de quota |
| `--device 0` | forcer un micro précis (les lister : voir §10) |

### `compiler` — recompiler après une retouche manuelle

**Les passages dictés recompilent le PDF tout seuls. Une retouche que tu fais
dans ton éditeur, non.** Voir le §8 pour la marche à suivre complète.

Une passe ponctuelle :

```bash
.venv/bin/audio2typst compiler --session CL
```

La surveillance continue, qui régénère le PDF à chaque sauvegarde :

```bash
.venv/bin/audio2typst compiler --session CL --suivre
```

| Option | Effet |
|---|---|
| `--session NOM` | recompile `sessions/NOM/document.typ` |
| *(argument positionnel)* | vise un `.typ` quelconque, hors session |
| `--suivre` | recompile à chaque sauvegarde du fichier |
| `--intervalle 0.5` | période de vérification en mode `--suivre` |

Une erreur de syntaxe n'interrompt pas la surveillance : le message s'affiche et
la boucle continue d'attendre.

### `dicter` — un passage à la fois

```bash
.venv/bin/audio2typst dicter                      # micro, Entrée pour arrêter
.venv/bin/audio2typst dicter enregistrement.wav   # depuis un fichier
.venv/bin/audio2typst dicter --confirmer          # avec relecture du texte brut
```

Pas de VAD : tu contrôles le début et la fin. Utile pour un passage isolé, ou
quand tu veux **relire le texte brut avant qu'il parte** chez Claude, avec
`--confirmer`. Corriger du français est plus sûr que corriger du Typst.

### `transcribe` — la reconnaissance seule

```bash
.venv/bin/audio2typst transcribe enregistrement.wav
```

Pas de Claude, pas de PDF. Sert à vérifier ce que Whisper entend, sans
consommer de quota.

### `bench` — comparer les modèles

```bash
.venv/bin/audio2typst bench enregistrement.wav
```

Passe le même fichier dans `small` et `large-v3-turbo`, affiche pour chacun le
temps, le rapport au temps réel et la transcription. C'est ce qui a servi à
choisir `small`. Relance-le quand tu changes de type de contenu.

### `record` — enregistrer et transcrire

```bash
.venv/bin/audio2typst record --save echantillon.wav
```

Capture au micro, transcrit, et conserve le WAV. Pratique pour se constituer des
échantillons de test réutilisables.

---

## 19. Dépannage


**« Aucun son n'est capté. »** Liste les micros :

```bash
.venv/bin/python -c "import sounddevice as sd; print(sd.query_devices())"
```

Puis force celui qui convient avec `--device N`.

**« Claude est appelé au milieu de mes phrases. »** Tes pauses de réflexion
dépassent le seuil. `--silence-paragraphe 3.5`.

**« Claude attend trop, il avale trois idées d'un coup. »** L'inverse :
`--silence-paragraphe 1.8`.

**« Des phrases bizarres apparaissent sur du silence. »** Ce sont des
hallucinations de Whisper. Le filtre en attrape les formes connues ; si une
nouvelle apparaît, ajoute son motif dans `HALLUCINATIONS`, au début de
`transcribe.py`.

**« J'ai corrigé le .typ mais le PDF n'a pas changé. »** Normal : seules les
dictées recompilent. Lance `audio2typst compiler --session NOM`, ou `--suivre`
pour qu'il se régénère à chaque sauvegarde (§8).

**« Le PDF ne se génère pas. »** Claude a produit du Typst invalide. Le système
tente **une** correction automatique en lui renvoyant l'erreur du compilateur.
Si ça échoue, le `.typ` reste sur le disque — corrige-le à la main, la session
continue.

**« Ça consomme trop de quota. »** Chaque paragraphe est un appel. Augmente
`--silence-paragraphe` pour en faire moins et de plus gros, et reste sur
Sonnet (le défaut) plutôt qu'Opus. Évite aussi de multiplier les pauses de
plusieurs minutes : chacune coûte un réamorçage de contexte (§9).

**⚠️ Ne définis jamais `ANTHROPIC_API_KEY`.** Si cette variable existe dans ton
environnement, Claude Code arrête d'utiliser ton abonnement et bascule en
facturation par token. Vérifier :

```bash
echo "${ANTHROPIC_API_KEY:-non définie}"
```

---

## 20. Ce qui reste à faire


**Une validation, prioritaire.** Le choix du modèle `small` repose sur
13 secondes d'audio et une seule formule. C'est mince. Une dictée réelle de
plusieurs minutes le confirmera — ou le remettra en cause.

**Deux questions techniques ouvertes.**

*Le coût croît avec la taille du document*, puisque toute la conversation est
relue à chaque tour. Sur un document de plusieurs pages, il faudra choisir entre
continuer à réécrire le document entier et passer à des modifications ciblées.

*Corriger le texte brut en dictée continue* n'est pas possible : `--confirmer`
n'existe que sur `dicter`, parce qu'une invite bloquante interromprait le flux.

**Trois questions que seul l'usage tranchera.** Une relecture globale par Claude
en fin de session serait-elle utile pour harmoniser numérotation et style ? À
quoi reconnaîtras-tu que la conversion mathématique est assez bonne ? Et qu'est-ce
qui te ferait abandonner le projet ?

---

## 21. Résumé en une page


| Question | Réponse |
|---|---|
| Où est le code ? | `src/audio2typst/`, six modules, ~1020 lignes |
| Où sont les bibliothèques ? | `.venv/`, 513 Mo, hors git |
| Où sont les modèles Whisper ? | `~/.cache/huggingface/`, 2 Go, hors du projet |
| Où sont mes documents ? | `sessions/<nom>/`, hors git |
| Qu'est-ce qui tourne en local ? | micro, VAD, Whisper, Typst |
| Qu'est-ce qui sort de la machine ? | le texte transcrit, vers Claude. Jamais l'audio. |
| Comment c'est facturé ? | ton abonnement Claude Code, via le CLI `claude` |
| La commande à retenir (téléphone) | `.venv/bin/audio2typst importer fichier.m4a --session mon-cours` |
| La commande à retenir (micro PC) | `.venv/bin/audio2typst live --session mon-cours` |
| Le fichier à soigner | `glossaire-maths.txt` |
