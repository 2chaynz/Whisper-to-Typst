"""Structuration : texte brut dicté -> document Typst, via Claude.

Le backend est un processus `claude` à durée de vie longue, pas un appel par
passage. Mesuré sur cette machine : l'amorçage du contexte tombe de 8 866 à
151 tokens entre le premier et le troisième tour, et la latence de 2,5 s à 1,6 s.
Relancer le processus à chaque passage (ou reprendre la session avec `--resume`)
repaie l'amorçage à chaque fois.

Conséquence de design : la conversation *est* le document accumulé. On n'envoie
que le nouveau passage ; Claude renvoie le document complet à jour.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import TracebackType

PROMPT_SYSTEME = Path(__file__).resolve().parents[2] / "prompts" / "system_prompt.md"

# Sonnet suffit : la tâche est une transformation contrainte, la syntaxe Typst
# est fournie dans le prompt. Opus coûterait du quota pour un gain marginal.
MODELE_DEFAUT = "sonnet"

# Rien dans cette tâche ne justifie un accès disque ou réseau.
OUTILS_INTERDITS = ("Bash", "Read", "Write", "Edit", "Glob", "Grep",
                    "WebFetch", "WebSearch", "Task")


class ErreurStructuration(RuntimeError):
    pass


class SessionClaude:
    """Processus `claude` persistant. À utiliser comme gestionnaire de contexte."""

    def __init__(self, modele: str = MODELE_DEFAUT, prompt_systeme: Path | None = None) -> None:
        self.modele = modele
        chemin = prompt_systeme or PROMPT_SYSTEME
        if not chemin.exists():
            raise ErreurStructuration(f"prompt système introuvable : {chemin}")
        self._systeme = chemin.read_text(encoding="utf-8")
        self._proc: subprocess.Popen[str] | None = None
        self.dernier_usage: dict | None = None

    def __enter__(self) -> "SessionClaude":
        self._proc = subprocess.Popen(
            [
                "claude", "--print", "--verbose",
                "--input-format", "stream-json",
                "--output-format", "stream-json",
                "--model", self.modele,
                "--append-system-prompt", self._systeme,
                "--disallowed-tools", *OUTILS_INTERDITS,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None,
                 tb: TracebackType | None) -> None:
        self.fermer()

    def fermer(self) -> None:
        if self._proc is None:
            return
        try:
            if self._proc.stdin:
                self._proc.stdin.close()
            self._proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        finally:
            self._proc = None

    def structurer(self, passage: str, document_autoritaire: str | None = None) -> str:
        """Envoie un passage transcrit, retourne le document Typst complet à jour.

        `document_autoritaire` resynchronise Claude après une édition manuelle du
        fichier : sans lui, le tour suivant régénérerait depuis la mémoire de la
        conversation et écraserait silencieusement la correction.
        """
        if self._proc is None or self._proc.poll() is not None:
            raise ErreurStructuration("session Claude fermée ou morte")
        assert self._proc.stdin and self._proc.stdout

        corps = ""
        if document_autoritaire is not None:
            corps += ("<document_autoritaire>\n"
                      f"{document_autoritaire.rstrip()}\n"
                      "</document_autoritaire>\n\n")
        corps += f"<nouveau_passage>{passage}</nouveau_passage>"

        message = {
            "type": "user",
            "message": {"role": "user", "content": [{"type": "text", "text": corps}]},
        }
        self._proc.stdin.write(json.dumps(message) + "\n")
        self._proc.stdin.flush()

        while True:
            ligne = self._proc.stdout.readline()
            if not ligne:
                erreur = self._proc.stderr.read() if self._proc.stderr else ""
                raise ErreurStructuration(f"flux Claude interrompu. {erreur[:400]}")
            try:
                evenement = json.loads(ligne)
            except json.JSONDecodeError:
                continue
            if evenement.get("type") != "result":
                continue
            if evenement.get("is_error"):
                raise ErreurStructuration(str(evenement.get("result"))[:400])
            self.dernier_usage = evenement.get("usage")
            return _nettoyer(evenement["result"])


def _nettoyer(sortie: str) -> str:
    """Retire un éventuel bloc de code englobant.

    Le prompt l'interdit, mais un modèle finit toujours par en produire un et
    ces trois lignes coûtent moins cher qu'un document Typst qui ne compile pas.
    """
    texte = sortie.strip()
    if texte.startswith("```"):
        lignes = texte.splitlines()
        if lignes[-1].strip() == "```":
            texte = "\n".join(lignes[1:-1])
    return texte.strip() + "\n"
