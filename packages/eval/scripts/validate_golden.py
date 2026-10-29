"""Altın set doğrulayıcı: şema, benzersizlik ve dağılım kontrolü (yalnızca standart kütüphane)."""

import json
import sys
from collections import Counter
from pathlib import Path

REQUIRED = {"id", "question", "lang", "type", "corpus", "expected_answer", "sources", "origin", "verified"}
TYPES = {"single_hop", "multi_hop", "unanswerable"}
LANGS = {"tr", "en"}
ORIGINS = {"human", "synthetic"}
MIN_SHARE = {"multi_hop": 0.20, "unanswerable": 0.15}


def validate_item(item: dict, line_no: int) -> list[str]:
    errors = []
    missing = REQUIRED - item.keys()
    if missing:
        return [f"satır {line_no}: eksik alan(lar): {sorted(missing)}"]
    if item["type"] not in TYPES:
        errors.append(f"satır {line_no}: geçersiz type '{item['type']}'")
    if item["lang"] not in LANGS:
        errors.append(f"satır {line_no}: geçersiz lang '{item['lang']}'")
    if item["origin"] not in ORIGINS:
        errors.append(f"satır {line_no}: geçersiz origin '{item['origin']}'")
    if not isinstance(item["verified"], bool):
        errors.append(f"satır {line_no}: verified true/false olmalı")
    if not item["question"].strip():
        errors.append(f"satır {line_no}: soru boş")

    sources = item["sources"]
    if not isinstance(sources, list):
        errors.append(f"satır {line_no}: sources bir liste olmalı")
    elif item["type"] == "unanswerable":
        if sources:
            errors.append(f"satır {line_no}: unanswerable sorunun kaynağı olmamalı")
        if item["expected_answer"] is not None:
            errors.append(f"satır {line_no}: unanswerable sorunun expected_answer değeri null olmalı")
    else:
        if not item["expected_answer"]:
            errors.append(f"satır {line_no}: expected_answer boş")
        need = 2 if item["type"] == "multi_hop" else 1
        if len(sources) < need:
            errors.append(f"satır {line_no}: {item['type']} en az {need} kaynak ister")
        for src in sources:
            if not isinstance(src, dict) or not src.get("doc") or not src.get("section"):
                errors.append(f"satır {line_no}: her kaynakta 'doc' ve 'section' olmalı")
    return errors


def main(path: str) -> int:
    items, errors = [], []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"satır {line_no}: geçersiz JSON ({exc.msg})")
            continue
        errors.extend(validate_item(item, line_no))
        items.append(item)

    ids = Counter(i.get("id") for i in items)
    errors.extend(f"tekrarlanan id: {i}" for i, n in ids.items() if n > 1)

    total = len(items)
    types = Counter(i.get("type") for i in items)
    for t, share in MIN_SHARE.items():
        if total and types[t] / total < share:
            errors.append(f"dağılım: {t} oranı {types[t] / total:.0%} (en az {share:.0%} olmalı)")

    print(f"{total} soru | tür: {dict(types)} | dil: {dict(Counter(i.get('lang') for i in items))} "
          f"| doğrulanmış: {sum(1 for i in items if i.get('verified') is True)}")
    for e in errors:
        print(f"HATA  {e}")
    if errors:
        print(f"{len(errors)} hata bulundu.")
        return 1
    print("Altın set geçerli.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))