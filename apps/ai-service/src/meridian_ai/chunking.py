"""Bölümleri embedding modeline sığan, bağlamı korunmuş parçalara böler."""

import re
from dataclasses import dataclass

from meridian_ai.parsing import ParsedDocument

# multilingual-e5-large en fazla 512 token okur. ~1200 karakter Türkçede ~350, İngilizcede
# ~300 token eder; başlık bağlamı eklendiğinde de sınırın altında kalır.
MAX_CHARS = 1_200
# Ardışık parçalar arasında tekrar eden metin: cümle parça sınırında bölündüğünde anlam kaybolmasın.
OVERLAP_CHARS = 150

_PARAGRAPH = re.compile(r"\n\s*\n")
_SENTENCE = re.compile(r"(?<=[.!?:;])\s+")


@dataclass(frozen=True)
class Chunk:
    ordinal: int
    section: str
    content: str


def chunk_document(
    document: ParsedDocument, max_chars: int = MAX_CHARS, overlap: int = OVERLAP_CHARS
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section in document.sections:
        heading = " > ".join((document.title, *section.path))
        for content in _pack(_pieces(section.text, max_chars), max_chars, overlap):
            chunks.append(Chunk(len(chunks), heading, content))
    return chunks


def _pieces(text: str, max_chars: int) -> list[str]:
    """Paragraflar; tek başına sığmayan paragraf cümlelere, o da sığmazsa kelimelere bölünür."""
    pieces: list[str] = []
    for paragraph in (p.strip() for p in _PARAGRAPH.split(text)):
        if not paragraph:
            continue
        if len(paragraph) <= max_chars:
            pieces.append(paragraph)
            continue
        for sentence in _SENTENCE.split(paragraph):
            if len(sentence) <= max_chars:
                pieces.append(sentence)
            else:
                pieces.extend(_split_words(sentence, max_chars))
    return pieces


def _split_words(text: str, max_chars: int) -> list[str]:
    parts: list[str] = []
    current = ""
    for word in text.split():
        while len(word) > max_chars:
            if current:
                parts.append(current)
                current = ""
            parts.append(word[:max_chars])
            word = word[max_chars:]
        candidate = f"{current} {word}" if current else word
        if len(candidate) > max_chars:
            parts.append(current)
            current = word
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


def _pack(pieces: list[str], max_chars: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        candidate = f"{current}\n\n{piece}" if current else piece
        if len(candidate) <= max_chars:
            current = candidate
            continue
        chunks.append(current)
        tail = _tail(current, overlap)
        current = f"{tail}\n\n{piece}" if tail and len(tail) + 2 + len(piece) <= max_chars else piece
    if current:
        chunks.append(current)
    return chunks


def _tail(text: str, size: int) -> str:
    """Metnin son ``size`` karakteri, kelime ortasından başlamayacak şekilde."""
    if len(text) <= size:
        return text
    tail = text[-size:]
    space = tail.find(" ")
    return tail[space + 1 :] if space != -1 else tail
