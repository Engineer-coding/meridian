"""Değerlendirme kapısı (ADR-0010): kayıtlı rapor güncel mi, eşiklerin üstünde mi?

Gerçek ölçüm CPU'da saatler sürer ve CI'da çalıştırılamaz. Bu yüzden CI ölçmez, ölçümün geçerliliğini
denetler: rapor, sonucu etkileyen kodun ve verinin parmak izini taşır. Bunlardan biri değişip rapor
yenilenmezse ya da rapordaki skor eşiğin altındaysa test kırılır.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from meridian_ai.evaluation.corpus import EVAL_DIR

_PACKAGE = Path(__file__).resolve().parents[1]

# Arama sonucunu etkileyen kod. Süreç, depo ve bağlantı kodu bilerek yok: skoru değiştirmez.
RETRIEVAL_CODE = ("parsing.py", "chunking.py", "embedding.py", "indexer.py", "retrieval.py", "reranking.py")
ANSWER_CODE = (*RETRIEVAL_CODE, "answering.py", "llm.py")


def fingerprint(golden: Path, code: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    for path in (*(_PACKAGE / name for name in code), golden, EVAL_DIR / "corpus" / "manifest.json"):
        # Satır sonları Windows ve Linux checkout'larında farklı olabilir.
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def thresholds() -> dict[str, Any]:
    return json.loads((EVAL_DIR / "thresholds.json").read_text(encoding="utf-8"))


def violations(
    report: dict[str, Any], floors: dict[str, float], ceilings: dict[str, float] | None = None
) -> list[str]:
    """``report`` düz bir metrik sözlüğüdür; eksik metrik de ihlaldir, sessizce geçmez."""
    found = []
    for name, floor in floors.items():
        value = report.get(name)
        if value is None or value < floor:
            found.append(f"{name} = {value}, en az {floor} olmalı")
    for name, ceiling in (ceilings or {}).items():
        value = report.get(name)
        if value is None or value > ceiling:
            found.append(f"{name} = {value}, en fazla {ceiling} olmalı")
    return found
