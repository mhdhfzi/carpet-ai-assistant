from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import OrderStatus, PricingUnit, ReturnMethod
from app.schemas.booking import CustomerIn

Feet = Annotated[Decimal, Field(gt=0, max_digits=6, decimal_places=2)]
Amount = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]


class OrderItemIn(BaseModel):
    service_id: int
    # Carpets: the measured size in feet (the book's "Size Karpet"); square feet follow.
    length_ft: Feet | None = None
    width_ft: Feet | None = None
    # Sofa seats, mattresses, cars; or square feet when the size isn't known as L x W.
    quantity: Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)] | None = None
    # Owner only. Unset = the price list's price (handmade carpet: set after inspection).
    unit_price: Amount | None = None
    notes: str | None = Field(default=None, max_length=500)


class OrderCreate(BaseModel):
    customer: CustomerIn
    received_on: date | None = None  # defaults to today
    items: list[OrderItemIn] = Field(min_length=1, max_length=50)
    return_method: ReturnMethod | None = None
    deposit: Amount = Decimal("0")
    discount: Amount = Decimal("0")  # owner only
    notes: str | None = Field(default=None, max_length=1000)


class OrderUpdate(BaseModel):
    """Only the fields sent are changed."""

    status: OrderStatus | None = None
    status_note: str | None = Field(default=None, max_length=300)
    items: list[OrderItemIn] | None = Field(default=None, min_length=1, max_length=50)
    return_method: ReturnMethod | None = None
    deposit: Amount | None = None
    discount: Amount | None = None
    notes: str | None = Field(default=None, max_length=1000)


class OrderCustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    area: str | None
    address: str | None


class OrderServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    pricing_unit: PricingUnit


class OrderItemRead(BaseModel):
    id: int
    position: int
    tag: str  # written on the carpet's tag, e.g. "412-2"
    service: OrderServiceRead
    length_ft: Decimal | None
    width_ft: Decimal | None
    quantity: Decimal
    unit_price: Decimal | None  # None: the owner hasn't set it yet
    line_total: Decimal | None
    notes: str | None


class OrderEventRead(BaseModel):
    status: OrderStatus
    note: str | None
    by: str | None  # who made the change
    at: datetime


class OrderRead(BaseModel):
    id: int
    number: int
    customer: OrderCustomerRead
    received_on: date
    status: OrderStatus
    return_method: ReturnMethod | None
    deposit: Decimal
    discount: Decimal
    notes: str | None
    washed_on: date | None
    ready_on: date | None
    completed_on: date | None
    # Carpets dry in 5-7 days after washing; None until washed (or with no carpets).
    ready_from: date | None
    ready_by: date | None
    price_pending: bool  # some item has no price yet: totals are partial
    subtotal: Decimal
    total: Decimal  # subtotal - discount
    balance: Decimal  # total - deposit
    items: list[OrderItemRead]
    events: list[OrderEventRead]
    created_at: datetime


class CustomerSummary(BaseModel):
    id: int
    name: str
    phone: str
    area: str | None
    address: str | None
    orders: int
    last_order_on: date | None
    total_value: Decimal  # all their orders except cancelled ones


class CustomerDetail(CustomerSummary):
    order_history: list[OrderRead]
