from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.db.models import Channel, OrderStatus, PaymentMethod, UnansweredReason


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


class RevenueBucketRead(BaseModel):
    label: str
    start: date
    amount: Decimal


class ServiceStatRead(BaseModel):
    name: str
    items: int
    value: Decimal


class BusinessDayCount(BaseModel):
    weekday: str
    orders: int


class BusinessAnalytics(BaseModel):
    """Money, orders and progress from the back office (for a real business)."""

    days: int
    start: date
    end: date
    revenue: Decimal
    revenue_by_method: dict[PaymentMethod, Decimal]
    revenue_over_time: list[RevenueBucketRead]
    orders: int
    order_value: Decimal
    cancelled: int
    unpaid: Decimal
    unpaid_orders: int
    in_progress: dict[OrderStatus, int]
    services: list[ServiceStatRead]
    busy_days: list[BusinessDayCount]
    average_days_to_ready: float | None
