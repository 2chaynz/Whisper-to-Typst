"""Capture micro. Étape 1 : start/stop manuel, pas encore de VAD."""

from __future__ import annotations

import queue
import sys
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

from . import SAMPLE_RATE


def record_until_enter(device: int | None = None) -> np.ndarray:
    """Enregistre au micro jusqu'à ce que l'utilisateur appuie sur Entrée.

    Retourne du float32 mono à 16 kHz, directement consommable par Whisper.
    """
    blocks: queue.Queue[np.ndarray] = queue.Queue()

    def on_audio(indata, frames, time_info, status):
        if status:
            print(f"[audio] {status}", file=sys.stderr)
        blocks.put(indata.copy())

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        device=device,
        callback=on_audio,
    )
    with stream:
        print("● Enregistrement… (Entrée pour arrêter)", flush=True)
        input()

    chunks = []
    while not blocks.empty():
        chunks.append(blocks.get())
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(chunks).reshape(-1)


def load_wav(path: str | Path) -> np.ndarray:
    """Charge un WAV PCM 16 bits mono en float32, en vérifiant le taux."""
    with wave.open(str(path), "rb") as w:
        if w.getnchannels() != 1:
            raise ValueError(f"{path} : attendu mono, trouvé {w.getnchannels()} canaux")
        if w.getsampwidth() != 2:
            raise ValueError(f"{path} : attendu PCM 16 bits")
        if w.getframerate() != SAMPLE_RATE:
            raise ValueError(
                f"{path} : attendu {SAMPLE_RATE} Hz, trouvé {w.getframerate()} Hz"
            )
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def save_wav(audio: np.ndarray, path: str | Path) -> Path:
    """Écrit du float32 mono en WAV PCM 16 bits (utile pour rejouer un segment)."""
    path = Path(path)
    pcm = np.clip(audio, -1.0, 1.0)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes((pcm * 32767).astype(np.int16).tobytes())
    return path


# --- Découpage automatique par détection de silence -------------------------

# webrtcvad n'accepte que des trames de 10, 20 ou 30 ms.
DUREE_TRAME_MS = 30
TAILLE_TRAME = SAMPLE_RATE * DUREE_TRAME_MS // 1000

# Deux seuils, parce que deux découpages différents cohabitent (décision A5) :
# le premier borne ce qu'on donne à Whisper, le second ce qu'on donne à Claude.
SILENCE_SEGMENT_S = 0.8
SILENCE_PARAGRAPHE_S = 2.5

# Agressivité webrtcvad : 0 laisse passer le bruit, 3 coupe la parole faible.
# 2 est le compromis usuel pour un micro de portable en intérieur.
AGRESSIVITE_VAD = 2


def _automate(trames, seuil_seg: int, seuil_par: int, vad) -> "object":
    """Automate de découpage, commun au micro et au fichier.

    Consomme des trames de `TAILLE_TRAME` échantillons, produit
    `(audio, fin_de_paragraphe)`. Isolé du flux audio pour être testable.
    """
    courant: list[np.ndarray] = []
    silence = 0
    segment_en_attente = False

    for trame in trames:
        if len(trame) != TAILLE_TRAME:
            continue
        pcm = (np.clip(trame, -1.0, 1.0) * 32767).astype(np.int16)

        if vad.is_speech(pcm.tobytes(), SAMPLE_RATE):
            courant.append(trame)
            silence = 0
            continue

        silence += 1
        if courant:
            # Couper net sur la dernière syllabe dégrade la transcription :
            # on laisse déborder le silence dans le segment.
            courant.append(trame)

        if courant and silence >= seuil_seg:
            yield np.concatenate(courant), False
            courant = []
            segment_en_attente = True
        elif segment_en_attente and silence >= seuil_par:
            segment_en_attente = False
            yield np.zeros(0, dtype=np.float32), True

    if courant:
        yield np.concatenate(courant), True


def _seuils(silence_segment: float, silence_paragraphe: float) -> tuple[int, int]:
    trames_par_s = SAMPLE_RATE / TAILLE_TRAME
    return int(silence_segment * trames_par_s), int(silence_paragraphe * trames_par_s)


def segments_depuis_audio(
    audio: np.ndarray,
    silence_segment: float = SILENCE_SEGMENT_S,
    silence_paragraphe: float = SILENCE_PARAGRAPHE_S,
    agressivite: int = AGRESSIVITE_VAD,
):
    """Même découpage, appliqué à un tableau déjà en mémoire.

    Sert à régler les seuils sur un enregistrement réel, sans micro ni
    chronomètre : on rejoue la dictée autant de fois qu'il faut.
    """
    import webrtcvad

    seuil_seg, seuil_par = _seuils(silence_segment, silence_paragraphe)
    trames = (audio[i:i + TAILLE_TRAME] for i in range(0, len(audio), TAILLE_TRAME))
    yield from _automate(trames, seuil_seg, seuil_par, webrtcvad.Vad(agressivite))


def segments_vad(
    device: int | None = None,
    silence_segment: float = SILENCE_SEGMENT_S,
    silence_paragraphe: float = SILENCE_PARAGRAPHE_S,
    agressivite: int = AGRESSIVITE_VAD,
):
    """Écoute en continu et produit `(audio, fin_de_paragraphe)`.

    `fin_de_paragraphe` indique qu'un silence long a suivi : l'appelant doit
    alors vider son tampon vers Claude. Boucle jusqu'à KeyboardInterrupt.
    """
    import webrtcvad

    trames: queue.Queue[np.ndarray] = queue.Queue()

    def on_audio(indata, frames, time_info, status):
        if status:
            print(f"[audio] {status}", file=sys.stderr)
        trames.put(indata.copy().reshape(-1))

    seuil_seg, seuil_par = _seuils(silence_segment, silence_paragraphe)
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="float32",
        device=device, blocksize=TAILLE_TRAME, callback=on_audio,
    )
    with stream:
        yield from _automate(iter(trames.get, None), seuil_seg, seuil_par,
                             webrtcvad.Vad(agressivite))
