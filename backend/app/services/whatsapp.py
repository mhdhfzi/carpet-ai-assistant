"""WhatsApp Business Cloud API: verify webhook requests, read incoming messages, and reply.

Flow: Meta POSTs a signed webhook -> we check the signature and answer 200 at once (Meta
retries slow or failed deliveries) -> each message is handled in the background with the
same chat.reply() the web chat uses -> the reply is sent back through Meta's Graph API.
"""

import hashlib
import hmac
import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Protocol

import httpx2
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.embeddings import Embedder, EmbeddingError
from app.ai.llm import ChatModel, LLMError
from app.db.models import Channel, Conversation, Customer, Message, MessageRole
from app.services import chat

logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 4096  # WhatsApp's limit for one text message

UNSUPPORTED_REPLY = (
    "Maaf, saya hanya boleh membaca mesej teks buat masa ini. Sila taip soalan anda. / "
    "Sorry, I can only read text messages for now. Please type your question."
)
UNAVAILABLE_REPLY = (
    "Maaf, pembantu tidak dapat membalas sekarang. Pemilik akan menghubungi anda. / "
    "Sorry, the assistant can't reply right now. The owner will get back to you."
)

SessionFactory = Callable[[], AbstractContextManager[Session]]


class WhatsAppError(Exception):
    pass


# --- Webhook security and parsing ----------------------------------------------------------


def verify_signature(app_secret: str, body: bytes, signature_header: str | None) -> bool:
    """Check Meta's X-Hub-Signature-256 header: an HMAC-SHA256 of the raw body, keyed with
    the app secret. Without it, anyone who found the URL could post fake customer messages.

    compare_digest takes the same time whether the first or last character differs, so the
    signature can't be guessed one character at a time from response timings.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header.removeprefix("sha256="))


@dataclass(frozen=True)
class IncomingMessage:
    message_id: str  # WhatsApp's id ("wamid..."), used to ignore duplicate deliveries
    sender: str  # the customer's WhatsApp id: their number without "+", e.g. "60123456789"
    kind: str  # "text", "image", "audio", ...
    text: str | None  # None for anything but text


def parse_messages(payload: dict[str, Any]) -> list[IncomingMessage]:
    """Customer messages in a webhook payload. Delivery/read status updates are ignored."""
    if payload.get("object") != "whatsapp_business_account":
        return []
    messages = []
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            for raw in (change.get("value") or {}).get("messages") or []:
                if not raw.get("id") or not raw.get("from"):
                    continue
                kind = raw.get("type", "unknown")
                text = (raw.get("text") or {}).get("body") if kind == "text" else None
                messages.append(IncomingMessage(raw["id"], raw["from"], kind, text))
    return messages


# --- Sending -------------------------------------------------------------------------------


class WhatsAppClient(Protocol):
    def send_text(self, to: str, body: str) -> None: ...


class GraphWhatsAppClient:
    """Sends messages through Meta's Graph API (behind an interface, faked in tests)."""

    def __init__(
        self,
        access_token: str,
        phone_number_id: str,
        api_version: str,
        client: httpx2.Client | None = None,
    ) -> None:
        self._url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
        self._headers = {"Authorization": f"Bearer {access_token}"}
        self._client = client or httpx2.Client(
            timeout=15.0, transport=httpx2.HTTPTransport(retries=2)
        )

    def send_text(self, to: str, body: str) -> None:
        response = self._client.post(
            self._url,
            headers=self._headers,
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": body[:MAX_TEXT_LENGTH]},
            },
        )
        if response.is_error:
            raise WhatsAppError(f"WhatsApp API returned {response.status_code}: {response.text}")


# --- Handling messages ---------------------------------------------------------------------


def process_messages(
    session_factory: SessionFactory,
    embedder: Embedder,
    llm: ChatModel,
    client: WhatsAppClient,
    messages: list[IncomingMessage],
) -> None:
    """Background task: handle each message in its own session.

    Runs after the webhook has answered, when the request's session is already closed. One
    failing message is logged and doesn't stop the others.
    """
    for message in messages:
        try:
            with session_factory() as db:
                handle_message(db, embedder, llm, client, message)
        except Exception:
            logger.exception("Failed to handle WhatsApp message %s", message.message_id)


def handle_message(
    db: Session,
    embedder: Embedder,
    llm: ChatModel,
    client: WhatsAppClient,
    message: IncomingMessage,
) -> None:
    # Meta may deliver the same message more than once; reply only the first time.
    if db.scalar(select(Message.id).where(Message.external_id == message.message_id)):
        return
    conversation = _conversation_for(db, message.sender)

    if message.text is None:
        db.add(
            Message(
                conversation=conversation,
                role=MessageRole.CUSTOMER,
                content=f"[{message.kind} message]",
                external_id=message.message_id,
            )
        )
        db.commit()
        if not conversation.handed_off:
            _send(db, client, conversation, UNSUPPORTED_REPLY)
        return

    try:
        result = chat.reply(
            db, embedder, llm, conversation, message.text, external_id=message.message_id
        )
    except IntegrityError:
        # The unique external_id caught a duplicate being handled at the same moment.
        db.rollback()
        return
    except (LLMError, EmbeddingError):
        # The customer's message is already saved; tell them instead of staying silent.
        logger.exception("AI provider error while answering WhatsApp message")
        _send(db, client, conversation, UNAVAILABLE_REPLY)
        return

    if result.reply:
        _deliver(client, conversation.external_id, result.reply)


def _conversation_for(db: Session, wa_id: str) -> Conversation:
    """The customer's WhatsApp conversation, created on their first message.

    WhatsApp identifies people by phone number, so (unlike the web chat) the conversation
    can be linked to an existing customer straight away.
    """
    conversation = db.scalar(
        select(Conversation)
        .where(Conversation.channel == Channel.WHATSAPP, Conversation.external_id == wa_id)
        .order_by(Conversation.id.desc())
    )
    if conversation is None:
        customer = db.scalar(select(Customer).where(Customer.phone == f"+{wa_id}"))
        conversation = Conversation(channel=Channel.WHATSAPP, external_id=wa_id, customer=customer)
        db.add(conversation)
        db.flush()
    return conversation


def _send(db: Session, client: WhatsAppClient, conversation: Conversation, text: str) -> None:
    """Store a fixed assistant message (not generated by the AI) and send it."""
    db.add(Message(conversation=conversation, role=MessageRole.ASSISTANT, content=text))
    db.commit()
    _deliver(client, conversation.external_id, text)


def _deliver(client: WhatsAppClient, to: str, text: str) -> None:
    try:
        client.send_text(to, text)
    except WhatsAppError:
        # Logged rather than raised: the reply is stored, and the owner can follow up.
        logger.exception("Failed to send WhatsApp reply")
