from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.ai import rag
from app.ai.ingest import ingest
from app.ai.llm import ChatTurn, Citation, LLMAnswer
from app.ai.prompts import HANDOFF_MESSAGE
from app.ai.retrieval import retrieve
from tests.fakes import FakeChatModel, FakeEmbedder
from tests.test_ingest import write_doc


@pytest.fixture
def embedder(db: Session, tmp_path: Path) -> FakeEmbedder:
    write_doc(
        tmp_path,
        "hours.md",
        {
            "Opening hours": "We are open every day except Friday, 9 am to 5.30 pm.",
            "Public holidays": "We are usually closed on public holidays.",
        },
    )
    write_doc(tmp_path, "carpets.md", {"Carpet return": "Carpets are returned in 5 to 7 days."})
    embedder = FakeEmbedder()
    ingest(db, embedder, tmp_path)
    return embedder


def ask(text: str) -> list[ChatTurn]:
    return [ChatTurn("user", text)]


def test_retrieve_ranks_the_most_similar_chunk_first(db: Session, embedder: FakeEmbedder) -> None:
    chunks = retrieve(db, embedder, "are you open on friday", limit=2)

    assert chunks[0].heading == "Opening hours"
    assert chunks[0].score > chunks[1].score


def test_answer_passes_retrieved_chunks_and_maps_citations_to_sources(
    db: Session, embedder: FakeEmbedder
) -> None:
    llm = FakeChatModel(
        LLMAnswer(
            "No, we're closed on Fridays.",
            citations=[Citation(0, "open every day except Friday")],
        )
    )

    result = rag.answer(db, embedder, llm, ask("Are you open on Friday?"))

    call = llm.calls[0]
    assert call.documents[0].title == "hours.md: Opening hours"
    assert "except Friday" in call.documents[0].text
    assert "Never guess" in call.system
    assert result.text == "No, we're closed on Fridays."
    assert [(s.source, s.heading) for s in result.sources] == [("hours.md", "Opening hours")]
    assert result.grounded


def test_answer_without_citations_is_not_grounded(db: Session, embedder: FakeEmbedder) -> None:
    llm = FakeChatModel(LLMAnswer("I'm not sure, the owner will get back to you."))

    result = rag.answer(db, embedder, llm, ask("Do you clean curtains?"))

    assert not result.grounded
    assert result.sources == []


def test_duplicate_and_out_of_range_citations_are_ignored(
    db: Session, embedder: FakeEmbedder
) -> None:
    llm = FakeChatModel(
        LLMAnswer(
            "Closed Fridays.", citations=[Citation(0, "a"), Citation(0, "b"), Citation(99, "x")]
        )
    )

    result = rag.answer(db, embedder, llm, ask("Friday?"))

    assert [s.cited_text for s in result.sources] == ["a"]


def test_refusal_returns_the_handoff_message(db: Session, embedder: FakeEmbedder) -> None:
    llm = FakeChatModel(LLMAnswer("", refused=True))

    result = rag.answer(db, embedder, llm, ask("Something odd"))

    assert result.text == HANDOFF_MESSAGE
    assert not result.grounded


def test_retrieval_query_includes_the_previous_customer_message() -> None:
    messages = [
        ChatTurn("user", "How much is Karpet Biasa?"),
        ChatTurn("assistant", "RM1.80 per square foot."),
        ChatTurn("user", "How about shaggy?"),
    ]

    assert rag.retrieval_query(messages) == "How much is Karpet Biasa?\nHow about shaggy?"


def test_full_conversation_is_passed_to_the_model(db: Session, embedder: FakeEmbedder) -> None:
    llm = FakeChatModel(LLMAnswer("Yes."))
    messages = [
        ChatTurn("user", "Hi"),
        ChatTurn("assistant", "Hello! How can I help?"),
        ChatTurn("user", "Are you open Friday?"),
    ]

    rag.answer(db, embedder, llm, messages)

    assert llm.calls[0].messages == messages
