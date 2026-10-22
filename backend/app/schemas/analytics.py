from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.db.models import Channel, PaymentMethod, UnansweredReason


class ChannelConversionRead(BaseModel):
    channel: Channel
    conversations: int
    converted: int
    rate: float | None  # converted / conversations; None when there were no conversations


class WeekdayCount(BaseModel):
    weekday: str
    bookings: int


class TopicRead(BaseModel):
    title: str
    heading: str
    count: int


class AnalyticsSummary(BaseModel):
    days: int
    start: datetime
    end: datetime
    conversations: int
    handed_off: int
    bookings: int
    conversion_rate: float | None
    conversion: list[ChannelConversionRead]
    busy_days: list[WeekdayCount]
    top_topics: list[TopicRead]
    open_unanswered: dict[UnansweredReason, int]


class ServiceStatRead(BaseModel):
    name: str
    items: int
    value: Decimal


class BusinessDayCount(BaseModel):
    weekday: str
    orders: int


class MonthStatRead(BaseModel):
    month: str  # "2026-10"
    revenue: Decimal
    orders: int
    top_service: str | None


class BusinessAnalytics(BaseModel):
    """Money and orders from the back office (for a real business): totals to date, the last
    12 months side by side, and one month in detail."""

    month: str  # the month in detail, "2026-10"
    start: date
    end: date
    revenue_total: Decimal  # everything ever received
    unpaid: Decimal  # owed now, on every order
    unpaid_orders: int
    months: list[MonthStatRead]  # the last 12 months, oldest first
    revenue: Decimal  # the chosen month's
    revenue_by_method: dict[PaymentMethod, Decimal]
    orders: int
    order_value: Decimal
    cancelled: int
    services: list[ServiceStatRead]
    busy_days: list[BusinessDayCount]
    average_days_to_ready: float | None
