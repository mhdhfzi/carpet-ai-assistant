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


class PeriodStatRead(BaseModel):
    start: date
    end: date
    revenue: Decimal
    orders: int
    average_days_to_ready: float | None


class BusinessAnalytics(BaseModel):
    """Money and orders from the back office (for a real business), for one year: its
    totals, its months side by side, and the whole year or one month in detail."""

    year: int
    years: list[int]  # the years that can be picked, newest first
    month: int | None  # the month in detail (1-12), or None for the whole year
    start: date  # the detail period
    end: date
    revenue_total: Decimal  # received in the year
    unpaid: Decimal  # owed now on the year's orders
    unpaid_orders: int
    months: list[MonthStatRead]  # January onwards (up to this month for this year)
    last_year_months: list[MonthStatRead]  # all 12 months of the year before
    revenue: Decimal  # the detail period's
    revenue_by_method: dict[PaymentMethod, Decimal]
    orders: int
    order_value: Decimal
    cancelled: int
    services: list[ServiceStatRead]
    busy_days: list[BusinessDayCount]
    average_days_to_ready: float | None
    previous: PeriodStatRead  # the month (or year) before, to show the change
