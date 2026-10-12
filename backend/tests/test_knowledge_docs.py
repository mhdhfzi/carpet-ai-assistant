"""Checks the knowledge documents follow the rules in knowledge/README.md."""

import re
from pathlib import Path

import pytest

KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "knowledge"
DOCUMENTS = sorted(p for p in KNOWLEDGE_DIR.glob("*.md") if p.name != "README.md")
FRONT_MATTER = re.compile(r"\A---\n(?P<body>.*?)\n---\n", re.DOTALL)


def test_there_are_documents() -> None:
    assert DOCUMENTS


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_document_has_a_title(path: Path) -> None:
    match = FRONT_MATTER.match(path.read_text(encoding="utf-8"))

    assert match, "missing front matter"
    assert re.search(r"^title: \S", match["body"], re.MULTILINE), "missing title"


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_document_has_sections(path: Path) -> None:
    """Sections (## headings) are the chunking unit for retrieval."""
    assert re.search(r"^## \S", path.read_text(encoding="utf-8"), re.MULTILINE)


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_document_contains_no_prices(path: Path) -> None:
    """Prices come from the database only, so they can't go out of date in two places."""
    prices = re.findall(r"RM\s?\d", path.read_text(encoding="utf-8"), re.IGNORECASE)

    assert not prices, "put prices in app/seed.py, not in knowledge documents"
