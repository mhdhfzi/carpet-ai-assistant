from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

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
