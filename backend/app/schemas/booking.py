import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.db.models import BookingLocation, BookingStatus

_E164 = re.compile(r"^\+[1-9]\d{7,14}$")


def normalize_phone(raw: str) -> str:
    """Normalise a phone number to E.164, assuming Malaysia (+60) for local numbers.

    "012-345 6789" -> "+60123456789", "60123456789" -> "+60123456789".
    """
    phone = re.sub(r"[\s\-()]", "", raw)
    if phone.startswith("0"):
        phone = "+6" + phone
    elif not phone.startswith("+"):
        phone = "+" + phone
    if not _E164.match(phone):
        raise ValueError("Invalid phone number")
    return phone


class CustomerIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str
    area: str | None = Field(default=None, max_length=100)
    address: str | None = None

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, value: str) -> str:
        return normalize_phone(value)


class BookingItemIn(BaseModel):
    service_id: int
    # Square feet or number of items, depending on the service's pricing unit.
    quantity: Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]


class BookingCreate(BaseModel):
    customer: CustomerIn
    # AwareDatetime rejects times without a timezone, which would be ambiguous.
    # The end time is derived from the services' visit durations.
    scheduled_start: AwareDatetime
    location: BookingLocation = BookingLocation.CUSTOMER_HOME
    items: list[BookingItemIn] = Field(min_length=1)
    notes: str | None = None

    @field_validator("items")
    @classmethod
    def _unique_services(cls, items: list[BookingItemIn]) -> list[BookingItemIn]:
        ids = [item.service_id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("Each service may appear only once per booking")
        return items


class BookingUpdate(BaseModel):
    status: BookingStatus | None = None
    notes: str | None = None


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    area: str | None
    address: str | None


class ServiceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class BookingItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service: ServiceSummary
    quantity: Decimal
    unit_price: Decimal
    unit_price_max: Decimal
    line_total: Decimal
    line_total_max: Decimal


class BookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer: CustomerRead
    conversation_id: int | None  # the chat that led to the booking, if any
    scheduled_start: datetime
    scheduled_end: datetime
    location: BookingLocation
    status: BookingStatus
    estimated_price: Decimal
    estimated_price_max: Decimal  # equals estimated_price unless an item is priced on inspection
    notes: str | None
    items: list[BookingItemRead]
    created_at: datetime
    updated_at: datetime


class DayAvailability(BaseModel):
    day: date
    slots: list[datetime]  # possible visit start times
