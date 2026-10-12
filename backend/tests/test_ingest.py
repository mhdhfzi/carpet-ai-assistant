from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.embeddings import EmbeddingError
from app.ai.ingest import ingest
from app.ai.price_list import SOURCE as PRICE_LIST_SOURCE
from app.db.models import KnowledgeChunk, PricingUnit, Service
from tests.fakes import FakeEmbedder


def write_doc(directory: Path, name: str, sections: dict[str, str]) -> None:
    body = "".join(f"## {heading}\n\n{text}\n\n" for heading, text in sections.items())
    (directory / name).write_text(f"---\ntitle: {name}\n---\n\n{body}", encoding="utf-8")


@pytest.fixture
def knowledge(tmp_path: Path) -> Path:
    write_doc(tmp_path, "hours.md", {"Opening hours": "Closed on Fridays.", "Notice": "2 days."})
    write_doc(tmp_path, "faq.md", {"Drop off": "You can drop off carpets at our shop."})
    return tmp_path


def chunk_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(KnowledgeChunk)) or 0


def test_ingest_stores_document_and_price_list_chunks(db: Session, knowledge: Path) -> None:
    db.add(
        Service(name="Karpet Biasa", pricing_unit=PricingUnit.PER_SQFT, unit_price=Decimal("1.80"))
    )
    db.flush()

    result = ingest(db, FakeEmbedder(), knowledge)

    assert (result.chunks, result.embedded, result.reused) == (4, 4, 0)
    price = db.scalar(select(KnowledgeChunk).where(KnowledgeChunk.source == PRICE_LIST_SOURCE))
    assert price is not None
    assert price.content.startswith("Karpet Biasa costs RM1.80 per square foot.")
    assert len(price.embedding) == 1024


def test_reingest_reuses_embeddings_for_unchanged_chunks(db: Session, knowledge: Path) -> None:
    ingest(db, FakeEmbedder(), knowledge)
    write_doc(knowledge, "faq.md", {"Drop off": "You can drop off carpets and sofas."})
    embedder = FakeEmbedder()

    result = ingest(db, embedder, knowledge)

    assert (result.embedded, result.reused) == (1, 2)
    assert embedder.embedded == ["faq.md: Drop off\n\nYou can drop off carpets and sofas."]
    assert chunk_count(db) == 3  # replaced, not appended


def test_removed_sections_are_deleted(db: Session, knowledge: Path) -> None:
    ingest(db, FakeEmbedder(), knowledge)
    (knowledge / "faq.md").unlink()

    ingest(db, FakeEmbedder(), knowledge)

    assert set(db.scalars(select(KnowledgeChunk.source))) == {"hours.md"}


def test_changing_the_model_reembeds_everything(db: Session, knowledge: Path) -> None:
    ingest(db, FakeEmbedder(model="model-a"), knowledge)

    result = ingest(db, FakeEmbedder(model="model-b"), knowledge)

    assert (result.embedded, result.reused) == (3, 0)


def test_wrong_vector_size_is_rejected_and_nothing_changes(db: Session, knowledge: Path) -> None:
    ingest(db, FakeEmbedder(), knowledge)

    class BrokenEmbedder(FakeEmbedder):
        def embed_documents(self, texts):
            return [[0.0, 1.0] for _ in texts]

    with pytest.raises(EmbeddingError):
        ingest(db, BrokenEmbedder(model="other"), knowledge)
    assert chunk_count(db) == 3


def test_real_knowledge_base_ingests(db: Session) -> None:
    result = ingest(db, FakeEmbedder())

    assert result.chunks == chunk_count(db) > 10
