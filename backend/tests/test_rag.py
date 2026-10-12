from pathlib import Path

from sqlalchemy.orm import Session

from app.ai import rag
from app.ai.ingest import ingest
from app.ai.llm import ChatTurn, Citation
from app.ai.retrieval import RetrievedChunk, retrieve
from tests.fakes import FakeEmbedder
from tests.test_ingest import write_doc

CHUNKS = [
    RetrievedChunk("hours.md", "Hours", "Opening hours", "Closed on Fridays.", 0.7),
    RetrievedChunk("faq.md", "FAQ", "Carpet return", "Returned in 5 to 7 days.", 0.5),
]


def test_retrieve_ranks_the_most_similar_chunk_first(db: Session, tmp_path: Path) -> None:
    write_doc(
        tmp_path,
        "hours.md",
        {
            "Opening hours": "We are open every day except Friday, 9 am to 5.30 pm.",
            "Public holidays": "We are usually closed on public holidays.",
        },
    )
    embedder = FakeEmbedder()
    ingest(db, embedder, tmp_path)

    chunks = retrieve(db, embedder, "are you open on friday", limit=2)

    assert chunks[0].heading == "Opening hours"
    assert chunks[0].score > chunks[1].score


def test_documents_are_titled_with_document_and_section() -> None:
    documents = rag.to_documents(CHUNKS)

    assert [d.title for d in documents] == ["Hours: Opening hours", "FAQ: Carpet return"]
    assert documents[0].text == "Closed on Fridays."


def test_citations_map_to_sources_once_each() -> None:
    citations = [Citation(1, "5 to 7 days"), Citation(1, "again"), Citation(0, "Fridays")]

    sources = rag.cited_sources(citations, CHUNKS)

    assert [(s.source, s.cited_text) for s in sources] == [
        ("faq.md", "5 to 7 days"),
        ("hours.md", "Fridays"),
    ]


def test_out_of_range_citations_are_ignored() -> None:
    assert rag.cited_sources([Citation(99, "x"), Citation(-1, "y")], CHUNKS) == []


def test_retrieval_query_includes_the_previous_customer_message() -> None:
    messages = [
        ChatTurn("user", "How much is Karpet Biasa?"),
        ChatTurn("assistant", "RM1.80 per square foot."),
        ChatTurn("user", "How about shaggy?"),
    ]

    assert rag.retrieval_query(messages) == "How much is Karpet Biasa?\nHow about shaggy?"
