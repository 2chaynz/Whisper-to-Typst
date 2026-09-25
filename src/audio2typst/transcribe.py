"""Wrapper faster-whisper : audio -> texte brut français, biaisé par un glossaire."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

# Sur CPU sans GPU, int8 est le seul compromis viable : float32 multiplie
# le temps de décodage par 3 à 4 pour un gain de précision marginal.
DEFAULT_MODEL = "small"
DEFAULT_COMPUTE = "int8"

# Sur du non-parlé, Whisper ne se tait pas : il restitue des phrases vues à
# l'entraînement, majoritairement des génériques de sous-titres. Le VAD en
# écarte l'essentiel, ces motifs rattrapent le reste. Constaté ici sur 4 s de
# bruit rose : « Sous-titres réalisés par la communauté d'Amara.org ».
HALLUCINATIONS = (
    "sous-titres realises par",
    "sous-titrage",
    "soustitreur",
    "amara.org",
    "merci d'avoir regarde",
    "merci a tous",
    "abonnez-vous",
    "a bientot",
)


def _normaliser(texte: str) -> str:
    import unicodedata
    sans_accent = "".join(
        c for c in unicodedata.normalize("NFD", texte.lower())
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(sans_accent.split())


def est_hallucination(texte: str) -> bool:
    """Vrai si la transcription est un artefact de non-parlé plutôt que du contenu."""
    norme = _normaliser(texte)
    if not norme or norme in {".", "...", "merci", "merci."}:
        return True
    # Court ET reconnaissable : une phrase longue qui contient « sous-titrage »
    # peut être du vrai contenu dicté.
    return len(norme) < 120 and any(motif in norme for motif in HALLUCINATIONS)


@dataclass
class Transcription:
    text: str
    language: str
    duration_audio: float
    duration_wall: float

    @property
    def realtime_factor(self) -> float:
        """< 1 = plus rapide que le temps réel. C'est le chiffre qui décide de B1."""
        if self.duration_audio == 0:
            return float("inf")
        return self.duration_wall / self.duration_audio


def load_glossary(path: str | Path | None) -> str | None:
    """Le glossaire devient l'`initial_prompt` de Whisper.

    Whisper le traite comme du contexte précédent, pas comme une consigne : une
    simple liste de termes suffit à biaiser le décodage vers ce vocabulaire.

    Ce n'est pas un agrément. Mesuré sur `small` : sans glossaire, "pi carré"
    est transcrit "p²" et la formule est silencieusement fausse ; avec, la
    transcription égale celle de `large-v3-turbo` pour un tiers du temps.
    """
    if path is None:
        return None
    path = Path(path)
    if not path.exists():
        return None
    terms = [
        ligne.strip()
        for ligne in path.read_text(encoding="utf-8").splitlines()
        if ligne.strip() and not ligne.lstrip().startswith("#")
    ]
    return ", ".join(terms) if terms else None


class Transcriber:
    """Charge le modèle une seule fois et le réutilise sur tous les segments."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        compute_type: str = DEFAULT_COMPUTE,
        glossary: str | None = None,
        cpu_threads: int = 0,
    ) -> None:
        self.model_name = model_name
        self.glossary = glossary
        self._model = WhisperModel(
            model_name,
            device="cpu",
            compute_type=compute_type,
            cpu_threads=cpu_threads,  # 0 = laisse CTranslate2 décider
        )

    def transcribe(self, audio: np.ndarray) -> Transcription:
        start = time.perf_counter()
        segments, info = self._model.transcribe(
            audio,
            language="fr",
            initial_prompt=self.glossary,
            beam_size=5,
            # Chaque segment est déjà une unité de sens ; rechaîner sur le texte
            # précédent fait boucler Whisper sur ses propres hallucinations.
            condition_on_previous_text=False,
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        if est_hallucination(text):
            text = ""
        return Transcription(
            text=text,
            language=info.language,
            duration_audio=info.duration,
            duration_wall=time.perf_counter() - start,
        )
