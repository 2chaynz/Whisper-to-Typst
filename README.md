# audio2typst

Dictée vocale française — prose et mathématiques mêlées — vers un document
Typst structuré, en syntaxe native.

```
micro → VAD → Whisper (local) → Claude → .typ → PDF
```

## Installation

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Aucune toolchain Rust n'est nécessaire : le compilateur Typst arrive par pip.
La structuration passe par le CLI `claude` (mode headless), donc par un
abonnement Claude Code — pas par une clé API.

> **Ne définissez pas `ANTHROPIC_API_KEY`.** Si la variable est présente,
> Claude Code bascule en facturation par token au lieu d'utiliser l'abonnement.

## Usage

```bash
audio2typst importer enregistrement.m4a # un fichier déjà enregistré (téléphone…)
audio2typst live                        # dictée continue au micro
audio2typst dicter                      # un passage, start/stop manuel
audio2typst bench fichier.wav           # compare les modèles Whisper
```

`importer` accepte tous les formats — m4a, mp3, wav, opus — et les convertit
lui-même. C'est le mode à privilégier si vous dictez au téléphone : sans
contrainte de temps réel, vous pouvez utiliser le modèle le plus précis
(`--model large-v3-turbo`).

Un silence court clôt un segment pour Whisper ; un silence long (2,5 s par
défaut) envoie le bloc accumulé à Claude. Les deux seuils se règlent avec
`--silence-segment` et `--silence-paragraphe`, en direct comme à l'import.

En dictée continue, **Entrée** met le micro en pause et **Ctrl-C** termine.

## Le glossaire n'est pas optionnel

`glossaire-maths.txt` est passé à Whisper en `initial_prompt` et biaise la
reconnaissance vers le vocabulaire mathématique. Mesuré sur le modèle `small` :

| | sans glossaire | avec glossaire |
|---|---|---|
| « pi carré sur 6 » | `p² sur 6` | `pi carré sur 6` |
| « à l'infini » | `l'infinie` | `l'infini` |

Sans lui, les formules sont silencieusement fausses. Ajoutez-y votre propre
vocabulaire, un terme par ligne.

## Corriger

Le document accumulé vit dans la conversation avec Claude. Vous pouvez tout de
même éditer `sessions/<nom>/document.typ` à la main : la modification est
détectée par empreinte et réinjectée comme faisant autorité, donc vos choix de
notation survivent aux passages suivants.

`--confirmer` (commande `dicter`) permet de corriger le texte brut avant qu'il
parte chez Claude — corriger du texte est plus sûr que corriger du Typst.

## Session

```
sessions/<nom>/
├── document.typ          le document courant
├── document.pdf
└── transcriptions.jsonl  texte brut horodaté, avant toute interprétation
```

Le journal brut permet de revenir en arrière quand une structuration part de
travers.

## Licence

MIT.
# Whipser-to-Typst
