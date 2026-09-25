"""Point d'entrée CLI. Étape 1 : audio -> texte brut. Claude arrive à l'étape 2."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .capture import load_wav, record_until_enter, save_wav, segments_vad
from .compile import compiler
from .session import Session
from .structure import ErreurStructuration, SessionClaude
from .transcribe import Transcriber, load_glossary

# Les deux candidats retenus pour un CPU 4 threads sans GPU.
# `medium` est écarté : ~2 à 3x le temps réel sur cette machine.
BENCH_MODELS = ("small", "large-v3-turbo")

# Chargé d'office : sans lui, `small` corrompt les symboles mathématiques.
GLOSSAIRE_PAR_DEFAUT = Path("glossaire-maths.txt")


def glossaire_effectif(choisi: Path | None) -> Path | None:
    if choisi is not None:
        return choisi
    return GLOSSAIRE_PAR_DEFAUT if GLOSSAIRE_PAR_DEFAUT.exists() else None


def cmd_record(args: argparse.Namespace) -> int:
    audio = record_until_enter(device=args.device)
    if audio.size == 0:
        print("Rien n'a été capturé.", file=sys.stderr)
        return 1
    print(f"· {audio.size / 16_000:.1f} s capturées")

    if args.save:
        print(f"· audio écrit dans {save_wav(audio, args.save)}")

    tr = Transcriber(args.model, glossary=load_glossary(glossaire_effectif(args.glossary)))
    result = tr.transcribe(audio)
    print(f"· transcrit en {result.duration_wall:.1f} s "
          f"(x{result.realtime_factor:.2f} du temps réel)\n")
    print(result.text)
    return 0


def cmd_transcribe(args: argparse.Namespace) -> int:
    audio = load_wav(args.fichier)
    tr = Transcriber(args.model, glossary=load_glossary(glossaire_effectif(args.glossary)))
    result = tr.transcribe(audio)
    print(f"· {result.duration_audio:.1f} s d'audio transcrites en "
          f"{result.duration_wall:.1f} s (x{result.realtime_factor:.2f})\n")
    print(result.text)
    return 0


def cmd_bench(args: argparse.Namespace) -> int:
    """Compare les modèles candidats sur un même échantillon : c'est ce qui
    tranche le choix de taille, plutôt qu'une estimation a priori."""
    audio = load_wav(args.fichier)
    glossary = load_glossary(glossaire_effectif(args.glossary))
    print(f"Échantillon : {audio.size / 16_000:.1f} s"
          f"{' · glossaire actif' if glossary else ''}\n")

    for name in BENCH_MODELS:
        print(f"{'─' * 72}\n▸ {name}", flush=True)
        try:
            result = Transcriber(name, glossary=glossary).transcribe(audio)
        except Exception as exc:  # modèle absent du cache, mémoire, etc.
            print(f"  échec : {exc}", file=sys.stderr)
            continue
        verdict = "temps réel tenu" if result.realtime_factor <= 1 else "trop lent pour la boucle"
        print(f"  {result.duration_wall:.1f} s  ·  x{result.realtime_factor:.2f}  ·  {verdict}\n")
        print(f"  {result.text}\n")
    return 0


def cmd_dicter(args: argparse.Namespace) -> int:
    """Chaîne complète : audio -> texte brut -> Typst -> PDF.

    Un seul processus Claude pour toute la session : c'est ce qui rend
    l'accumulation du document quasi gratuite d'un passage au suivant.
    """
    sess = Session(args.session)
    print(f"Session : {sess.dossier}")

    tr = Transcriber(args.model, glossary=load_glossary(glossaire_effectif(args.glossary)))
    sources = args.fichiers or [None]

    premier_tour = True
    with SessionClaude(modele=args.claude_model) as claude:
        for source in sources:
            audio = load_wav(source) if source else record_until_enter()
            if audio.size == 0:
                print("Rien à transcrire.", file=sys.stderr)
                continue

            reconnu = tr.transcribe(audio)
            print(f"\n▸ transcrit (x{reconnu.realtime_factor:.2f}) : {reconnu.text}")

            if args.confirmer:
                corrige = input("  [Entrée pour accepter, ou retape le texte] > ").strip()
                if corrige:
                    reconnu.text = corrige

            # Deux cas où la mémoire de Claude ne reflète pas le disque, et où
            # continuer sans rien dire écraserait le document :
            #   - on reprend une session existante dans un processus neuf ;
            #   - le fichier a été corrigé dans un éditeur entre deux passages.
            autoritaire = sess.edition_externe()
            if autoritaire is not None:
                print("▸ édition manuelle détectée — resynchronisation de Claude")
            elif premier_tour and sess.document.strip():
                autoritaire = sess.document
                print("▸ session reprise — le document existant est réinjecté")
            premier_tour = False

            try:
                document = claude.structurer(reconnu.text, document_autoritaire=autoritaire)
            except ErreurStructuration as exc:
                print(f"  échec Claude : {exc}", file=sys.stderr)
                return 1

            sess.enregistrer_passage(reconnu.text, document,
                                     meta={"modele_asr": args.model} | (claude.dernier_usage or {}))
            print(f"▸ document : {sess.typ}")

    res = compiler(sess.typ)
    if res:
        print(f"▸ PDF : {res.pdf}")
        return 0
    print(f"▸ la compilation Typst a échoué :\n{res.erreur}", file=sys.stderr)
    return 1


def _envoyer(claude, sess, tampon: list[str], premier: bool) -> bool:
    """Vide le tampon vers Claude et écrit le document. Retourne le nouveau `premier`."""
    passage = " ".join(tampon).strip()
    if not passage:
        return premier

    autoritaire = sess.edition_externe()
    if autoritaire is not None:
        print("  ▸ édition manuelle détectée — resynchronisation")
    elif premier and sess.document.strip():
        autoritaire = sess.document
        print("  ▸ session reprise — document existant réinjecté")

    try:
        document = claude.structurer(passage, document_autoritaire=autoritaire)
    except ErreurStructuration as exc:
        print(f"  ▸ échec Claude : {exc}", file=sys.stderr)
        return False

    sess.enregistrer_passage(passage, document, meta=claude.dernier_usage)

    res = compiler(sess.typ)
    if not res:
        # Le compilateur dit précisément ce qui cloche : le lui renvoyer coûte
        # un tour et rattrape la plupart des fautes de syntaxe. Une seule
        # tentative — si elle échoue, le .typ reste sur disque, corrigeable
        # à la main, et la session continue.
        print(f"  ▸ Typst refuse, correction demandée : {(res.erreur or '')[:100]}")
        try:
            document = claude.structurer(
                "Le document que tu viens de produire ne compile pas. Erreur du "
                f"compilateur Typst :\n{res.erreur}\n"
                "Corrige uniquement cette erreur et renvoie le document complet."
            )
        except ErreurStructuration as exc:
            print(f"  ▸ échec de la correction : {exc}", file=sys.stderr)
        else:
            sess.enregistrer_passage(passage, document, meta=claude.dernier_usage)
            res = compiler(sess.typ)

    etat = f"PDF {res.pdf}" if res else f"non compilé : {(res.erreur or '')[:120]}"
    print(f"  ▸ {len(document.splitlines())} lignes · {etat}")
    return False


def cmd_live(args: argparse.Namespace) -> int:
    """Dictée continue. Le VAD découpe pour Whisper, les silences longs
    déclenchent l'envoi à Claude (décision A5)."""
    sess = Session(args.session)
    tr = Transcriber(args.model, glossary=load_glossary(glossaire_effectif(args.glossary)))
    print(f"Session : {sess.dossier}")
    print(f"Parle. Silence de {args.silence_paragraphe}s = envoi à Claude. Ctrl-C pour finir.\n")

    tampon: list[str] = []
    premier = True
    try:
        with SessionClaude(modele=args.claude_model) as claude:
            for audio, fin_paragraphe in segments_vad(
                device=args.device,
                silence_segment=args.silence_segment,
                silence_paragraphe=args.silence_paragraphe,
            ):
                if fin_paragraphe:
                    if tampon:
                        premier = _envoyer(claude, sess, tampon, premier)
                        tampon = []
                    continue

                reconnu = tr.transcribe(audio)
                if not reconnu.text:          # silence ou hallucination filtrée
                    continue
                print(f"· {reconnu.text}")
                tampon.append(reconnu.text)

            return 0
    except KeyboardInterrupt:
        print("\n— fin de dictée —")
        if tampon:
            with SessionClaude(modele=args.claude_model) as claude:
                _envoyer(claude, sess, tampon, premier=True)
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="audio2typst")
    parser.add_argument("--model", default="small", help="modèle Whisper (défaut : small)")
    parser.add_argument("--glossary", type=Path, default=None,
                        help=f"vocabulaire, un terme par ligne (défaut : {GLOSSAIRE_PAR_DEFAUT})")
    sub = parser.add_subparsers(dest="commande", required=True)

    p_rec = sub.add_parser("record", help="enregistre au micro puis transcrit")
    p_rec.add_argument("--device", type=int, default=None, help="index du périphérique d'entrée")
    p_rec.add_argument("--save", type=Path, default=None, help="conserve le WAV capturé")
    p_rec.set_defaults(func=cmd_record)

    p_tr = sub.add_parser("transcribe", help="transcrit un WAV existant")
    p_tr.add_argument("fichier", type=Path)
    p_tr.set_defaults(func=cmd_transcribe)

    p_bench = sub.add_parser("bench", help="compare les modèles candidats sur un WAV")
    p_bench.add_argument("fichier", type=Path)
    p_bench.set_defaults(func=cmd_bench)

    p_dic = sub.add_parser("dicter", help="chaîne complète : audio -> Typst -> PDF")
    p_dic.add_argument("fichiers", nargs="*", type=Path,
                       help="WAV à traiter ; sans argument, enregistre au micro")
    p_dic.add_argument("--session", default=None, help="nom de session (défaut : horodaté)")
    p_dic.add_argument("--claude-model", default="sonnet", help="modèle Claude (défaut : sonnet)")
    p_dic.add_argument("--confirmer", action="store_true",
                       help="permet de corriger le texte brut avant envoi à Claude")
    p_dic.set_defaults(func=cmd_dicter)

    p_live = sub.add_parser("live", help="dictée continue avec découpage automatique")
    p_live.add_argument("--session", default=None)
    p_live.add_argument("--device", type=int, default=None)
    p_live.add_argument("--claude-model", default="sonnet")
    p_live.add_argument("--silence-segment", type=float, default=0.8,
                        help="silence (s) qui clôt un segment pour Whisper")
    p_live.add_argument("--silence-paragraphe", type=float, default=2.5,
                        help="silence (s) qui déclenche l'envoi à Claude")
    p_live.set_defaults(func=cmd_live)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
