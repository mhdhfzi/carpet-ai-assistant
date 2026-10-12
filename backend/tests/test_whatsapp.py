"""WhatsApp webhook with signed, Meta-shaped payloads and a fake sending client."""

import hashlib
import hmac
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.llm import LLMError, ModelTurn
from app.api.deps import WhatsAppConfig, whatsapp_config_dependency
from app.db.models import Channel, Conversation, Customer, Message, MessageRole
from app.services.whatsapp import (
    UNAVAILABLE_REPLY,
    UNSUPPORTED_REPLY,
    parse_messages,
    verify_signature,
)
from tests.conftest import WHATSAPP_TEST_CONFIG
from tests.fakes import FakeChatModel, FakeWhatsAppClient

SECRET = WHATSAPP_TEST_CONFIG.app_secret or ""
CUSTOMER = "60123456789"


def text_message(text: str, message_id: str = "wamid.1", sender: str = CUSTOMER) -> dict:
    return {
        "from": sender,
        "id": message_id,
        "timestamp": "1791777600",
        "type": "text",
        "text": {"body": text},
    }


def payload(*messages: dict, statuses: list[dict] | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "metadata": {"display_phone_number": "60120000000", "phone_number_id": "123"},
        "contacts": [{"profile": {"name": "Aminah"}, "wa_id": CUSTOMER}],
        "messages": list(messages),
    }
    if statuses is not None:
        value = {**value, "messages": [], "statuses": statuses}
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "999", "changes": [{"field": "messages", "value": value}]}],
    }


def sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def post(client: TestClient, data: dict, signature: str | None = "valid"):
    body = json.dumps(data).encode()
    headers = {"Content-Type": "application/json"}
    if signature == "valid":
        headers["X-Hub-Signature-256"] = sign(body)
    elif signature is not None:
        headers["X-Hub-Signature-256"] = signature
    return client.post("/api/whatsapp/webhook", content=body, headers=headers)


def message_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Message)) or 0


# --- Verification handshake ------------------------------------------------------------------


def test_meta_verification_handshake(client: TestClient) -> None:
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "test-verify-token",
        "hub.challenge": "42",
    }

    response = client.get("/api/whatsapp/webhook", params=params)

    assert response.status_code == 200
    assert response.text == "42"


@pytest.mark.parametrize(
    "params",
    [
        {"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "42"},
        {"hub.mode": "unsubscribe", "hub.verify_token": "test-verify-token", "hub.challenge": "42"},
    ],
)
def test_verification_rejects_wrong_token_or_mode(client: TestClient, params: dict) -> None:
    assert client.get("/api/whatsapp/webhook", params=params).status_code == 403


# --- Signature ------------------------------------------------------------------------------


def test_signature_check() -> None:
    body = b'{"hello": "world"}'

    assert verify_signature("s3cret", body, sign(body, "s3cret"))
    assert not verify_signature("s3cret", body, sign(body, "other-secret"))
    assert not verify_signature("s3cret", body + b" ", sign(body, "s3cret"))  # tampered
    assert not verify_signature("s3cret", body, None)
    assert not verify_signature("s3cret", body, "md5=abc")


@pytest.mark.parametrize("signature", [None, "sha256=deadbeef"])
def test_unsigned_or_forged_requests_are_rejected_and_not_processed(
    client: TestClient, db: Session, fake_llm: FakeChatModel, signature: str | None
) -> None:
    response = post(client, payload(text_message("Hi")), signature=signature)

    assert response.status_code == 401
    assert fake_llm.calls == [] and message_count(db) == 0


def test_webhook_refuses_everything_when_not_configured(client: TestClient) -> None:
    client.app.dependency_overrides[whatsapp_config_dependency] = lambda: WhatsAppConfig(None, None)

    assert post(client, payload(text_message("Hi"))).status_code == 503


# --- Messages -------------------------------------------------------------------------------


def test_text_message_gets_an_ai_reply_on_whatsapp(
    client: TestClient,
    db: Session,
    fake_llm: FakeChatModel,
    fake_whatsapp: FakeWhatsAppClient,
) -> None:
    fake_llm.script.append(ModelTurn("Cuci sofa RM60 satu tempat duduk."))

    response = post(client, payload(text_message("Berapa harga cuci sofa?")))

    assert response.status_code == 200
    assert fake_whatsapp.sent == [(CUSTOMER, "Cuci sofa RM60 satu tempat duduk.")]
    conversation = db.scalar(select(Conversation).where(Conversation.channel == Channel.WHATSAPP))
    assert conversation is not None and conversation.external_id == CUSTOMER
    stored = list(db.scalars(select(Message).order_by(Message.id)))
    assert [(m.role, m.external_id) for m in stored] == [
        (MessageRole.CUSTOMER, "wamid.1"),
        (MessageRole.ASSISTANT, None),
    ]


def test_duplicate_delivery_is_answered_once(
    client: TestClient, db: Session, fake_llm: FakeChatModel, fake_whatsapp: FakeWhatsAppClient
) -> None:
    data = payload(text_message("Hi", message_id="wamid.same"))

    post(client, data)
    post(client, data)  # Meta retrying the same delivery

    assert len(fake_llm.calls) == 1
    assert len(fake_whatsapp.sent) == 1
    assert db.scalar(select(func.count()).where(Message.external_id == "wamid.same")) == 1


def test_follow_ups_continue_the_same_conversation(
    client: TestClient, db: Session, fake_llm: FakeChatModel
) -> None:
    post(client, payload(text_message("Hi", message_id="wamid.1")))
    post(client, payload(text_message("Sofa price?", message_id="wamid.2")))

    assert db.scalar(select(func.count()).select_from(Conversation)) == 1
    assert [t.content for t in fake_llm.calls[-1].messages] == [
        "Hi",
        "Hello from the fake model.",
        "Sofa price?",
    ]


def test_conversation_is_linked_to_an_existing_customer(client: TestClient, db: Session) -> None:
    db.add(Customer(name="Aminah", phone=f"+{CUSTOMER}"))
    db.flush()

    post(client, payload(text_message("Hi")))

    conversation = db.scalar(select(Conversation))
    assert conversation is not None and conversation.customer is not None
    assert conversation.customer.name == "Aminah"


def test_non_text_messages_get_a_polite_reply_without_the_ai(
    client: TestClient, db: Session, fake_llm: FakeChatModel, fake_whatsapp: FakeWhatsAppClient
) -> None:
    image = {"from": CUSTOMER, "id": "wamid.img", "type": "image", "image": {"id": "media-1"}}

    post(client, payload(image))

    assert fake_llm.calls == []
    assert fake_whatsapp.sent == [(CUSTOMER, UNSUPPORTED_REPLY)]
    stored = db.scalar(select(Message).where(Message.external_id == "wamid.img"))
    assert stored is not None and stored.content == "[image message]"


def test_status_updates_are_ignored(
    client: TestClient, fake_llm: FakeChatModel, fake_whatsapp: FakeWhatsAppClient
) -> None:
    statuses = [{"id": "wamid.1", "status": "delivered", "recipient_id": CUSTOMER}]

    response = post(client, payload(statuses=statuses))

    assert response.status_code == 200
    assert fake_llm.calls == [] and fake_whatsapp.sent == []


def test_handed_off_conversation_gets_no_ai_reply(
    client: TestClient, db: Session, fake_llm: FakeChatModel, fake_whatsapp: FakeWhatsAppClient
) -> None:
    db.add(Conversation(channel=Channel.WHATSAPP, external_id=CUSTOMER, handed_off=True))
    db.flush()

    post(client, payload(text_message("Hello?")))

    assert fake_llm.calls == [] and fake_whatsapp.sent == []
    assert db.scalar(select(Message.content)) == "Hello?"  # saved for the owner


def test_ai_failure_sends_an_apology_instead_of_silence(
    client: TestClient, db: Session, fake_llm: FakeChatModel, fake_whatsapp: FakeWhatsAppClient
) -> None:
    def broken(**_: Any) -> ModelTurn:
        raise LLMError("upstream down")

    fake_llm.respond = broken  # type: ignore[method-assign]

    response = post(client, payload(text_message("Hi")))

    assert response.status_code == 200
    assert fake_whatsapp.sent == [(CUSTOMER, UNAVAILABLE_REPLY)]


def test_several_messages_in_one_delivery(
    client: TestClient, fake_whatsapp: FakeWhatsAppClient
) -> None:
    post(
        client,
        payload(
            text_message("Hi", message_id="wamid.a"),
            text_message("Hello", message_id="wamid.b", sender="60111111111"),
        ),
    )

    assert sorted(to for to, _ in fake_whatsapp.sent) == ["60111111111", CUSTOMER]


def test_parse_ignores_other_webhooks_and_malformed_entries() -> None:
    assert parse_messages({"object": "page", "entry": []}) == []
    malformed = payload({"type": "text", "text": {"body": "no id or sender"}})
    assert parse_messages(malformed) == []


def test_invalid_json_is_rejected(client: TestClient) -> None:
    body = b"not json"
    response = client.post(
        "/api/whatsapp/webhook", content=body, headers={"X-Hub-Signature-256": sign(body)}
    )

    assert response.status_code == 400
