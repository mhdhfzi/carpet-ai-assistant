"""Days the business is closed on top of Fridays (public holidays, leave)."""

from datetime import date

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.deps import DbSession
from app.db.models import ClosedDate
from app.schemas.closed_date import ClosedDateIn, ClosedDateRead

router = APIRouter(prefix="/api/closed-dates", tags=["availability"])


@router.get("", response_model=list[ClosedDateRead])
def list_closed_dates(db: DbSession, date_from: date | None = None) -> list[ClosedDate]:
    stmt = select(ClosedDate).order_by(ClosedDate.day)
    if date_from is not None:
        stmt = stmt.where(ClosedDate.day >= date_from)
    return list(db.scalars(stmt))


@router.put("/{day}", response_model=ClosedDateRead)
def set_closed_date(day: date, data: ClosedDateIn, db: DbSession) -> ClosedDate:
    """Idempotent: closing a day twice just updates the reason."""
    closed = db.get(ClosedDate, day) or ClosedDate(day=day)
    closed.reason = data.reason
    db.add(closed)
    db.commit()
    return closed


@router.delete("/{day}", status_code=status.HTTP_204_NO_CONTENT)
def reopen_date(day: date, db: DbSession) -> None:
    closed = db.get(ClosedDate, day)
    if closed is not None:
        db.delete(closed)
        db.commit()
