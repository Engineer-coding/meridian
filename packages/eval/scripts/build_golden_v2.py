"""İnsan kararlarından altın set v2'yi üretir (yalnızca standart kütüphane).

    python -I packages/eval/scripts/build_golden_v2.py decisions.json

`decisions.json`: doğrulama sayfasının kararları, `{"kvkk-101": {"decision": "approve"}, ...}`.
- approve: aday olduğu gibi girer, `verified: true`.
- edit: düzeltilen soru/cevap/anahtar kelimelerle girer, `verified: true`.
- reject: girmez.
Kararı verilmemiş yeni aday girmez: doğrulanmamış soru setin parçası olmaz. Mevcut v1 sorusu
kararsız ya da reddedilmişse soru kalır, yalnızca (doğrulanmamış) anahtar kelimeleri eklenmez.
"""

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

EVAL = Path(__file__).resolve().parents[1]


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _existing_keywords() -> dict:
    spec = importlib.util.spec_from_file_location("candidates", EVAL / "scripts" / "golden_v2_candidates.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.EXISTING_KEYWORDS


def _apply_edit(item: dict, decision: dict) -> None:
    item["question"] = decision.get("question") or item["question"]
    if item["type"] != "unanswerable":
        item["expected_answer"] = decision.get("answer") or item["expected_answer"]
        item["keywords"] = decision.get("keywords") or item.get("keywords", [])
    if decision.get("note"):
        item["notes"] = decision["note"]


def build(decisions: dict[str, dict], v1: list[dict], candidates: list[dict], keywords: dict) -> tuple[list[dict], Counter]:
    tally: Counter = Counter()
    out: list[dict] = []
    for item in v1:
        decision = decisions.get(item["id"])
        verdict = decision["decision"] if decision else None
        if item["id"] in keywords and verdict in ("approve", "edit"):
            item["keywords"] = keywords[item["id"]]
            if verdict == "edit":
                _apply_edit(item, decision)
        elif item["id"] in keywords:
            tally["v1_without_keywords"] += 1
        out.append(item)
    for item in candidates:
        decision = decisions.get(item["id"])
        if not decision:
            tally["undecided"] += 1
            continue
        tally[decision["decision"]] += 1
        if decision["decision"] == "reject":
            continue
        if decision["decision"] == "edit":
            _apply_edit(item, decision)
        item.pop("forbidden", None)
        item["verified"] = True
        out.append(item)
    return out, tally


def main(path: str) -> int:
    decisions = json.loads(Path(path).read_text(encoding="utf-8"))
    decisions.pop("_review", None)
    excluded = set(decisions.pop("_excluded", {}).get("ids", []))
    items, tally = build(
        decisions,
        _read_jsonl(EVAL / "golden" / "v1.jsonl"),
        [c for c in _read_jsonl(EVAL / "candidates" / "v2.jsonl") if c["id"] not in excluded],
        _existing_keywords(),
    )
    target = EVAL / "golden" / "v2.jsonl"
    lines = "\n".join(json.dumps(item, ensure_ascii=False) for item in items)
    target.write_text(lines + "\n", encoding="utf-8", newline="\n")
    print(f"{len(items)} soru yazıldı: {dict(tally)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
