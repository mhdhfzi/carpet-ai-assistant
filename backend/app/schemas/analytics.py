from datetime import datetime

from pydantic import BaseModel

from app.db.models import Channel, UnansweredReason


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
