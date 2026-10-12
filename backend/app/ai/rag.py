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


def retrieval_query(messages: Sequence[ChatTurn]) -> str:
    """Search with the latest two customer messages, not just the last one.

    Follow-ups like "how about shaggy?" only make sense with the message before them.
    """
    customer_messages = [turn.content for turn in messages if turn.role == "user"]
    return "\n".join(customer_messages[-2:])


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
