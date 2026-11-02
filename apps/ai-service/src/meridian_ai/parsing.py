"""Markdown/metin belgesini başlık yoluna göre bölümlere ayırır."""

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_TITLE = re.compile(r"""^title:\s*["']?(.+?)["']?\s*$""", re.MULTILINE)
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
# Hugo kısa kodları: {{< glossary_tooltip text="Pod" term_id="pod" >}} → "Pod"; diğerleri silinir.
_SHORTCODE_WITH_TEXT = re.compile(r"""\{\{[<%]\s*[\w/-]+[^}]*?\btext=["']([^"']*)["'][^}]*?[>%]\}\}""")
_SHORTCODE = re.compile(r"\{\{[<%].*?[>%]\}\}", re.DOTALL)
# Başlık bağlantı kimliği: "## Container restarts {#restart-policy}".
_HEADING_ANCHOR = re.compile(r"\s*\{#[^}]*\}\s*$")


@dataclass(frozen=True)
class Section:
    path: tuple[str, ...]
    text: str


@dataclass(frozen=True)
class ParsedDocument:
    title: str
    sections: list[Section] = field(default_factory=list)


def parse_markdown(raw: str, file_path: str) -> ParsedDocument:
    text = raw.replace("\r\n", "\n")
    title: str | None = None
    if match := _FRONT_MATTER.match(text):
        if found := _TITLE.search(match.group(1)):
            title = found.group(1).strip()
        text = text[match.end() :]
    text = _HTML_COMMENT.sub("", text)
    text = _SHORTCODE_WITH_TEXT.sub(r"\1", text)
    text = _SHORTCODE.sub("", text)

    headings: list[tuple[int, str]] = []
    sections: list[Section] = []
    buffer: list[str] = []
    in_fence = False

    def flush() -> None:
        body = "\n".join(buffer).strip()
        buffer.clear()
        if body:
            sections.append(Section(tuple(h for _, h in headings), body))

    for line in text.split("\n"):
        if _FENCE.match(line):
            in_fence = not in_fence
        heading = None if in_fence else _HEADING.match(line)
        if heading is None:
            buffer.append(line)
            continue
        flush()
        level, name = len(heading.group(1)), _HEADING_ANCHOR.sub("", heading.group(2)).strip()
        if level == 1 and title is None:
            title = name
        while headings and headings[-1][0] >= level:
            headings.pop()
        headings.append((level, name))
    flush()

    title = title or PurePosixPath(file_path).stem.replace("_", " ").replace("-", " ").strip() or file_path
    # Başlık yolunun başında belge başlığı zaten varsa (H1) tekrarlanmaz.
    sections = [Section(s.path[1:] if s.path[:1] == (title,) else s.path, s.text) for s in sections]
    return ParsedDocument(title=title, sections=sections)
