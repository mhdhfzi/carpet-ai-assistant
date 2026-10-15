from fastapi import APIRouter, Depends, Path

from app.api.deps import ChatModelDep, DbSession, EmbedderDep
from app.core.rate_limit import chat_limiter, history_limiter
from app.schemas.chat import ChatHistory, ChatMessageRead, ChatRequest, ChatResponse, ChatStatus
from app.services import assistant_status, chat

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse, dependencies=[Depends(chat_limiter)])
def send_message(
    data: ChatRequest, db: DbSession, embedder: EmbedderDep, llm: ChatModelDep
) -> ChatResponse:
    """Send a customer message from the web chat and get the assistant's reply."""
    result = chat.handle_web_message(db, embedder, llm, data.session_id, data.message)
    return ChatResponse(
        session_id=result.conversation.external_id,
        reply=result.reply,
        handed_off=result.conversation.handed_off,
    )


# Declared before /{session_id}, which would otherwise match "status".
@router.get("/status", response_model=ChatStatus, dependencies=[Depends(history_limiter)])
def chat_status(db: DbSession) -> ChatStatus:
    """Whether the chat can answer right now. The widget asks on every page load and shows
    its button only if it can. Cheap: no AI call."""
    return ChatStatus(available=assistant_status.is_available(db))


@router.get("/{session_id}", response_model=ChatHistory, dependencies=[Depends(history_limiter)])
def get_history(session_id: str = Path(max_length=100), *, db: DbSession) -> ChatHistory:
    """Messages of a web conversation, so the widget can restore it after a page reload.

    The session token is the only key: an unknown token is a plain 404, revealing nothing
    about other conversations.
    """
    conversation, messages = chat.web_history(db, session_id)
    return ChatHistory(
        session_id=conversation.external_id,
        handed_off=conversation.handed_off,
        messages=[ChatMessageRead.model_validate(m) for m in messages],
    )
