from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession, RequireOwner
from app.schemas.analytics import (
    AnalyticsSummary,
    ChannelConversionRead,
    TopicRead,
    WeekdayCount,
)
from app.services import analytics

router = APIRouter(prefix="/api/analytics", tags=["analytics"], dependencies=[RequireOwner])


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


@router.get("", response_model=AnalyticsSummary)
def get_summary(db: DbSession, days: Annotated[int, Query(ge=1, le=365)] = 30) -> AnalyticsSummary:
    """Chats, conversion, busy days, common topics and open unanswered questions."""
    s = analytics.summary(db, days)
    converted = sum(c.converted for c in s.conversion)
    return AnalyticsSummary(
        days=s.days,
        start=s.start,
        end=s.end,
        conversations=s.conversations,
        handed_off=s.handed_off,
        bookings=s.bookings,
        conversion_rate=_rate(converted, s.conversations),
        conversion=[
            ChannelConversionRead(
                channel=c.channel,
                conversations=c.conversations,
                converted=c.converted,
                rate=_rate(c.converted, c.conversations),
            )
            for c in s.conversion
        ],
        busy_days=[WeekdayCount(weekday=day, bookings=count) for day, count in s.busy_days],
        top_topics=[
            TopicRead(title=t.title, heading=t.heading, count=t.count) for t in s.top_topics
        ],
        open_unanswered=s.open_unanswered,
    )
