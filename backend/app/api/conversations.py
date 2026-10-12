"""Conversations as the owner sees them: every message, with the sources the AI cited."""

from fastapi import APIRouter
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, RequireOwner
from app.db.models import Conversation
from app.schemas.chat import ConversationRead
from app.services.errors import NotFoundError

router = APIRouter(prefix="/api/conversations", tags=["conversations"], dependencies=[RequireOwner])


@router.get("/{conversation_id}", response_model=ConversationRead)
def get_conversation(conversation_id: int, db: DbSession) -> Conversation:
    conversation = db.get(
        Conversation,
        conversation_id,
        options=[selectinload(Conversation.messages), selectinload(Conversation.customer)],
    )
    if conversation is None:
        raise NotFoundError(f"Conversation {conversation_id} not found")
    return conversation
