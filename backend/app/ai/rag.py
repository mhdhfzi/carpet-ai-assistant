"""Retrieval-augmented generation helpers: what to search for, how retrieved chunks are
given to the model, and how the model's citations map back to knowledge sources."""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.ai.llm import ChatTurn, Citation, Document
from app.ai.retrieval import RetrievedChunk


@dataclass(frozen=True)
class Source:
    """A knowledge chunk the answer cited; shown to the owner in the admin view."""

    source: str
    title: str
    heading: str
    cited_text: str


# A question ends at ?, ! or a full stop followed by a space, or at a line break.
_QUESTION_END = re.compile(r"(?<=[?!.])\s+|\n+")
MAX_PARTS = 3


def retrieval_queries(messages: Sequence[ChatTurn]) -> list[str]:
    """What to search for: the latest customer message, then each question in it if it asks
    several, then the latest two messages together.

    One query per question, because the strongest topic otherwise takes every result: in
    "Hari Jumaat buka tak? Berapa harga cuci tilam queen?" the mattress prices crowded out
    the opening hours. The pair is for follow-ups like "how about shaggy?", which only make
    sense with the message before; the latest message alone keeps a short new question from
    being drowned out by a long earlier one.
    """
    customer_messages = [turn.content for turn in messages if turn.role == "user"]
    if not customer_messages:
        return []
    latest = customer_messages[-1]
    queries = [latest]
    parts = [p.strip() for p in _QUESTION_END.split(latest) if len(p.strip()) >= 3]
    if len(parts) > 1:
        queries += parts[:MAX_PARTS]
    if len(customer_messages) >= 2:
        queries.append("\n".join(customer_messages[-2:]))
    return queries


def to_documents(chunks: Sequence[RetrievedChunk]) -> list[Document]:
    return [Document(title=f"{c.title}: {c.heading}", text=c.content) for c in chunks]


def cited_sources(citations: Sequence[Citation], chunks: Sequence[RetrievedChunk]) -> list[Source]:
    """One Source per cited chunk, in citation order; invalid indexes are ignored."""
    sources, seen = [], set()
    for citation in citations:
        index = citation.document_index
        if index in seen or not 0 <= index < len(chunks):
            continue
        seen.add(index)
        chunk = chunks[index]
        sources.append(Source(chunk.source, chunk.title, chunk.heading, citation.cited_text))
    return sources
