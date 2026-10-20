from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import (
    ItemFold,
    ItemStatus,
    OrderStatus,
    PaymentMethod,
    PricingUnit,
    ReturnMethod,
)
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
    # The book's "Depo": recorded as the order's first payment.
    deposit: Amount = Decimal("0")
    deposit_method: PaymentMethod = PaymentMethod.CASH
    discount: Amount = Decimal("0")  # owner only
    notes: str | None = Field(default=None, max_length=1000)


class PaymentIn(BaseModel):
    amount: Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]
    method: PaymentMethod
    paid_on: date | None = None  # defaults to today
    note: str | None = Field(default=None, max_length=200)


class ItemStatusUpdate(BaseModel):
    status: ItemStatus
    # Kept on the timeline; when washing, also the carpet's wash note ("catatan").
    note: str | None = Field(default=None, max_length=300)
    # Packing a velvet carpet: rolled (gulung) or folded (lipat). Ignored for other items.
    fold: ItemFold | None = None
    # A carpet measured while it's washed: both, in feet.
    length_ft: Feet | None = None
    width_ft: Feet | None = None


class PaymentVoid(BaseModel):
    reason: str = Field(min_length=3, max_length=200)


class PaymentRead(BaseModel):
    id: int
    amount: Decimal
    method: PaymentMethod
    paid_on: date
    note: str | None
    received_by: str | None
    voided: bool
    void_reason: str | None


class OrderUpdate(BaseModel):
    """Only the fields sent are changed."""

    status: OrderStatus | None = None
    status_note: str | None = Field(default=None, max_length=300)
    items: list[OrderItemIn] | None = Field(default=None, min_length=1, max_length=50)
    return_method: ReturnMethod | None = None
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
    needs_fold: bool  # velvet: packed rolled or folded


class OrderItemRead(BaseModel):
    id: int
    position: int
    tag: str  # written on the carpet's tag, e.g. "412-2"
    service: OrderServiceRead
    length_ft: Decimal | None
    width_ft: Decimal | None
    quantity: Decimal | None  # None: a carpet not measured yet
    unit_price: Decimal | None  # None: the owner hasn't set it yet
    line_total: Decimal | None
    notes: str | None
    status: ItemStatus
    washed_on: date | None
    washed_by: str | None
    wash_note: str | None
    ready_on: date | None  # the day it was packed
    packed_by: str | None
    fold: ItemFold | None
    # A washed carpet can be packed 5-7 days later, once dry; None once packed (or for items
    # that aren't carpets).
    ready_from: date | None
    ready_by: date | None


class WorkItemRead(OrderItemRead):
    """An item on the washing or packing list, with the order it belongs to."""

    order_id: int
    order_number: int
    customer_name: str
    received_on: date


class WorkLogRead(BaseModel):
    """One day's washing and packing forms."""

    day: date
    washed: list[WorkItemRead]
    packed: list[WorkItemRead]


class OrderEventRead(BaseModel):
    status: OrderStatus
    item_tag: str | None  # the item that moved, or None for the whole order
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
    discount: Decimal
    notes: str | None
    washed_on: date | None
    ready_on: date | None
    completed_on: date | None
    # Carpets dry in 5-7 days after washing; None until washed (or with no carpets).
    ready_from: date | None
    ready_by: date | None
    items_washed: int  # items washed or packed: "2 / 3 dicuci"
    items_ready: int  # items packed: "2 / 3 siap"
    price_pending: bool  # some item has no price yet: totals are partial
    subtotal: Decimal
    total: Decimal  # subtotal - discount
    paid: Decimal  # payments, not counting voided ones
    balance: Decimal  # total - paid
    items: list[OrderItemRead]
    payments: list[PaymentRead]
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
    unpaid: Decimal  # what they still owe on those orders


class CustomerDetail(CustomerSummary):
    order_history: list[OrderRead]


class WorkSummaryRead(BaseModel):
    to_wash: int
    to_pack: int
    drying: int
    ready_orders: int
    unpaid: Decimal
    unpaid_orders: int


class UntaggedIn(BaseModel):
    description: str = Field(min_length=2, max_length=200)  # e.g. "Biasa 7.7 x 5.3, biru"


class UntaggedMatch(BaseModel):
    tag: str = Field(min_length=3, max_length=20)  # e.g. "412-2"


class UntaggedRead(BaseModel):
    id: int
    description: str
    found_on: date
    found_by: str | None
    matched_tag: str | None


class ReceiptBusiness(BaseModel):
    name: str  # as printed on the receipt
    logo: str  # the short mark in the round badge
    reg_no: str
    address: str
    phone: str
    email: str
    facebook: str
    payment_details: str  # one item per line
    terms: str


class ReceiptRead(BaseModel):
    """Everything a printed receipt shows. Its number is the order number."""

    business: ReceiptBusiness
    order: OrderRead
    issued_on: date
