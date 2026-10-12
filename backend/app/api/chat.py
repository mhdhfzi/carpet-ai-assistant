from fastapi import APIRouter

from app.api.deps import ChatModelDep, DbSession, EmbedderDep
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import chat

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
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
