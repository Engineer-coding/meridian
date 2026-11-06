"""Altın set v2 adaylarının otomatik denetimi: kanıt kaynakta birebir var mı, tuzak terim korpusta yok mu?

İnsan onayının yerini tutmaz; insanın zamanını yalnızca anlam denetimine ayırmasını sağlar.
"""

import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from meridian_ai.chunking import chunk_document
from meridian_ai.evaluation.golden import SourceRef, _matches_one
from meridian_ai.fetchers import RawDocument
from meridian_ai.parsing import parse_markdown

_WORDS = re.compile(r"\w+", re.UNICODE)
_LINK_TARGET = re.compile(r"\]\([^)]*\)")


def _normalize(text: str) -> str:
    text = _LINK_TARGET.sub("]", unicodedata.normalize("NFKC", text)).casefold()
    return " ".join(_WORDS.findall(text))


@dataclass
class Check:
    errors: list[str] = field(default_factory=list)
    stats: Counter = field(default_factory=Counter)


def section_text(documents: list[RawDocument]) -> dict[tuple[str, str], str]:
    """(belge, başlık yolu) → normalize edilmemiş bölüm metni (parçalar birleştirilmiş)."""
    sections: dict[tuple[str, str], list[str]] = {}
    for document in documents:
        for chunk in chunk_document(parse_markdown(document.text, document.path)):
            sections.setdefault((document.path, chunk.section), []).append(chunk.content)
    return {key: "\n".join(parts) for key, parts in sections.items()}


def check(items: list[dict[str, Any]], documents: list[RawDocument]) -> Check:
    sections = section_text(documents)
    corpus = _normalize(" ".join(d.text for d in documents))
    result = Check()
    seen: set[str] = set()
    for item in items:
        identity = _normalize(item["question"])
        if identity in seen:
            result.errors.append(f"{item['id']}: tekrar eden soru")
        seen.add(identity)
        result.stats[item["type"]] += 1
        result.stats[item["lang"]] += 1
        if item["type"] == "unanswerable":
            for term in item.get("forbidden", []):
                # Kelime sınırıyla: "dpo", "endpoint" içinde sayılmasın.
                if f" {_normalize(term)} " in f" {corpus} ":
                    result.errors.append(f"{item['id']}: tuzak terim korpusta geçiyor: {term!r}")
            continue
        for source in item["sources"]:
            ref = SourceRef(source["doc"], source["section"])
            texts = [t for (doc, sec), t in sections.items() if _matches_one(ref, doc, sec)]
            if not texts:
                result.errors.append(f"{item['id']}: bölüm bulunamadı: {source['doc']} § {source['section']}")
            elif evidence := source.get("evidence"):
                if not any(_normalize(evidence) in _normalize(t) for t in texts):
                    result.errors.append(f"{item['id']}: kanıt bölümde yok: {evidence!r}")
    return result


def to_jsonl(items: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = (json.dumps(item, ensure_ascii=False) for item in items)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
