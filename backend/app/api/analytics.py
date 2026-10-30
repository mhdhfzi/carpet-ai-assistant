from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession, RequireOrdersEnabled, RequireOwner
from app.schemas.analytics import (
    AnalyticsSummary,
    BusinessAnalytics,
    BusinessDayCount,
    ChannelConversionRead,
    MonthStatRead,
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
    db: DbSession,
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    month: Annotated[int | None, Query(ge=1, le=12)] = None,
) -> BusinessAnalytics:
    """One year (?year=2026, default this year): money received and still owed, each month
    side by side (money, orders, customers, services), and the whole year or one month in
    detail (&month=10). Owner only; where the back office is switched on."""
    s = business_analytics.summary(db, year or business_analytics.today().year, month)
    return BusinessAnalytics(
        year=s.year,
        years=s.years,
        month=s.month,
        start=s.start,
        end=s.end,
        revenue_total=s.revenue_total,
        unpaid=s.unpaid,
        unpaid_orders=s.unpaid_orders,
        customers_total=s.customers_total,
        months=[_month(m) for m in s.months],
        month_before=_month(s.month_before),
        revenue=s.revenue,
        revenue_by_method=s.revenue_by_method,
        orders=s.orders,
        order_value=s.order_value,
        new_customers=s.new_customers,
        cancelled=s.cancelled,
        services=[ServiceStatRead(name=x.name, items=x.items, value=x.value) for x in s.services],
        busy_days=[BusinessDayCount(weekday=d, orders=n) for d, n in s.busy_days],
    )


def _month(m: business_analytics.MonthStat) -> MonthStatRead:
    return MonthStatRead(
        month=f"{m.month:%Y-%m}",
        revenue=m.revenue,
        orders=m.orders,
        order_value=m.order_value,
        customers=m.customers,
        new_customers=m.new_customers,
        top_service=m.top_service,
        items_by_service=m.items_by_service,
    )
