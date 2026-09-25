"""Compilation Typst -> PDF via les bindings Python (pas de toolchain Rust)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import typst


@dataclass
class ResultatCompilation:
    ok: bool
    pdf: Path | None
    erreur: str | None

    def __bool__(self) -> bool:
        return self.ok


def compiler(source: str | Path, sortie: str | Path | None = None) -> ResultatCompilation:
    """Compile un .typ. Ne lève pas : le message d'erreur est une donnée utile,
    c'est lui qu'on renverra à Claude pour qu'il corrige sa propre syntaxe."""
    source = Path(source)
    sortie = Path(sortie) if sortie else source.with_suffix(".pdf")
    try:
        typst.compile(str(source), output=str(sortie))
    except Exception as exc:
        return ResultatCompilation(ok=False, pdf=None, erreur=str(exc))
    return ResultatCompilation(ok=True, pdf=sortie, erreur=None)
