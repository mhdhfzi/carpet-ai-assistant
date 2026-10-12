"""The owner's to-do list of questions the assistant couldn't answer."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.db.models import UnansweredQuestion
from app.schemas.unanswered import UnansweredQuestionRead, UnansweredQuestionUpdate
from app.services import unanswered

router = APIRouter(prefix="/api/unanswered-questions", tags=["unanswered questions"])


@router.get("", response_model=list[UnansweredQuestionRead])
def list_unanswered_questions(
    db: DbSession,
    resolved: bool | None = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[UnansweredQuestion]:
    """Newest first. Defaults to open (unresolved) questions; omit with resolved= for all."""
    return unanswered.list_questions(db, resolved=resolved, limit=limit, offset=offset)


@router.patch("/{question_id}", response_model=UnansweredQuestionRead)
def update_unanswered_question(
    question_id: int, data: UnansweredQuestionUpdate, db: DbSession
) -> UnansweredQuestion:
    """Mark resolved once the knowledge base or price list covers the question."""
    return unanswered.set_resolved(db, question_id, data.resolved)
