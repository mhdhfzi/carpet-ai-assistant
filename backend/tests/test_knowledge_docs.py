"""Checks the knowledge documents (the demo's and the real business's) follow the rules in
knowledge/README.md, and that the two businesses never leak into each other."""

import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
DEMO_DIR = BACKEND / "knowledge"  # Kilau Carpet Care, fictional
REAL_DIR = BACKEND / "knowledge-cucicuci"  # Cuci-Cuci Senawang
DOCUMENTS = sorted(p for d in (DEMO_DIR, REAL_DIR) for p in d.glob("*.md") if p.name != "README.md")


def _id(path: Path) -> str:
    return f"{path.parent.name}/{path.name}"


FRONT_MATTER = re.compile(r"\A---\n(?P<body>.*?)\n---\n", re.DOTALL)


def test_there_are_documents() -> None:
    assert list(DEMO_DIR.glob("*.md")) and list(REAL_DIR.glob("*.md"))


@pytest.mark.parametrize("path", DOCUMENTS, ids=_id)
def test_document_has_a_title(path: Path) -> None:
    match = FRONT_MATTER.match(path.read_text(encoding="utf-8"))

    assert match, "missing front matter"
    assert re.search(r"^title: \S", match["body"], re.MULTILINE), "missing title"


@pytest.mark.parametrize("path", DOCUMENTS, ids=_id)
def test_document_has_sections(path: Path) -> None:
    """Sections (## headings) are the chunking unit for retrieval."""
    assert re.search(r"^## \S", path.read_text(encoding="utf-8"), re.MULTILINE)


@pytest.mark.parametrize("path", DOCUMENTS, ids=_id)
def test_document_contains_no_prices(path: Path) -> None:
    """Prices come from the database only, so they can't go out of date in two places."""
    prices = re.findall(r"RM\s?\d", path.read_text(encoding="utf-8"), re.IGNORECASE)

    assert not prices, "put prices in app/seed.py, not in knowledge documents"


def test_the_two_businesses_never_mix() -> None:
    """Recruiters on the demo must never be sent to the real business, and real customers
    must never be told the business is fictional."""
    demo = " ".join(p.read_text(encoding="utf-8") for p in DEMO_DIR.glob("*.md"))
    real = " ".join(p.read_text(encoding="utf-8") for p in REAL_DIR.glob("*.md"))

    for real_detail in ("Cuci-Cuci", "Senawang 5", "019-276", "cucicucisenawang"):
        assert real_detail not in demo
    for demo_detail in ("Kilau", "fictional", "Jalan Contoh", "example.com"):
        assert demo_detail not in real
