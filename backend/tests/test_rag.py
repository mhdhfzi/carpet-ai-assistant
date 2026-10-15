from pathlib import Path

from sqlalchemy.orm import Session

from app.ai import rag
from app.ai.ingest import ingest
from app.ai.llm import ChatTurn, Citation
from app.ai.retrieval import RetrievedChunk, retrieve, retrieve_for
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


def test_retrieval_queries_are_the_latest_message_then_the_last_two_together() -> None:
    messages = [
        ChatTurn("user", "How much is Karpet Biasa?"),
        ChatTurn("assistant", "RM1.80 per square foot."),
        ChatTurn("user", "How about shaggy?"),
    ]

    assert rag.retrieval_queries(messages) == [
        "How about shaggy?",
        "How much is Karpet Biasa?\nHow about shaggy?",
    ]
    assert rag.retrieval_queries(messages[:1]) == ["How much is Karpet Biasa?"]


def test_a_short_new_question_is_not_drowned_out_by_a_long_earlier_message(
    db: Session, tmp_path: Path
) -> None:
    """Interleaving gives the latest message its own best match, even when the earlier
    message dominates the combined query."""
    write_doc(
        tmp_path,
        "faq.md",
        {
            "Sofa cleaning": "Sofa cleaning is priced per sofa seat; a sofa seat cleaning price.",
            "Mattress cleaning": "Mattress cleaning is priced per mattress, sofa seats separately.",
            "Shop address": "Our shop is at Taipan 2, Senawang.",
        },
    )
    embedder = FakeEmbedder()
    ingest(db, embedder, tmp_path)
    earlier = "How much is sofa seat cleaning, the sofa seat price, and mattress cleaning?"
    combined = f"{earlier}\nWhere is your shop?"

    alone = retrieve(db, embedder, combined, limit=2)
    both = retrieve_for(db, embedder, ["Where is your shop?", combined], limit=2)

    assert "Shop address" not in [c.heading for c in alone]  # the bug this fixes
    assert [c.heading for c in both][0] == "Shop address"
    assert len({c.heading for c in both}) == len(both) == 2
