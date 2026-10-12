"""Numbers for the owner's analytics page."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import (
    Booking,
    BookingStatus,
    Channel,
    Conversation,
    Message,
    MessageRole,
    UnansweredQuestion,
    UnansweredReason,
)
from app.services.availability import HOURS

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
TOP_TOPICS = 8


@dataclass(frozen=True)
class ChannelConversion:
    channel: Channel
    conversations: int
    converted: int  # conversations that led to at least one booking


@dataclass(frozen=True)
class Topic:
    title: str
    heading: str
    count: int


@dataclass(frozen=True)
class Summary:
    days: int
    start: datetime
    end: datetime
    conversations: int
    handed_off: int
    bookings: int  # bookings made in the period (any channel, including direct ones)
    conversion: list[ChannelConversion]
    busy_days: list[tuple[str, int]]  # (weekday, bookings), Monday first
    top_topics: list[Topic]
    open_unanswered: dict[UnansweredReason, int]


def summary(db: Session, days: int = 30) -> Summary:
    """Activity in the last `days` days, counted from midnight Malaysia time."""
    now = clock.now()
    today = now.astimezone(HOURS.timezone).date()
    start = datetime.combine(today - timedelta(days=days - 1), time.min, HOURS.timezone)

    return Summary(
        days=days,
        start=start,
        end=now,
        conversations=_count(db, select(func.count(Conversation.id)), Conversation, start),
        handed_off=_count(
            db,
            select(func.count(Conversation.id)).where(Conversation.handed_off),
            Conversation,
            start,
        ),
        bookings=_count(db, select(func.count(Booking.id)), Booking, start),
        conversion=_conversion(db, start),
        busy_days=_busy_days(db, start),
        top_topics=_top_topics(db, start),
        open_unanswered=_open_unanswered(db),
    )


def _count(db: Session, stmt, model, start: datetime) -> int:
    return db.scalar(stmt.where(model.created_at >= start)) or 0


def _conversion(db: Session, start: datetime) -> list[ChannelConversion]:
    totals = dict(
        db.execute(
            select(Conversation.channel, func.count(Conversation.id))
            .where(Conversation.created_at >= start)
            .group_by(Conversation.channel)
        ).all()
    )
    converted = dict(
        db.execute(
            select(Conversation.channel, func.count(distinct(Conversation.id)))
            .join(Booking, Booking.conversation_id == Conversation.id)
            .where(Conversation.created_at >= start)
            .group_by(Conversation.channel)
        ).all()
    )
    return [
        ChannelConversion(channel, totals.get(channel, 0), converted.get(channel, 0))
        for channel in Channel
    ]


def _busy_days(db: Session, start: datetime) -> list[tuple[str, int]]:
    """Bookings made in the period, by the weekday of the visit (in Malaysia time).
    Cancelled bookings don't keep the team busy, so they're left out."""
    local_start = func.timezone(HOURS.timezone.key, Booking.scheduled_start)
    weekday = func.extract("isodow", local_start)  # 1 = Monday ... 7 = Sunday
    rows = db.execute(
        select(weekday, func.count(Booking.id))
        .where(Booking.created_at >= start, Booking.status != BookingStatus.CANCELLED)
        .group_by(weekday)
    ).all()
    counts = {int(day): count for day, count in rows}
    return [(name, counts.get(index, 0)) for index, name in enumerate(WEEKDAYS, start=1)]


def _top_topics(db: Session, start: datetime) -> list[Topic]:
    """Knowledge sections the assistant cited most: what customers ask about.

    Counted in Python: one row per cited reply is small at this business's scale. A
    jsonb_array_elements aggregate in SQL would be the next step if it grew.
    """
    counter: Counter[tuple[str, str]] = Counter()
    for sources in db.scalars(
        select(Message.sources).where(
            Message.role == MessageRole.ASSISTANT,
            Message.created_at >= start,
            Message.sources.is_not(None),
        )
    ):
        counter.update({(s["title"], s["heading"]) for s in sources or []})
    return [
        Topic(title, heading, count)
        for (title, heading), count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ][:TOP_TOPICS]


def _open_unanswered(db: Session) -> dict[UnansweredReason, int]:
    rows = dict(
        db.execute(
            select(UnansweredQuestion.reason, func.count(UnansweredQuestion.id))
            .where(UnansweredQuestion.resolved.is_(False))
            .group_by(UnansweredQuestion.reason)
        ).all()
    )
    return {reason: rows.get(reason, 0) for reason in UnansweredReason}
