# audio2typst — Plan technique

Pipeline open source : dictée vocale (français, contenu mathématique dense) → document Typst structuré, en syntaxe native.

## 1. Problème et positionnement

Aucun projet existant ne couvre ce cas d'usage précisément :

- Les outils "speech-to-LaTeX" existants (voir §2) ne traitent que des **équations isolées** dictées une par une, pas un document complet mêlant prose et maths.
- Aucun ne vise **Typst** — tout le monde cible LaTeX.
- La dictée manuscrite parlée de maths reste un problème difficile : les meilleurs modèles académiques publiés en 2025 affichent encore 27–40% de taux d'erreur caractère sur des équations isolées (papier *Speech-to-LaTeX*, voir §2). Un mécanisme de correction humaine léger est donc une nécessité structurelle du pipeline, pas un nice-to-have.

Le projet vise : dicter une explication orale libre (cours, réflexion personnelle) et obtenir un `.typ` structuré (prose + maths en syntaxe Typst native), avec relecture/correction possible à chaque étape.

## 2. Prior art étudié

| Projet | Approche | Lien |
|---|---|---|
| Thomas-McKanna/speech-to-latex | Whisper Web (WASM) + WebLLM (LLM local navigateur) + MathJax, 100% client-side | https://github.com/Thomas-McKanna/speech-to-latex |
| dkorzh10/speech2latex | Dataset + benchmark académique (66k échantillons audio annotés), compare post-correction ASR / few-shot / audio-LLM natifs | https://github.com/dkorzh10/speech2latex (papier arXiv:2508.03542) |
| hsahovic/Speech-to-maths | Grammaire CMU Sphinx contrainte + parsing d'arbre de formule (algo de Myers) + modèle ML de désambiguïsation par utilisateur/document | https://github.com/hsahovic/Speech-to-maths |
| mirober/mathfly | Dictée Dragon NaturallySpeaking (payant) + vocabulaire de commandes ("begin fraction", "over", templates d'environnements LaTeX) | https://github.com/mirober/mathfly |
| wolf-whisper, WhiLa | POC expérimentaux Whisper + couche LLM/symbolique pour LaTeX, non maintenus | github.com/kwazzi-jack/wolf-whisper, pypi.org/project/whila |

Alternative envisagée et écartée : le package Typst `mitex`, qui permet d'embarquer directement de la syntaxe LaTeX dans un document Typst sans conversion. Écarté au profit de la génération de syntaxe Typst native, car Claude dispose déjà de skills Typst/CeTZ dans l'environnement cible — la génération native est donc viable sans dépendance supplémentaire, et cohérente avec le style Typst déjà en usage.

## 3. Décisions d'architecture (verrouillées)

| Décision | Choix retenu | Raison |
|---|---|---|
| Plateforme | Hybride : ASR local + Claude API | ASR local = gratuit/privé/rapide ; Claude API = seule option qui exploite les skills Typst/CeTZ pour une syntaxe native fiable |
| Représentation des maths | Syntaxe Typst native générée directement | Permise par les skills Claude disponibles ; plus cohérente avec le style Typst déjà utilisé (pas de dépendance `mitex`) |
| Mode de dictée | Libre — prose et maths mélangées, un seul passage LLM | Correspond à l'usage réel (explication calme après coup) ; pas de charge mentale de "mode" à gérer en parlant |
| Granularité | Par segments, document qui s'accumule progressivement | Isole les erreurs (vs. tout envoyer d'un coup) ; correspond au pattern de travail déjà en usage (explication → bout de Typst → suivante) |
| Délimitation des segments | VAD (détection automatique de silence) | Dictée en continu sans interruption manuelle |
| Contexte envoyé à Claude | Le `.typ` déjà généré + le nouveau texte brut, à chaque appel | Cohérence de style/numérotation ; Claude peut ajuster ce qui précède si besoin |
| Glossaire technique | Fichier optionnel par session, passé en `initial_prompt` à Whisper | Améliore la reconnaissance du vocabulaire pointu (ex: "lagrangien", "epsilon-delta") avant même d'arriver chez Claude |
| Modèle Whisper | `medium`, multilingue (pas `.en`) | Bon compromis précision/latence pour de l'audio propre solo en français ; le surcoût de latence ne se sent pas en traitement par segments |
| Langage d'implémentation | Python | Prototypage rapide, écosystème riche (audio, bindings whisper.cpp, SDK Anthropic), cohérent avec un usage en Claude Code |
| Point de correction | Texte brut éditable avant envoi à Claude (défaut) ; `.typ` éditable à la main ensuite comme n'importe quel fichier | Corriger du texte brut est sûr ; corriger du Typst généré risque de casser la syntaxe |

## 4. Pipeline

```
Micro (capture continue)
   → VAD : détection de silence → fin de segment
   → whisper.cpp (modèle medium, fr, initial_prompt = glossaire session) → texte brut
   → [point de correction optionnel : édition rapide du texte brut]
   → API Claude : { .typ accumulé jusqu'ici + nouveau texte brut } → .typ mis à jour
     (structuration prose + conversion maths en syntaxe Typst native)
   → écriture du .typ sur disque → `typst compile` → PDF
   → retour à l'écoute pour le segment suivant
```

## 5. Stack technique

- **Capture audio** : `sounddevice` (léger, cross-platform, marche bien sous Linux)
- **VAD** : `webrtcvad` pour la v1 (simple, CPU-only, pas de modèle à télécharger) ; upgrade possible vers `silero-vad` (modèle ML léger, plus précis) si la segmentation déçoit en pratique
- **ASR** : binding Python de whisper.cpp — `pywhispercpp` de préférence à un `subprocess` avec fichiers temporaires (plus propre, moins d'I/O disque)
- **Structuration** : SDK officiel `anthropic` (Python)
- **Rendu** : binaire `typst` en CLI (`cargo install typst-cli`, ou binaire précompilé — gratuit, open source), appelé en sous-processus pour compiler `.typ` → PDF
- **État de session** : un dossier par session contenant le `.typ` courant, le glossaire, et un log des transcriptions brutes horodatées (utile pour debug, et pour revenir en arrière si Claude part dans une mauvaise direction sur un segment)

## 6. Structure de repo proposée

```
audio2typst/
├── README.md
├── LICENSE                        # MIT — cohérent avec le prior art étudié
├── pyproject.toml
├── src/audio2typst/
│   ├── capture.py                 # micro + VAD, découpage en segments
│   ├── transcribe.py              # wrapper whisper.cpp, gestion glossaire (initial_prompt)
│   ├── structure.py               # appel Claude, gestion du contexte doc accumulé
│   ├── session.py                 # état de session (.typ courant, historique segments)
│   ├── compile.py                 # wrapper `typst compile`
│   └── cli.py                     # point d'entrée
├── prompts/
│   └── system_prompt.md           # prompt de structuration Typst (voir §7)
└── sessions/                      # sessions générées (gitignored)
```

## 7. Ébauche de prompt système (structure.py)

Point de départ à affiner en pratique — à adapter avec le contenu des skills `typst` et `typst-cetz` :

```
Tu reçois :
1. Le contenu actuel d'un document Typst en cours de rédaction (peut être vide en début de session).
2. Un nouveau texte brut, transcrit depuis une dictée orale en français, mêlant prose
   explicative et description parlée d'expressions mathématiques.

Ta tâche : produire le document Typst mis à jour, en intégrant le nouveau texte.

Règles :
- Convertis les descriptions mathématiques parlées en syntaxe Typst native
  (ex: "x carré plus un sur x moins un" → $x^2 + 1 / (x - 1)$ ou la forme
  Typst la plus idiomatique selon le contexte — pas de LaTeX, pas de mitex).
- Garde la prose proche du sens de ce qui a été dit, reformulée proprement,
  sans en changer le fond.
- Maintiens la cohérence de style et de structure (titres, numérotation) avec
  le document existant.
- Si une phrase est ambiguë mathématiquement, choisis l'interprétation la plus
  probable dans le contexte, et n'hésite pas à signaler l'ambiguïté en commentaire
  Typst (//) plutôt que de deviner silencieusement.
- Ne renvoie que le document Typst complet mis à jour, rien d'autre.
```

## 8. Feuille de route

1. **Squelette sans VAD** — start/stop manuel → whisper.cpp → texte brut affiché en terminal. Valide juste la chaîne audio + ASR.
2. **Ajout Claude** — texte brut → un appel API simple → premier `.typ` généré et compilé. Valide la chaîne complète sur un segment isolé.
3. **Contexte accumulé** — un deuxième segment est envoyé avec le `.typ` existant en contexte ; vérifier la cohérence de l'insertion.
4. **Glossaire** — biaiser Whisper via `initial_prompt` à partir d'un fichier de vocabulaire.
5. **VAD** — remplace le start/stop manuel par la segmentation automatique en continu (`webrtcvad`).
6. **Polish** — gestion d'erreurs (API indisponible, silence anormalement long, coupure au milieu d'une phrase), packaging (`pyproject.toml`, entry point CLI), README utilisateur.

## 9. Points ouverts (à trancher en implémentation)

- Seuil exact de silence (en secondes) pour clore un segment côté `webrtcvad`.
- Contenu précis et itération du prompt système Claude — notamment comment référencer explicitement les skills `typst`/`typst-cetz` disponibles dans l'environnement Claude Code.
- Faut-il une passe de relecture finale par Claude sur tout le document en fin de session, pour la cohérence globale (numérotation, style) ?
- Format exact du fichier de glossaire (liste brute vs. structuré par thème/session) et sa persistance entre sessions.
- Gestion des erreurs de compilation Typst (si Claude génère une syntaxe invalide) — retry automatique avec le message d'erreur du compilateur en contexte ?
