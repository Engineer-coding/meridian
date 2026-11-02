"""KVKK (6698) resmî PDF'ini değerlendirme korpusu için Markdown'a çevirir.

Her madde bir başlık olur ("### Madde 13 – Başvuru usulü"); altın setteki "Madde 13" gibi
kaynak referansları bu başlıklarla eşleşir. PDF'in hash'i manifest'teki değerle aynı değilse
dönüştürmez: mevzuat güncellenmişse altın setin de gözden geçirilmesi gerekir.

    uv run --with pypdf==6.1.1 python -I packages/eval/scripts/kvkk_to_markdown.py 6698.pdf
"""

import hashlib
import json
import re
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parents[1]
OUTPUT = EVAL / "corpus" / "kvkk" / "6698.md"

_CHAPTER = re.compile(r"^([A-ZÇĞİÖŞÜ]+) BÖLÜM$")
_ARTICLE = re.compile(r"^(GEÇİCİ )?MADDE (\d+)\s*-\s*(.*)$")
# Fıkra başı: cümle sonundan sonra gelen "(2) ". "(4), (5) ve (6) numaralı" gibi atıflar bölünmez.
_PARAGRAPH = re.compile(r"(?<=[.:;])\s(?=\(\d+\)\s)")
# Dipnotlar sayfa altında, metnin ortasına düşer: "1 2/3/2024 tarihli ve 7499 sayılı Kanunun ..."
# ile başlar ve değişikliği bildiren cümleyle ("... değiştirilmiştir.") biter.
_FOOTNOTE_START = re.compile(r"^\d{1,2} \d{1,2}/\d{1,2}/\d{4} tarihli")
_FOOTNOTE_END = re.compile(r"(tir|tır)\.$")
# Dipnot işareti: "ilişkilidir.2", "Kabahatler1".
_FOOTNOTE_MARK = re.compile(r"(?<=[.,;:”])\s?\d{1,2}$|(?<=[^\d\s])\d{1,2}$")
# Kanun metni bittikten sonra kadro cetveli ve değişiklik tablosu gelir; korpusa alınmaz.
_END = "(I) SAYILI CETVEL"


def _title(text: str) -> str:
    """Türkçe büyük/küçük harf: str.title() "İ"yi "i̇" yapar, "I"yı "i" sanar."""
    words = text.replace("I", "ı").replace("İ", "i").lower().split()
    return " ".join(w[:1].replace("i", "İ").replace("ı", "I").upper() + w[1:] for w in words)


def _without_footnotes(lines: list[str]) -> list[str]:
    kept: list[str] = []
    in_footnote = False
    for line in lines:
        if not in_footnote and _FOOTNOTE_START.match(line):
            in_footnote = True
        if in_footnote:
            in_footnote = not _FOOTNOTE_END.search(line)
            continue
        kept.append(_FOOTNOTE_MARK.sub("", line).rstrip())
    return kept


def convert(text: str) -> str:
    lines = [line.strip() for line in text.replace("\r\n", "\n").split("\n")]
    if _END in lines:
        lines = lines[: lines.index(_END)]
    lines = _without_footnotes(lines)

    out = [f"# {_title(lines[0])}", ""]
    body: list[str] = []
    pending_title: str | None = None
    i = 1

    def flush() -> None:
        if body:
            joined = re.sub(r"\s+", " ", " ".join(body)).strip()
            out.append(_PARAGRAPH.sub("\n\n", joined))
            out.append("")
            body.clear()

    while i < len(lines):
        line = lines[i]
        if chapter := _CHAPTER.match(line):
            flush()
            out += [f"## {_title(chapter.group(1))} Bölüm – {lines[i + 1]}", ""]
            i += 2
            continue
        if article := _ARTICLE.match(line):
            flush()
            prefix = "Geçici Madde" if article.group(1) else "Madde"
            heading = f"### {prefix} {article.group(2)}"
            out += [f"{heading} – {pending_title}" if pending_title else heading, ""]
            pending_title = None
            body.append(article.group(3))
            i += 1
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if line and _ARTICLE.match(nxt):
            # Madde başlığı ("Başvuru usulü") her zaman MADDE satırından hemen önce gelir.
            pending_title = line
        elif line:
            body.append(line)
        i += 1
    flush()
    return "\n".join(out).rstrip() + "\n"


def main(pdf_path: str) -> int:
    from pypdf import PdfReader

    pdf = Path(pdf_path)
    manifest = json.loads((EVAL / "corpus" / "manifest.json").read_text(encoding="utf-8"))
    expected = next(c["sha256"] for c in manifest["corpora"] if c["id"] == "kvkk")
    actual = hashlib.sha256(pdf.read_bytes()).hexdigest()
    if actual != expected:
        print(f"PDF hash'i {actual}, manifest {expected} bekliyor", file=sys.stderr)
        return 1
    text = "\n".join(page.extract_text() for page in PdfReader(pdf).pages)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(convert(text), encoding="utf-8", newline="\n")
    print(f"{OUTPUT.relative_to(EVAL.parents[1])} yazıldı")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
