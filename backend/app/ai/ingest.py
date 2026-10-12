"""Rebuild the knowledge base: chunk documents, embed them, store them in pgvector.

Run with:  python -m app.ai.ingest

Safe to re-run at any time. Chunks whose text hasn't changed reuse their stored embedding,
and the old chunks are replaced in a single transaction, so the chatbot never sees a
half-built knowledge base.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ai.chunking import KNOWLEDGE_DIR, Chunk, load_documents
from app.ai.embeddings import Embedder, EmbeddingError, get_embedder
from app.ai.price_list import price_list_chunks
from app.db.models import KnowledgeChunk
from app.db.session import SessionLocal
from app.services import catalog


@dataclass(frozen=True)
class IngestResult:
    chunks: int
    embedded: int  # sent to the embedding API
    reused: int  # embedding copied from the previous run


def content_hash(chunk: Chunk, model: str) -> str:
    return hashlib.sha256(f"{model}\n{chunk.embedding_text}".encode()).hexdigest()


def ingest(db: Session, embedder: Embedder, knowledge_dir: Path = KNOWLEDGE_DIR) -> IngestResult:
    chunks = load_documents(knowledge_dir) + price_list_chunks(catalog.list_services(db))
    hashes = [content_hash(chunk, embedder.model) for chunk in chunks]

    embeddings = _existing_embeddings(db, set(hashes))
    reused = sum(1 for h in hashes if h in embeddings)

    # Embed each distinct new text once (identical sections would share a hash).
    new = {h: chunk for h, chunk in zip(hashes, chunks, strict=True) if h not in embeddings}
    if new:
        vectors = embedder.embed_documents([chunk.embedding_text for chunk in new.values()])
        if len(vectors) != len(new) or any(len(v) != embedder.dimensions for v in vectors):
            raise EmbeddingError("Embedding API returned an unexpected number or size of vectors")
        embeddings.update(zip(new, vectors, strict=True))

    db.execute(delete(KnowledgeChunk))
    db.add_all(
        KnowledgeChunk(
            source=chunk.source,
            title=chunk.title,
            heading=chunk.heading,
            content=chunk.content,
            content_hash=h,
            embedding=embeddings[h],
        )
        for h, chunk in zip(hashes, chunks, strict=True)
    )
    db.commit()
    return IngestResult(chunks=len(chunks), embedded=len(new), reused=reused)


def _existing_embeddings(db: Session, hashes: set[str]) -> dict[str, list[float]]:
    rows = db.execute(
        select(KnowledgeChunk.content_hash, KnowledgeChunk.embedding).where(
            KnowledgeChunk.content_hash.in_(hashes)
        )
    )
    return {row.content_hash: list(row.embedding) for row in rows}


def main() -> None:
    try:
        with SessionLocal() as db:
            result = ingest(db, get_embedder())
    except EmbeddingError as exc:
        raise SystemExit(f"Ingestion failed: {exc}") from exc
    print(
        f"Knowledge base rebuilt: {result.chunks} chunks "
        f"({result.embedded} embedded, {result.reused} reused)."
    )


if __name__ == "__main__":
    main()
