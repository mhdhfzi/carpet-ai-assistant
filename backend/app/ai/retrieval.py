"""Find the knowledge chunks most relevant to a question (the "R" in RAG)."""

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
    vector = embedder.embed_query(query)
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
