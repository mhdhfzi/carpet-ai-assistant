"""Business numbers from the back office: money received, orders, what's owed, what's in
progress, popular services, busy days and how long carpets take.

Computed in Python from the period's orders and payments: a small business has a few
thousand orders a year, so clarity beats squeezing it into one SQL query.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    ItemStatus,
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    PaymentMethod,
    PricingUnit,
)
from app.services import orders as order_service

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
OPEN = (OrderStatus.RECEIVED, OrderStatus.WASHED, OrderStatus.READY)


@dataclass(frozen=True)
class RevenueBucket:
    label: str  # "Mon 12" for a day, "12 Oct" for the week starting then
    start: date
    amount: Decimal


@dataclass(frozen=True)
class ServiceStat:
    name: str
    items: int
    value: Decimal


@dataclass(frozen=True)
class BusinessSummary:
    start: date
    end: date
    revenue: Decimal  # money received (payments, not voided) in the period
    revenue_by_method: dict[PaymentMethod, Decimal]
    revenue_over_time: list[RevenueBucket]
    orders: int  # received in the period, not cancelled
    order_value: Decimal  # their total value
    cancelled: int
    unpaid: Decimal  # owed now on every order that isn't cancelled
    unpaid_orders: int
    in_progress: dict[OrderStatus, int]  # open orders now, by step
    services: list[ServiceStat]  # most items first
    busy_days: list[tuple[str, int]]  # orders received per weekday
    average_days_to_ready: float | None  # carpets: received -> dry


def summary(db: Session, days: int) -> BusinessSummary:
    end = order_service.today()
    start = end - timedelta(days=days - 1)

    period_orders = _orders(db, Order.received_on.between(start, end))
    kept = [o for o in period_orders if o.status is not OrderStatus.CANCELLED]
    payments = db.scalars(
        select(Payment).where(Payment.voided_at.is_(None), Payment.paid_on.between(start, end))
    ).all()

    by_method = {method: Decimal("0") for method in PaymentMethod}
    for payment in payments:
        by_method[payment.method] += payment.amount

    owing = _orders(db, Order.status != OrderStatus.CANCELLED)
    balances = [order_service.totals(o).balance for o in owing]
    open_now = Counter(o.status for o in owing if o.status in OPEN)

    return BusinessSummary(
        start=start,
        end=end,
        revenue=sum(by_method.values(), Decimal("0")),
        revenue_by_method=by_method,
        revenue_over_time=_buckets(payments, start, end, days),
        orders=len(kept),
        order_value=sum((order_service.totals(o).total for o in kept), Decimal("0")),
        cancelled=len(period_orders) - len(kept),
        unpaid=sum((b for b in balances if b > 0), Decimal("0")),
        unpaid_orders=sum(1 for b in balances if b > 0),
        in_progress={status: open_now.get(status, 0) for status in OPEN},
        services=_services(kept),
        busy_days=_busy_days(kept),
        average_days_to_ready=_days_to_ready(kept),
    )


def _orders(db: Session, condition) -> list[Order]:
    return list(
        db.scalars(
            select(Order)
            .where(condition)
            .options(
                selectinload(Order.items).selectinload(OrderItem.service),
                selectinload(Order.payments),
            )
        )
    )


def _buckets(payments, start: date, end: date, days: int) -> list[RevenueBucket]:
    """Daily for a week; weekly (Monday to Sunday) for longer periods, so a chart stays readable."""
    daily = days <= 7
    first = start if daily else start - timedelta(days=start.weekday())
    step = timedelta(days=1 if daily else 7)
    totals: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
    for payment in payments:
        key = (
            payment.paid_on
            if daily
            else payment.paid_on - timedelta(days=payment.paid_on.weekday())
        )
        totals[key] += payment.amount
    buckets, cursor = [], first
    while cursor <= end:
        label = (
            f"{WEEKDAYS[cursor.weekday()]} {cursor.day}" if daily else f"{cursor.day} {cursor:%b}"
        )
        buckets.append(RevenueBucket(label, cursor, totals[cursor]))
        cursor += step
    return buckets


def _services(orders: list[Order]) -> list[ServiceStat]:
    counts: Counter[str] = Counter()
    values: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for order in orders:
        for item in order.items:
            # A sofa line of 3 seats counts as 3; a carpet counts as 1 whatever its size.
            many = item.service.pricing_unit is not PricingUnit.PER_SQFT
            counts[item.service.name] += int(item.quantity) if many else 1
            values[item.service.name] += order_service.line_total(item) or Decimal("0")
    return [ServiceStat(name, n, values[name]) for name, n in counts.most_common()]


def _busy_days(orders: list[Order]) -> list[tuple[str, int]]:
    per_day = Counter(WEEKDAYS[o.received_on.weekday()] for o in orders)
    return [(day, per_day.get(day, 0)) for day in WEEKDAYS]


def _days_to_ready(orders: list[Order]) -> float | None:
    """Average days from received to dry, over carpets that are dry."""
    waits = [
        (item.ready_on - order.received_on).days
        for order in orders
        for item in order.items
        if item.service.pricing_unit is PricingUnit.PER_SQFT
        and item.status is ItemStatus.READY
        and item.ready_on is not None
    ]
    return round(sum(waits) / len(waits), 1) if waits else None
