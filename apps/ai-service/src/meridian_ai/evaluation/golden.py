"""Altın set ve alaka eşleştirmesi: bir parça, altın kaynaklardan hangisini karşılıyor?"""

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceRef:
    doc: str
    section: str
    # Aynı bilgiyi taşıyan başka bölümler (v1): herhangi biri bulunursa kaynak bulunmuş sayılır.
    alternatives: tuple["SourceRef", ...] = ()

    def candidates(self) -> tuple["SourceRef", ...]:
        return (self, *self.alternatives)


@dataclass(frozen=True)
class Question:
    id: str
    question: str
    lang: str
    type: str
    corpus: str
    sources: tuple[SourceRef, ...]
    # Cevap doğruluğu için (v2): her grup "bunlardan biri cevapta geçmeli" demektir.
    keywords: tuple[tuple[str, ...], ...] = ()

    @property
    def answerable(self) -> bool:
        return self.type != "unanswerable"


def load_golden(path: Path) -> list[Question]:
    questions = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            questions.append(
                Question(
                    id=item["id"],
                    question=item["question"],
                    lang=item["lang"],
                    type=item["type"],
                    corpus=item["corpus"],
                    sources=tuple(_source(s) for s in item["sources"]),
                    keywords=tuple(tuple(group) for group in item.get("keywords", [])),
                )
            )
    return questions


def _source(raw: dict) -> SourceRef:
    alternatives = tuple(SourceRef(a["doc"], a["section"]) for a in raw.get("alternatives", []))
    return SourceRef(raw["doc"], raw["section"], alternatives)


_PUNCTUATION = re.compile(r"[^\w\s]")
# Altın sette giriş bölümü (ilk başlıktan önceki metin) "Giriş" ile anılır.
_INTRO = re.compile(r"^giriş\b")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(_PUNCTUATION.sub(" ", text).split())


def matches(ref: SourceRef, doc_path: str, section: str) -> bool:
    """Parça, kaynağın belgesinde ve adı geçen başlığın (ya da alt başlıklarının) altındaysa alakalıdır.

    ``section`` başlık yoludur: "Belge başlığı > H2 > H3". Başlık adı kelime sınırında önek
    olarak eşleşir: "Madde 13" → "Madde 13 – Veri sorumlusuna başvuru" (ama "Madde 130" değil);
    "type: ClusterIP" → "`type: ClusterIP`".
    """
    return any(_matches_one(candidate, doc_path, section) for candidate in ref.candidates())


def _matches_one(ref: SourceRef, doc_path: str, section: str) -> bool:
    if doc_path != ref.doc:
        return False
    path = [normalize(part) for part in section.split(" > ")]
    wanted = normalize(ref.section)
    if _INTRO.match(wanted):
        return len(path) == 1
    return any(part == wanted or part.startswith(wanted + " ") for part in path[1:])


def _fold(text: str) -> str:
    """Türkçe büyük/küçük harfe ve "ı/i" farkına duyarsız; noktalama korunur ("5.000", "status.x")."""
    return unicodedata.normalize("NFKC", text).casefold().replace("i̇", "i").replace("ı", "i")


_CITATION = re.compile(r"\[\d+\]")


def keyword_hit(answer: str, keyword: str) -> bool:
    """Kelime başından eşleşir, ekler serbesttir ("kurul" → "Kurula"); "one" "none" içinde sayılmaz.
    Sayılar iki yandan sınırlıdır: "6", "16" içinde; "5.000", "15.000" içinde sayılmaz. Noktadan sonra
    kelime başlayabilir (".status.x"), sayı başlayamaz. Atıf numarası ("[1]") cevap içeriği değildir."""
    wanted = re.escape(_fold(keyword))
    if keyword[:1].isdigit():
        wanted = r"(?<![\w.])" + wanted
    elif keyword[:1].isalnum():
        wanted = r"(?<!\w)" + wanted
    if keyword[-1:].isdigit():
        wanted += r"(?![\d.]*\d)"
    return re.search(wanted, _fold(_CITATION.sub(" ", answer))) is not None


def answer_correct(answer: str, keywords: tuple[tuple[str, ...], ...]) -> bool:
    """Tüm gruplardan en az bir kelime cevapta geçiyorsa doğru. Anlamı değil beklenen gerçeği denetler:
    deterministiktir, model gerektirmez, CI'da aynı sonucu verir."""
    return bool(keywords) and all(any(keyword_hit(answer, k) for k in group) for group in keywords)
