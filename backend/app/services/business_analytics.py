"""Business numbers from the back office for one year: money received and owed, each
month side by side (money, orders, most popular service) next to last year's, and the whole
year or one of its months in detail, compared with the period before it.

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
    items_by_service: dict[str, int]  # each service's items that month
    revenue_by_method: dict[PaymentMethod, Decimal]  # that month's money, by how it was paid


@dataclass(frozen=True)
class PeriodStat:
    """The headline numbers of the period before, to show how the detail period changed."""

    start: date
    end: date
    revenue: Decimal
    orders: int
    average_days_to_ready: float | None
    revenue_by_method: dict[PaymentMethod, Decimal]
    items_by_service: dict[str, int]
    busy_days: list[tuple[str, int]]


@dataclass(frozen=True)
class BusinessSummary:
    year: int
    years: list[int]  # years that can be picked: this one back to the first with data
    month: int | None  # the month shown in detail (1-12), or None for the whole year
    start: date  # the detail period
    end: date
    revenue_total: Decimal  # every payment received in the year (not voided)
    unpaid: Decimal  # owed now on the year's orders that aren't cancelled
    unpaid_orders: int
    months: list[MonthStat]  # January onwards: all 12, or up to this month for this year
    last_year_months: list[MonthStat]  # all 12 months of the year before, to compare
    # The detail period (the whole year, or the chosen month):
    revenue: Decimal
    revenue_by_method: dict[PaymentMethod, Decimal]
    orders: int  # received that month, not cancelled
    order_value: Decimal  # their total value
    cancelled: int
    services: list[ServiceStat]  # most items first
    busy_days: list[tuple[str, int]]  # orders received per weekday
    average_days_to_ready: float | None  # carpets: received -> packed
    previous: PeriodStat  # the month before the chosen month, or the year before the year


def today() -> date:
    return order_service.today()


def first_of_month(day: date) -> date:
    return day.replace(day=1)


def summary(db: Session, year: int, month: int | None = None) -> BusinessSummary:
    """One year: its totals, its months side by side, and the whole year (month=None) or
    one of its months in detail."""
    year_start, year_end = date(year, 1, 1), date(year, 12, 31)
    if month is None:
        start, end = year_start, year_end
    else:
        start = date(year, month, 1)
        end = _next_month(start) - timedelta(days=1)

    period_orders = _orders(db, Order.received_on.between(start, end))
    kept = _kept(period_orders)
    by_method = _by_method(db, start, end)

    # What's still owed on the orders received this year.
    owing = _orders(
        db,
        Order.received_on.between(year_start, year_end) & (Order.status != OrderStatus.CANCELLED),
    )
    balances = [order_service.totals(o).balance for o in owing]
    received = sum((p.amount for p in _payments(db, year_start, year_end)), Decimal("0"))

    return BusinessSummary(
        year=year,
        years=_years(db),
        month=month,
        start=start,
        end=end,
        revenue_total=received,
        unpaid=sum((b for b in balances if b > 0), Decimal("0")),
        unpaid_orders=sum(1 for b in balances if b > 0),
        months=_months_of(db, year),
        revenue=sum(by_method.values(), Decimal("0")),
        revenue_by_method=by_method,
        orders=len(kept),
        order_value=sum((order_service.totals(o).total for o in kept), Decimal("0")),
        cancelled=len(period_orders) - len(kept),
        services=_services(kept),
        busy_days=_busy_days(kept),
        average_days_to_ready=_days_to_ready(kept),
        last_year_months=_months_of(db, year - 1),
        previous=_previous(db, start, month is None),
    )


def _previous(db: Session, start: date, whole_year: bool) -> PeriodStat:
    """The period just before: the month before (September for October, December last year
    for January), or the whole year before."""
    if whole_year:
        before_start, before_end = date(start.year - 1, 1, 1), date(start.year - 1, 12, 31)
    else:
        before_end = start - timedelta(days=1)
        before_start = first_of_month(before_end)
    kept = _kept(_orders(db, Order.received_on.between(before_start, before_end)))
    by_method = _by_method(db, before_start, before_end)
    return PeriodStat(
        start=before_start,
        end=before_end,
        revenue=sum(by_method.values(), Decimal("0")),
        orders=len(kept),
        average_days_to_ready=_days_to_ready(kept),
        revenue_by_method=by_method,
        items_by_service={s.name: s.items for s in _services(kept)},
        busy_days=_busy_days(kept),
    )


def _kept(orders: list[Order]) -> list[Order]:
    return [o for o in orders if o.status is not OrderStatus.CANCELLED]


def _by_method(db: Session, start: date, end: date) -> dict[PaymentMethod, Decimal]:
    by_method = {method: Decimal("0") for method in PaymentMethod}
    for payment in _payments(db, start, end):
        by_method[payment.method] += payment.amount
    return by_method


def _years(db: Session) -> list[int]:
    """This year back to the first year with an order or a payment, newest first."""
    this_year = order_service.today().year
    firsts = [
        day.year
        for day in (
            db.scalar(select(func.min(Order.received_on))),
            db.scalar(select(func.min(Payment.paid_on))),
        )
        if day is not None
    ]
    first = min([*firsts, this_year])
    return list(range(this_year, first - 1, -1))


def _months_of(db: Session, year: int) -> list[MonthStat]:
    """Money, orders and the favourite service for each month of the year, so the owner
    can compare months at a glance. This year stops at this month (no empty future months)."""
    today = order_service.today()
    last = 12 if year < today.year else today.month if year == today.year else 0
    if not last:
        return []
    firsts = [date(year, m, 1) for m in range(1, last + 1)]
    end = _next_month(firsts[-1]) - timedelta(days=1)

    by_method: dict[date, dict[PaymentMethod, Decimal]] = {
        first: {method: Decimal("0") for method in PaymentMethod} for first in firsts
    }
    for payment in _payments(db, firsts[0], end):
        by_method[first_of_month(payment.paid_on)][payment.method] += payment.amount
    received: dict[date, list[Order]] = defaultdict(list)
    for order in _orders(db, Order.received_on.between(firsts[0], end)):
        if order.status is not OrderStatus.CANCELLED:
            received[first_of_month(order.received_on)].append(order)

    stats = []
    for first in firsts:
        popular = _services(received[first])
        stats.append(
            MonthStat(
                month=first,
                revenue=sum(by_method[first].values(), Decimal("0")),
                orders=len(received[first]),
                top_service=popular[0].name if popular else None,
                items_by_service={s.name: s.items for s in popular},
                revenue_by_method=by_method[first],
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
        for item in order_service.live_items(order):
            # A sofa line of 3 seats counts as 3; a carpet counts as 1 whatever its size.
            many = item.service.pricing_unit is not PricingUnit.PER_SQFT
            counts[item.service.name] += int(item.quantity or 0) if many else 1
            values[item.service.name] += order_service.line_total(item) or Decimal("0")
    # Most items first; a tie goes to the one worth more, then by name, so it never depends
    # on the order the database returns rows in.
    ranked = sorted(counts, key=lambda name: (-counts[name], -values[name], name))
    return [ServiceStat(name, counts[name], values[name]) for name in ranked]


def _busy_days(orders: list[Order]) -> list[tuple[str, int]]:
    per_day = Counter(WEEKDAYS[o.received_on.weekday()] for o in orders)
    return [(day, per_day.get(day, 0)) for day in WEEKDAYS]


def _days_to_ready(orders: list[Order]) -> float | None:
    """Average days from received to packed, over carpets that are packed."""
    waits = [
        (item.ready_on - order.received_on).days
        for order in orders
        for item in order_service.live_items(order)
        if not item.service.on_site
        and item.status is ItemStatus.READY
        and item.ready_on is not None
    ]
    return round(sum(waits) / len(waits), 1) if waits else None
