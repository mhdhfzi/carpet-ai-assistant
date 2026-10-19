from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession, RequireOrdersEnabled, RequireOwner
from app.schemas.analytics import (
    AnalyticsSummary,
    BusinessAnalytics,
    BusinessDayCount,
    ChannelConversionRead,
    RevenueBucketRead,
    ServiceStatRead,
    TopicRead,
    WeekdayCount,
)
from app.services import analytics, business_analytics

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


@router.get("/business", response_model=BusinessAnalytics, dependencies=[RequireOrdersEnabled])
def get_business(
    db: DbSession, days: Annotated[int, Query(ge=1, le=365)] = 30
) -> BusinessAnalytics:
    """Money received, orders, unpaid balances, work in progress, popular services, busy
    days and how long carpets take (owner only; where the back office is switched on)."""
    s = business_analytics.summary(db, days)
    return BusinessAnalytics(
        days=days,
        start=s.start,
        end=s.end,
        revenue=s.revenue,
        revenue_by_method=s.revenue_by_method,
        revenue_over_time=[
            RevenueBucketRead(label=b.label, start=b.start, amount=b.amount)
            for b in s.revenue_over_time
        ],
        orders=s.orders,
        order_value=s.order_value,
        cancelled=s.cancelled,
        unpaid=s.unpaid,
        unpaid_orders=s.unpaid_orders,
        in_progress=s.in_progress,
        services=[ServiceStatRead(name=x.name, items=x.items, value=x.value) for x in s.services],
        busy_days=[BusinessDayCount(weekday=d, orders=n) for d, n in s.busy_days],
        average_days_to_ready=s.average_days_to_ready,
    )
