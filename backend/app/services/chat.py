"""Customer conversations: store messages and generate the assistant's reply.

`reply` is channel-independent: the web chat and the WhatsApp webhook both use it.
Conversations are stored so the owner can review them and take over.
"""

import secrets
from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import agent
from app.ai.embeddings import Embedder
from app.ai.llm import ChatModel, ChatTurn
from app.ai.tools import ToolContext
from app.db.models import Channel, Conversation, Message, MessageRole, UnansweredReason
from app.services import unanswered
from app.services.errors import NotFoundError

# How many earlier messages the model sees. Enough for follow-up questions while keeping
# each request small (cost and latency grow with history).
HISTORY_LIMIT = 10


@dataclass(frozen=True)
class ChatResult:
    conversation: Conversation
    reply: str | None  # None when a human has taken over the conversation


def handle_web_message(
    db: Session, embedder: Embedder, llm: ChatModel, session_id: str | None, text: str
) -> ChatResult:
    conversation = _find_web_conversation(db, session_id) or _start_web_conversation(db)
    return reply(db, embedder, llm, conversation, text)


def reply(
    db: Session,
    embedder: Embedder,
    llm: ChatModel,
    conversation: Conversation,
    text: str,
    *,
    external_id: str | None = None,
) -> ChatResult:
    history = _recent_turns(db, conversation)

    # Save the customer's message first, in its own transaction: if the AI call fails,
    # the owner still sees what the customer asked.
    customer_message = Message(
        conversation=conversation, role=MessageRole.CUSTOMER, content=text, external_id=external_id
    )
    db.add(customer_message)
    db.commit()

    if conversation.handed_off:
        return ChatResult(conversation, reply=None)

    ctx = ToolContext(db=db, conversation=conversation, customer_message_id=customer_message.id)
    answer = agent.run(ctx, embedder, llm, [*history, ChatTurn("user", text)])
    db.add(
        Message(
            conversation=conversation,
            role=MessageRole.ASSISTANT,
            content=answer.text,
            sources=[asdict(source) for source in answer.sources],
            grounded=answer.grounded,
        )
    )
    if answer.gave_up:
        unanswered.log_question(
            db,
            conversation,
            customer_message.id,
            UnansweredReason.GAVE_UP,
            top_score=ctx.top_score,
        )
    db.commit()
    return ChatResult(conversation, reply=answer.text)


def _find_web_conversation(db: Session, session_id: str | None) -> Conversation | None:
    if not session_id:
        return None
    return db.scalar(
        select(Conversation).where(
            Conversation.channel == Channel.WEB, Conversation.external_id == session_id
        )
    )


def _start_web_conversation(db: Session) -> Conversation:
    """New conversation with a random, unguessable session token.

    The web chat has no login, so the token is the only thing tying a visitor to their
    conversation. Database IDs would be guessable; client-chosen tokens could collide with
    (or deliberately target) someone else's.
    """
    conversation = Conversation(channel=Channel.WEB, external_id=secrets.token_urlsafe(32))
    db.add(conversation)
    db.flush()
    return conversation


def _recent_turns(db: Session, conversation: Conversation) -> list[ChatTurn]:
    if conversation.id is None:
        return []
    messages = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.id.desc())
        .limit(HISTORY_LIMIT)
    ).all()
    # Staff replies are shown to the model as assistant turns: they speak for the business.
    turns = [
        ChatTurn("user" if m.role is MessageRole.CUSTOMER else "assistant", m.content)
        for m in reversed(messages)
    ]
    # The model's input must start with a customer turn; the cut-off may land mid-exchange.
    while turns and turns[0].role == "assistant":
        turns.pop(0)
    return turns


def web_history(
    db: Session, session_id: str, *, limit: int = 100
) -> tuple[Conversation, list[Message]]:
    """The latest messages of a web conversation, oldest first, for reloading the widget."""
    conversation = _find_web_conversation(db, session_id)
    if conversation is None:
        raise NotFoundError("Conversation not found")
    messages = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.id.desc())
        .limit(limit)
    ).all()
    return conversation, list(reversed(messages))
