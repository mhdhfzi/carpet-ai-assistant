from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.ingest import ingest
from app.ai.llm import ChatTurn, Citation, LLMError, ModelTurn
from app.api import deps
from app.db.models import Channel, Conversation, Message, MessageRole
from app.main import create_app
from app.services.chat import HISTORY_LIMIT
from tests.fakes import FakeChatModel, FakeEmbedder
from tests.test_ingest import write_doc


def send(client: TestClient, message: str, session_id: str | None = None) -> dict[str, Any]:
    response = client.post("/api/chat", json={"session_id": session_id, "message": message})
    assert response.status_code == 200, response.text
    return response.json()


def messages_of(db: Session, session_id: str) -> list[Message]:
    conversation = db.scalar(select(Conversation).where(Conversation.external_id == session_id))
    assert conversation is not None
    return list(
        db.scalars(select(Message).where(Message.conversation == conversation).order_by(Message.id))
    )


def test_first_message_starts_a_conversation(client: TestClient, db: Session) -> None:
    body = send(client, "Hi, are you open on Friday?")

    assert body["reply"] == "Hello from the fake model."
    assert body["handed_off"] is False
    assert len(body["session_id"]) >= 40  # random, unguessable token
    stored = messages_of(db, body["session_id"])
    assert [(m.role, m.content) for m in stored] == [
        (MessageRole.CUSTOMER, "Hi, are you open on Friday?"),
        (MessageRole.ASSISTANT, "Hello from the fake model."),
    ]
    conversation = db.scalar(
        select(Conversation).where(Conversation.external_id == body["session_id"])
    )
    assert conversation is not None and conversation.channel is Channel.WEB


def test_follow_up_messages_continue_with_history(
    client: TestClient, fake_llm: FakeChatModel
) -> None:
    session = send(client, "How much is Karpet Biasa?")["session_id"]

    body = send(client, "How about shaggy?", session)

    assert body["session_id"] == session
    assert fake_llm.calls[-1].messages == [
        ChatTurn("user", "How much is Karpet Biasa?"),
        ChatTurn("assistant", "Hello from the fake model."),
        ChatTurn("user", "How about shaggy?"),
    ]


def test_unknown_session_id_starts_a_new_conversation(client: TestClient) -> None:
    body = send(client, "Hello", session_id="made-up-by-the-client")

    assert body["session_id"] != "made-up-by-the-client"


def test_sessions_are_isolated(client: TestClient, fake_llm: FakeChatModel) -> None:
    send(client, "My address is 12 Jalan Rahsia")

    send(client, "What did I just tell you?")  # a different visitor: no session_id

    assert fake_llm.calls[-1].messages == [ChatTurn("user", "What did I just tell you?")]


def test_reply_sources_and_grounding_are_stored_for_the_owner(
    client: TestClient,
    db: Session,
    fake_llm: FakeChatModel,
    fake_embedder: FakeEmbedder,
    tmp_path: Path,
) -> None:
    write_doc(tmp_path, "hours.md", {"Opening hours": "We are closed on Fridays."})
    ingest(db, fake_embedder, tmp_path)
    fake_llm.script.append(ModelTurn("No, closed on Fridays.", citations=[Citation(0, "closed")]))

    body = send(client, "Are you open on Friday?")

    reply = messages_of(db, body["session_id"])[-1]
    assert reply.grounded is True
    assert reply.sources == [
        {
            "source": "hours.md",
            "title": "hours.md",
            "heading": "Opening hours",
            "cited_text": "closed",
        }
    ]
    assert "sources" not in body  # citations are for the owner's admin view, not the customer


def test_uncited_reply_is_stored_as_not_grounded(client: TestClient, db: Session) -> None:
    body = send(client, "Do you clean curtains?")  # fake model replies without citations

    reply = messages_of(db, body["session_id"])[-1]
    assert reply.grounded is False
    assert reply.sources == []


def test_history_is_limited_and_starts_with_a_customer_turn(
    client: TestClient, fake_llm: FakeChatModel
) -> None:
    session = send(client, "message 0")["session_id"]
    for i in range(1, 8):
        send(client, f"message {i}", session)

    turns = fake_llm.calls[-1].messages
    assert len(turns) <= HISTORY_LIMIT + 1
    assert turns[0].role == "user"
    assert turns[-1] == ChatTurn("user", "message 7")


def test_handed_off_conversation_gets_no_ai_reply(
    client: TestClient, db: Session, fake_llm: FakeChatModel
) -> None:
    session = send(client, "I want to complain")["session_id"]
    conversation = db.scalar(select(Conversation).where(Conversation.external_id == session))
    assert conversation is not None
    conversation.handed_off = True
    db.commit()
    calls_before = len(fake_llm.calls)

    body = send(client, "Hello? Anyone there?", session)

    assert body == {"session_id": session, "reply": None, "handed_off": True}
    assert len(fake_llm.calls) == calls_before
    assert messages_of(db, session)[-1].content == "Hello? Anyone there?"  # still saved


@pytest.mark.parametrize("message", ["", "   ", "x" * 2001])
def test_invalid_messages_are_rejected(client: TestClient, message: str) -> None:
    assert client.post("/api/chat", json={"message": message}).status_code == 422


def test_ai_failure_returns_503_but_keeps_the_customer_message(
    client: TestClient, db: Session, fake_llm: FakeChatModel
) -> None:
    def broken(**_: Any) -> ModelTurn:
        raise LLMError("upstream exploded with secret details")

    fake_llm.respond = broken  # type: ignore[method-assign]

    response = client.post("/api/chat", json={"message": "Are you open today?"})

    assert response.status_code == 503
    assert "secret" not in response.text
    stored = db.scalars(select(Message).where(Message.content == "Are you open today?")).all()
    assert len(stored) == 1


def test_missing_api_key_returns_503(
    db: Session, fake_embedder: FakeEmbedder, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_key() -> ModelTurn:
        raise LLMError("ANTHROPIC_API_KEY is not set")

    monkeypatch.setattr(deps, "get_chat_model", no_key)
    deps.chat_model_dependency.cache_clear()
    app = create_app()
    app.dependency_overrides[deps.get_db] = lambda: db
    app.dependency_overrides[deps.embedder_dependency] = lambda: fake_embedder

    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": "Hello"})

    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" not in response.text


# --- History (restoring the widget after a page reload) ------------------------------------


def test_history_returns_the_conversation_without_internal_fields(
    client: TestClient, fake_llm: FakeChatModel
) -> None:
    fake_llm.script.append(ModelTurn("We're closed on Fridays.", citations=[Citation(0, "x")]))
    session = send(client, "Are you open Friday?")["session_id"]

    response = client.get(f"/api/chat/{session}")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session
    assert body["handed_off"] is False
    assert [(m["role"], m["content"]) for m in body["messages"]] == [
        ("customer", "Are you open Friday?"),
        ("assistant", "We're closed on Fridays."),
    ]
    assert set(body["messages"][0]) == {"role", "content", "created_at"}  # no sources


def test_history_of_an_unknown_session_is_404(client: TestClient) -> None:
    assert client.get("/api/chat/not-a-real-session").status_code == 404


def test_history_shows_handoff(client: TestClient, db: Session) -> None:
    session = send(client, "Hi")["session_id"]
    conversation = db.scalar(select(Conversation).where(Conversation.external_id == session))
    assert conversation is not None
    conversation.handed_off = True
    db.commit()

    assert client.get(f"/api/chat/{session}").json()["handed_off"] is True


# --- CORS ------------------------------------------------------------------------------------


def cors_client(db: Session, monkeypatch: pytest.MonkeyPatch, origins: str) -> TestClient:
    from app.core.config import get_settings

    monkeypatch.setenv("CORS_ORIGINS", origins)
    get_settings.cache_clear()
    app = create_app()
    get_settings.cache_clear()
    app.dependency_overrides[deps.get_db] = lambda: db
    return TestClient(app)


def preflight(client: TestClient, origin: str):
    return client.options(
        "/api/chat",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )


def test_cors_allows_only_listed_sites(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    client = cors_client(db, monkeypatch, "https://cucicucisenawang.com/, https://example.org")

    allowed = preflight(client, "https://cucicucisenawang.com")
    blocked = preflight(client, "https://evil.example")

    assert allowed.headers["access-control-allow-origin"] == "https://cucicucisenawang.com"
    assert "access-control-allow-origin" not in blocked.headers


def test_no_cors_by_default(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    client = cors_client(db, monkeypatch, "")

    assert "access-control-allow-origin" not in preflight(client, "https://x.example").headers
