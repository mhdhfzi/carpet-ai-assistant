import pytest

from app.ai.chunking import Chunk, load_documents, parse_document

DOC = """---
title: Booking and opening hours
---

# Booking and opening hours

We are a family business.

## Opening hours

Open every day except Friday.

## Public holidays

We are usually closed on public holidays.
"""


def test_each_section_becomes_a_chunk() -> None:
    chunks = parse_document(DOC, "booking.md")

    assert [c.heading for c in chunks] == [
        "Booking and opening hours",  # the introduction, under the document title
        "Opening hours",
        "Public holidays",
    ]
    assert chunks[1] == Chunk(
        "booking.md", "Booking and opening hours", "Opening hours", "Open every day except Friday."
    )


def test_embedding_text_carries_title_and_heading_for_context() -> None:
    chunk = parse_document(DOC, "booking.md")[2]

    assert chunk.embedding_text == (
        "Booking and opening hours: Public holidays\n\nWe are usually closed on public holidays."
    )


def test_document_without_intro_or_with_empty_sections() -> None:
    doc = "---\ntitle: T\n---\n# T\n\n## Empty\n\n## Full\n\nText.\n"

    assert [c.heading for c in parse_document(doc, "t.md")] == ["Full"]


def test_windows_line_endings_are_handled() -> None:
    assert len(parse_document(DOC.replace("\n", "\r\n"), "booking.md")) == 3


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ("# No front matter\n\n## A\n\nB", "missing front matter"),
        ("---\nauthor: me\n---\n## A\n\nB", "no title"),
    ],
)
def test_invalid_documents_are_rejected(text: str, error: str) -> None:
    with pytest.raises(ValueError, match=error):
        parse_document(text, "bad.md")


def test_real_knowledge_base_loads() -> None:
    chunks = load_documents()

    assert {c.source for c in chunks} >= {"faq.md", "services.md", "how-it-works.md"}
    assert all(c.content for c in chunks)
    assert "README.md" not in {c.source for c in chunks}
    # Every chunk must stand alone, so headings must be unique within a document.
    keys = [(c.source, c.heading) for c in chunks]
    assert len(keys) == len(set(keys))
