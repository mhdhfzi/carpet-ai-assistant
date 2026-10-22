"""Business numbers from the back office, month by month: money received, orders and the
most popular services, plus what's owed and everything received to date.

Computed in Python from the period's orders and payments: a small business has a few
thousand orders a year, so clarity beats squeezing it into one SQL query.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
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


@dataclass(frozen=True)
class ServiceStat:
    name: str
    items: int
    value: Decimal


@dataclass(frozen=True)
class MonthStat:
    month: date  # the first day of the month
    revenue: Decimal  # money received that month
    orders: int  # orders received that month, not cancelled
    top_service: str | None  # the service with the most items that month


@dataclass(frozen=True)
class BusinessSummary:
    month: date  # the month shown in detail (its first day)
    start: date
    end: date
    revenue_total: Decimal  # every payment ever received (not voided)
    unpaid: Decimal  # owed now on every order that isn't cancelled
    unpaid_orders: int
    months: list[MonthStat]  # the last 12 months, oldest first
    # The chosen month:
    revenue: Decimal
    revenue_by_method: dict[PaymentMethod, Decimal]
    orders: int  # received that month, not cancelled
    order_value: Decimal  # their total value
    cancelled: int
    services: list[ServiceStat]  # most items first
    busy_days: list[tuple[str, int]]  # orders received per weekday
    average_days_to_ready: float | None  # carpets: received -> packed


def today() -> date:
    return order_service.today()


def first_of_month(day: date) -> date:
    return day.replace(day=1)


def summary(db: Session, month: date) -> BusinessSummary:
    """Totals for the whole business, the last 12 months side by side, and one month in
    detail (`month`: any day in it)."""
    start = first_of_month(month)
    end = _next_month(start) - timedelta(days=1)

    month_orders = _orders(db, Order.received_on.between(start, end))
    kept = [o for o in month_orders if o.status is not OrderStatus.CANCELLED]
    by_method = {method: Decimal("0") for method in PaymentMethod}
    for payment in _payments(db, start, end):
        by_method[payment.method] += payment.amount

    owing = _orders(db, Order.status != OrderStatus.CANCELLED)
    balances = [order_service.totals(o).balance for o in owing]
    every_payment = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.voided_at.is_(None))
    )

    return BusinessSummary(
        month=start,
        start=start,
        end=end,
        revenue_total=Decimal(every_payment),
        unpaid=sum((b for b in balances if b > 0), Decimal("0")),
        unpaid_orders=sum(1 for b in balances if b > 0),
        months=_last_twelve_months(db),
        revenue=sum(by_method.values(), Decimal("0")),
        revenue_by_method=by_method,
        orders=len(kept),
        order_value=sum((order_service.totals(o).total for o in kept), Decimal("0")),
        cancelled=len(month_orders) - len(kept),
        services=_services(kept),
        busy_days=_busy_days(kept),
        average_days_to_ready=_days_to_ready(kept),
    )


def _last_twelve_months(db: Session) -> list[MonthStat]:
    """Money, orders and the favourite service for each of the last 12 months (this one
    included), so the owner can compare months at a glance."""
    this_month = first_of_month(order_service.today())
    firsts = [this_month]
    for _ in range(11):
        firsts.insert(0, first_of_month(firsts[0] - timedelta(days=1)))
    end = _next_month(this_month) - timedelta(days=1)

    revenue: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
    for payment in _payments(db, firsts[0], end):
        revenue[first_of_month(payment.paid_on)] += payment.amount
    received: dict[date, list[Order]] = defaultdict(list)
    for order in _orders(db, Order.received_on.between(firsts[0], end)):
        if order.status is not OrderStatus.CANCELLED:
            received[first_of_month(order.received_on)].append(order)

    stats = []
    for first in firsts:
        popular = _services(received[first])
        stats.append(
            MonthStat(
                first, revenue[first], len(received[first]), popular[0].name if popular else None
            )
        )
    return stats


def _next_month(first: date) -> date:
    return (first + timedelta(days=32)).replace(day=1)


def _payments(db: Session, start: date, end: date) -> list[Payment]:
    return list(
        db.scalars(
            select(Payment).where(Payment.voided_at.is_(None), Payment.paid_on.between(start, end))
        )
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


def _services(orders: list[Order]) -> list[ServiceStat]:
    counts: Counter[str] = Counter()
    values: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for order in orders:
        for item in order.items:
            # A sofa line of 3 seats counts as 3; a carpet counts as 1 whatever its size.
            many = item.service.pricing_unit is not PricingUnit.PER_SQFT
            counts[item.service.name] += int(item.quantity or 0) if many else 1
            values[item.service.name] += order_service.line_total(item) or Decimal("0")
    return [ServiceStat(name, n, values[name]) for name, n in counts.most_common()]


def _busy_days(orders: list[Order]) -> list[tuple[str, int]]:
    per_day = Counter(WEEKDAYS[o.received_on.weekday()] for o in orders)
    return [(day, per_day.get(day, 0)) for day in WEEKDAYS]


def _days_to_ready(orders: list[Order]) -> float | None:
    """Average days from received to packed, over carpets that are packed."""
    waits = [
        (item.ready_on - order.received_on).days
        for order in orders
        for item in order.items
        if item.service.pricing_unit is PricingUnit.PER_SQFT
        and item.status is ItemStatus.READY
        and item.ready_on is not None
    ]
    return round(sum(waits) / len(waits), 1) if waits else None
