from meridian_ai.chunking import chunk_document
from meridian_ai.parsing import ParsedDocument, Section, parse_markdown

HUGO_PAGE = """---
title: "Pod Lifecycle"
content_type: concept
weight: 30
---

<!-- overview -->
This page describes the lifecycle of a {{< glossary_tooltip text="Pod" term_id="pod" >}}.

{{< note >}}
Pods are ephemeral.
{{< /note >}}

## Pod phase {#pod-phase}

A Pod's `status` field has a `phase`.

```yaml
# not a heading
kind: Pod
```

### Pending

The Pod has been accepted.

## Container states

Waiting, Running, Terminated.
"""


def test_hugo_front_matter_and_shortcodes_are_cleaned() -> None:
    doc = parse_markdown(HUGO_PAGE, "content/en/docs/concepts/workloads/pods/pod-lifecycle.md")

    assert doc.title == "Pod Lifecycle"
    intro = doc.sections[0]
    assert intro.path == ()
    assert "lifecycle of a Pod." in intro.text
    assert "Pods are ephemeral." in intro.text
    assert "{{" not in intro.text
    assert "overview" not in intro.text


def test_sections_follow_heading_hierarchy_and_ignore_code_fences() -> None:
    doc = parse_markdown(HUGO_PAGE, "pod-lifecycle.md")

    assert [s.path for s in doc.sections] == [
        (),
        ("Pod phase",),
        ("Pod phase", "Pending"),
        ("Container states",),
    ]
    assert "# not a heading" in doc.sections[1].text


def test_first_h1_becomes_title_and_is_not_repeated_in_paths() -> None:
    doc = parse_markdown("# KVKK\n\nGiriş.\n\n## Madde 13\n\nBaşvuru otuz gün içinde.", "kvkk/6698.md")

    assert doc.title == "KVKK"
    assert [s.path for s in doc.sections] == [(), ("Madde 13",)]


def test_title_falls_back_to_file_name() -> None:
    assert parse_markdown("just text", "docs/getting_started-guide.txt").title == "getting started guide"


def test_chunks_carry_section_context_and_stay_within_budget() -> None:
    paragraphs = [f"Paragraf {i}: " + " ".join(f"kelime{i}x{j}" for j in range(30)) for i in range(20)]
    doc = ParsedDocument("Kılavuz", [Section(("Kurulum", "Linux"), "\n\n".join(paragraphs))])

    chunks = chunk_document(doc, max_chars=600, overlap=100)

    assert len(chunks) > 3
    assert all(len(c.content) <= 600 for c in chunks)
    assert {c.section for c in chunks} == {"Kılavuz > Kurulum > Linux"}
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))
    words = {w for p in paragraphs for w in p.split()}
    assert words <= {w for c in chunks for w in c.content.split()}


def test_consecutive_chunks_overlap() -> None:
    text = "\n\n".join(f"Cümle {i} " + "doldurma " * 20 for i in range(10))
    chunks = chunk_document(ParsedDocument("T", [Section((), text)]), max_chars=400, overlap=120)

    for previous, current in zip(chunks, chunks[1:], strict=False):
        last_words = previous.content.split()[-3:]
        assert " ".join(last_words) in current.content


def test_oversized_paragraph_and_word_are_split() -> None:
    text = "a" * 2_500 + " " + "Uzun cümle. " * 200
    chunks = chunk_document(ParsedDocument("T", [Section((), text)]), max_chars=500, overlap=50)

    assert all(len(c.content) <= 500 for c in chunks)
    assert sum(c.content.count("a" * 500) for c in chunks) >= 5


def test_empty_sections_produce_no_chunks() -> None:
    assert chunk_document(ParsedDocument("T", [])) == []
