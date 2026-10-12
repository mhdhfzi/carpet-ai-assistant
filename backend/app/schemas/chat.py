from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.db.models import MessageRole

MessageText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]


class ChatRequest(BaseModel):
    # Omit on the first message; send back the session_id from the previous response after.
    session_id: str | None = Field(default=None, max_length=100)
    message: MessageText


class ChatResponse(BaseModel):
    session_id: str
    reply: str | None  # None when the owner has taken over the conversation
    handed_off: bool


class ChatMessageRead(BaseModel):
    """A message as the customer saw it: no sources or other internal fields."""

    model_config = ConfigDict(from_attributes=True)

    role: MessageRole
    content: str
    created_at: datetime


class ChatHistory(BaseModel):
    session_id: str
    handed_off: bool
    messages: list[ChatMessageRead]
