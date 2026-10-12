"""Answer a customer's question from the knowledge base, with sources (RAG)."""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.embeddings import Embedder
from app.ai.llm import ChatModel, ChatTurn, Document
from app.ai.prompts import HANDOFF_MESSAGE, RAG_SYSTEM_PROMPT
from app.ai.retrieval import RetrievedChunk, retrieve

TOP_K = 5


@dataclass(frozen=True)
class Source:
    """A knowledge chunk the answer cited; shown to the owner in the admin view."""

    source: str
    title: str
    heading: str
    cited_text: str


@dataclass(frozen=True)
class RagAnswer:
    text: str
    sources: list[Source]
    retrieved: list[RetrievedChunk]

    @property
    def grounded(self) -> bool:
        """True if the answer cites the knowledge base.

        An uncited reply ("I'm not sure, the owner will get back to you") means the
        knowledge base didn't cover the question: a structured signal for logging
        unanswered questions, with no need to parse the reply text.
        """
        return bool(self.sources)


def answer(
    db: Session, embedder: Embedder, llm: ChatModel, messages: Sequence[ChatTurn]
) -> RagAnswer:
    chunks = retrieve(db, embedder, retrieval_query(messages), limit=TOP_K)
    documents = [Document(title=f"{c.title}: {c.heading}", text=c.content) for c in chunks]

    result = llm.answer(system=RAG_SYSTEM_PROMPT, documents=documents, messages=messages)
    if result.refused or not result.text:
        return RagAnswer(text=HANDOFF_MESSAGE, sources=[], retrieved=chunks)

    sources, seen = [], set()
    for citation in result.citations:
        if citation.document_index in seen or not 0 <= citation.document_index < len(chunks):
            continue
        seen.add(citation.document_index)
        chunk = chunks[citation.document_index]
        sources.append(Source(chunk.source, chunk.title, chunk.heading, citation.cited_text))
    return RagAnswer(text=result.text, sources=sources, retrieved=chunks)


def retrieval_query(messages: Sequence[ChatTurn]) -> str:
    """Search with the latest two customer messages, not just the last one.

    Follow-ups like "how about shaggy?" only make sense with the message before them.
    """
    customer_messages = [turn.content for turn in messages if turn.role == "user"]
    return "\n".join(customer_messages[-2:])
