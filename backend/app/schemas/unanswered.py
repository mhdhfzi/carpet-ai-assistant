from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models import UnansweredReason


class UnansweredQuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    message_id: int
    reason: UnansweredReason
    question: str
    detail: str | None
    top_score: float | None
    resolved: bool
    created_at: datetime


class UnansweredQuestionUpdate(BaseModel):
    resolved: bool
