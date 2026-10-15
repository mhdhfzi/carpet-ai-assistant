"""Retrieval-augmented generation helpers: what to search for, how retrieved chunks are
given to the model, and how the model's citations map back to knowledge sources."""

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


def retrieval_queries(messages: Sequence[ChatTurn]) -> list[str]:
    """What to search for: the latest customer message on its own, then the latest two
    together.

    The pair is for follow-ups like "how about shaggy?", which only make sense with the
    message before. The latest message alone is for new questions: joined to a long earlier
    message, a short "Kedai kat mana?" is drowned out and its answer never retrieved.
    """
    customer_messages = [turn.content for turn in messages if turn.role == "user"]
    queries = customer_messages[-1:]
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
