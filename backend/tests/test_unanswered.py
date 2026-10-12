from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.ingest import ingest
from app.ai.llm import ModelTurn, ToolCall
from app.db.models import Message, MessageRole, UnansweredQuestion, UnansweredReason
from tests.fakes import FakeChatModel, FakeEmbedder, tool_turn
from tests.test_ingest import write_doc


def send(client: TestClient, message: str, session_id: str | None = None) -> dict[str, Any]:
    response = client.post("/api/chat", json={"session_id": session_id, "message": message})
    assert response.status_code == 200, response.text
    return response.json()


def logged(db: Session) -> list[UnansweredQuestion]:
    return list(db.scalars(select(UnansweredQuestion).order_by(UnansweredQuestion.id)))


def test_answered_questions_and_small_talk_are_not_logged(
    client: TestClient, db: Session, fake_llm: FakeChatModel
) -> None:
    fake_llm.script += [ModelTurn("Hello! How can I help?"), ModelTurn("We're closed on Fridays.")]

    send(client, "Hi")
    send(client, "Are you open on Friday?")

    assert logged(db) == []


def test_flagged_question_is_logged_with_the_customer_message(
    client: TestClient,
    db: Session,
    fake_llm: FakeChatModel,
    fake_embedder: FakeEmbedder,
    tmp_path: Path,
) -> None:
    write_doc(tmp_path, "services.md", {"Carpets": "We clean carpets, sofas and mattresses."})
    ingest(db, fake_embedder, tmp_path)
    fake_llm.script += [
        tool_turn("flag_unanswered_question", question="Do you clean curtains?"),
        ModelTurn("I'm not sure, the owner will get back to you."),
    ]

    send(client, "Boleh cuci langsir tak?")

    [entry] = logged(db)
    assert entry.reason is UnansweredReason.NO_ANSWER
    assert entry.question == "Do you clean curtains?"  # summarised for the owner
    message = db.get(Message, entry.message_id)
    assert message is not None and message.role is MessageRole.CUSTOMER
    assert message.content == "Boleh cuci langsir tak?"  # original wording kept
    assert entry.top_score is not None
    assert entry.resolved is False


def test_handoff_is_logged_with_its_reason(
    client: TestClient, db: Session, fake_llm: FakeChatModel
) -> None:
    fake_llm.script += [
        tool_turn("handoff_to_human", reason="Customer upset about a late return"),
        ModelTurn("Sorry! The owner will reply here soon."),
    ]

    send(client, "Where is my carpet?? It's been 2 weeks!")

    [entry] = logged(db)
    assert entry.reason is UnansweredReason.HANDED_OFF
    assert entry.question == "Where is my carpet?? It's been 2 weeks!"
    assert entry.detail == "Customer upset about a late return"


def test_giving_up_is_logged(client: TestClient, db: Session, fake_llm: FakeChatModel) -> None:
    fake_llm.script.append(ModelTurn("", refused=True))

    send(client, "Something strange")

    [entry] = logged(db)
    assert entry.reason is UnansweredReason.GAVE_UP


def test_one_entry_per_message_and_reason(
    client: TestClient, db: Session, fake_llm: FakeChatModel
) -> None:
    fake_llm.script += [
        ModelTurn(
            "",
            tool_calls=[
                ToolCall("a", "flag_unanswered_question", {"question": "Curtains?"}),
                ToolCall("b", "flag_unanswered_question", {"question": "Curtains?"}),
                ToolCall("c", "handoff_to_human", {"reason": "Can't help"}),
            ],
        ),
        ModelTurn("The owner will reply soon."),
    ]

    send(client, "Curtains? Or a person please")

    assert sorted(e.reason for e in logged(db)) == [
        UnansweredReason.HANDED_OFF,
        UnansweredReason.NO_ANSWER,
    ]


def test_owner_lists_and_resolves_questions(
    client: TestClient, db: Session, fake_llm: FakeChatModel
) -> None:
    fake_llm.script += [
        tool_turn("flag_unanswered_question", question="Do you clean curtains?"),
        ModelTurn("Not sure, the owner will get back to you."),
    ]
    send(client, "Do you clean curtains?")

    [entry] = client.get("/api/unanswered-questions").json()
    assert entry["question"] == "Do you clean curtains?"
    assert entry["reason"] == "no_answer"

    response = client.patch(f"/api/unanswered-questions/{entry['id']}", json={"resolved": True})

    assert response.json()["resolved"] is True
    assert client.get("/api/unanswered-questions").json() == []
    resolved = client.get("/api/unanswered-questions", params={"resolved": True}).json()
    assert [e["id"] for e in resolved] == [entry["id"]]


def test_resolving_a_missing_question_returns_404(client: TestClient) -> None:
    response = client.patch("/api/unanswered-questions/999999", json={"resolved": True})

    assert response.status_code == 404
