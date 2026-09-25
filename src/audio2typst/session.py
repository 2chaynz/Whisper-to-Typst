"""État d'une session de dictée : document courant, journal des transcriptions.

Le journal brut horodaté n'est pas du confort de débogage : c'est le filet de
sécurité quand Claude part dans une mauvaise direction sur un passage. Le texte
reconnu est conservé tel quel, avant toute interprétation.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from pathlib import Path

RACINE_DEFAUT = Path("sessions")


class Session:
    def __init__(self, nom: str | None = None, racine: Path = RACINE_DEFAUT) -> None:
        self.nom = nom or _dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.dossier = racine / self.nom
        self.dossier.mkdir(parents=True, exist_ok=True)
        self.typ = self.dossier / "document.typ"
        self.journal = self.dossier / "transcriptions.jsonl"
        # Empreinte du document tel que *nous* l'avons écrit. Tout écart signale
        # une édition faite à la main entre deux passages.
        self._empreinte = self.dossier / ".empreinte"
        if not self.typ.exists():
            self.typ.write_text("", encoding="utf-8")

    @property
    def document(self) -> str:
        return self.typ.read_text(encoding="utf-8")

    def edition_externe(self) -> str | None:
        """Retourne le document si l'utilisateur l'a modifié hors de notre dos.

        Le document accumulé vit dans la conversation Claude ; une édition faite
        dans un éditeur lui est invisible et serait écrasée au passage suivant.
        On la détecte ici pour pouvoir resynchroniser au lieu de la perdre.
        """
        if not self._empreinte.exists():
            return None
        actuel = self.document
        if _signature(actuel) == self._empreinte.read_text(encoding="utf-8").strip():
            return None
        return actuel

    def enregistrer_passage(self, texte_brut: str, document: str,
                            meta: dict | None = None) -> None:
        """Écrit le document à jour et journalise la transcription d'origine."""
        self.typ.write_text(document, encoding="utf-8")
        self._empreinte.write_text(_signature(document), encoding="utf-8")
        entree = {
            "horodatage": _dt.datetime.now().isoformat(timespec="seconds"),
            "texte_brut": texte_brut,
        }
        if meta:
            entree["meta"] = meta
        with self.journal.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entree, ensure_ascii=False) + "\n")

    def passages(self) -> list[dict]:
        if not self.journal.exists():
            return []
        return [json.loads(l) for l in self.journal.read_text(encoding="utf-8").splitlines() if l.strip()]


def _signature(texte: str) -> str:
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()
