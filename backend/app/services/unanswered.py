"""The unanswered-questions log: questions the assistant couldn't handle, kept as a to-do
list for the owner (add the missing information, then mark the entry resolved)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Conversation, Message, UnansweredQuestion, UnansweredReason
from app.services.errors import NotFoundError


def log_question(
    db: Session,
    conversation: Conversation,
    message_id: int,
    reason: UnansweredReason,
    *,
    question: str | None = None,
    detail: str | None = None,
    top_score: float | None = None,
) -> UnansweredQuestion:
    """Record a question once per message and reason (a turn may flag and also hand off).

    `question` defaults to the customer's own message. Doesn't commit: it's saved with the
    rest of the caller's transaction.
    """
    existing = db.scalar(
        select(UnansweredQuestion).where(
            UnansweredQuestion.message_id == message_id, UnansweredQuestion.reason == reason
        )
    )
    if existing is not None:
        return existing
    if question is None:
        message = db.get(Message, message_id)
        question = message.content if message is not None else ""
    entry = UnansweredQuestion(
        conversation=conversation,
        message_id=message_id,
        reason=reason,
        question=question,
        detail=detail,
        top_score=top_score,
    )
    db.add(entry)
    return entry


def list_questions(
    db: Session, *, resolved: bool | None = False, limit: int = 50, offset: int = 0
) -> list[UnansweredQuestion]:
    stmt = select(UnansweredQuestion).order_by(
        UnansweredQuestion.created_at.desc(), UnansweredQuestion.id.desc()
    )
    if resolved is not None:
        stmt = stmt.where(UnansweredQuestion.resolved == resolved)
    return list(db.scalars(stmt.limit(limit).offset(offset)))


def set_resolved(db: Session, question_id: int, resolved: bool) -> UnansweredQuestion:
    entry = db.get(UnansweredQuestion, question_id)
    if entry is None:
        raise NotFoundError(f"Unanswered question {question_id} not found")
    entry.resolved = resolved
    db.commit()
    return entry
