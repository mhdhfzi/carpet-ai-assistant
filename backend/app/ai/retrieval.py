"""Find the knowledge chunks most relevant to a question (the "R" in RAG)."""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embeddings import Embedder
from app.db.models import KnowledgeChunk


@dataclass(frozen=True)
class RetrievedChunk:
    source: str
    title: str
    heading: str
    content: str
    score: float  # cosine similarity: 1.0 = same meaning, around 0 = unrelated


def retrieve(
    db: Session, embedder: Embedder, query: str, *, limit: int = 5
) -> list[RetrievedChunk]:
    return _nearest(db, embedder.embed_query(query), limit)


def retrieve_for(
    db: Session, embedder: Embedder, queries: Sequence[str], *, limit: int = 5
) -> list[RetrievedChunk]:
    """Search with several queries and interleave the results: every query's best match,
    then every query's second best, and so on, skipping repeats. Earlier queries pick first.

    Interleaving, not sorting by score: scores from different queries aren't comparable (a
    long query scores higher overall), and sorting would let one query crowd out the other.
    All queries are embedded in one request.
    """
    ranked = [_nearest(db, vector, limit) for vector in embedder.embed_queries(queries)]
    merged: list[RetrievedChunk] = []
    seen: set[tuple[str, str]] = set()
    for rank in range(limit):
        for results in ranked:
            if rank >= len(results) or len(merged) == limit:
                continue
            chunk = results[rank]
            if (chunk.source, chunk.heading) not in seen:
                seen.add((chunk.source, chunk.heading))
                merged.append(chunk)
    return merged


def _nearest(db: Session, vector: list[float], limit: int) -> list[RetrievedChunk]:
    distance = KnowledgeChunk.embedding.cosine_distance(vector)
    rows = db.execute(
        select(KnowledgeChunk, distance.label("distance")).order_by(distance).limit(limit)
    )
    return [
        RetrievedChunk(
            source=chunk.source,
            title=chunk.title,
            heading=chunk.heading,
            content=chunk.content,
            score=1 - row_distance,
        )
        for chunk, row_distance in rows
    ]
