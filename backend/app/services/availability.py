"""When can the team visit a customer?

The owner agrees the final time with each customer, so this module only checks that a
requested time is plausible and suggests free times; bookings stay pending until confirmed.

The rules (`slot_problem`, `free_slots`) are pure functions, unit-tested without a database.
The functions at the bottom load the data they need (existing bookings, closed dates).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import Booking, BookingLocation, BookingStatus, ClosedDate, Service
from app.services.errors import BusinessRuleError

Period = tuple[datetime, datetime]

# Bookings that occupy the team. Cancelled and finished jobs free their slot.
BLOCKING_STATUSES = (BookingStatus.PENDING, BookingStatus.CONFIRMED)


@dataclass(frozen=True)
class BusinessHours:
    timezone: ZoneInfo = ZoneInfo("Asia/Kuala_Lumpur")
    opens: time = time(9, 0)
    closes: time = time(17, 30)
    closed_weekdays: frozenset[int] = frozenset({4})  # Friday (Monday is 0)
    # Customers must book at least this many calendar days ahead, so the owner can plan.
    min_notice_days: int = 2
    slot_step: timedelta = timedelta(minutes=30)


HOURS = BusinessHours()


class SlotUnavailableError(BusinessRuleError):
    pass


def visit_duration(services: Iterable[Service]) -> timedelta:
    """One visit handles every item, so the longest job sets the duration."""
    return timedelta(minutes=max(s.visit_minutes for s in services))


def earliest_bookable_date(now: datetime, hours: BusinessHours = HOURS) -> date:
    return now.astimezone(hours.timezone).date() + timedelta(days=hours.min_notice_days)


def is_open_day(day: date, closed_dates: set[date], hours: BusinessHours = HOURS) -> bool:
    return day.weekday() not in hours.closed_weekdays and day not in closed_dates


def slot_problem(
    start: datetime,
    duration: timedelta,
    *,
    busy: Iterable[Period],
    closed_dates: set[date],
    now: datetime,
    hours: BusinessHours = HOURS,
) -> str | None:
    """Why a visit can't start at `start`, as a customer-friendly sentence; None if it can."""
    local_start = start.astimezone(hours.timezone)
    local_end = local_start + duration
    day = local_start.date()

    earliest = earliest_bookable_date(now, hours)
    if day < earliest:
        return (
            f"Bookings need at least {hours.min_notice_days} days' notice; "
            f"the earliest date is {earliest:%A, %d %B %Y}."
        )
    if day.weekday() in hours.closed_weekdays:
        return f"We are closed on {day:%A}s."
    if day in closed_dates:
        return f"We are closed on {day:%d %B %Y}."

    opens = datetime.combine(day, hours.opens, tzinfo=hours.timezone)
    closes = datetime.combine(day, hours.closes, tzinfo=hours.timezone)
    if local_start < opens or local_end > closes:
        return (
            f"The visit must start and finish within opening hours "
            f"({hours.opens:%H:%M}-{hours.closes:%H:%M})."
        )
    if any(local_start < busy_end and busy_start < local_end for busy_start, busy_end in busy):
        return "That time clashes with another booking."
    return None


def free_slots(
    day: date,
    duration: timedelta,
    *,
    busy: Iterable[Period],
    closed_dates: set[date],
    now: datetime,
    hours: BusinessHours = HOURS,
) -> list[datetime]:
    """Start times on `day`, every `slot_step`, at which a visit of `duration` is possible."""
    busy = list(busy)
    start = datetime.combine(day, hours.opens, tzinfo=hours.timezone)
    closes = datetime.combine(day, hours.closes, tzinfo=hours.timezone)
    slots = []
    while start + duration <= closes:
        problem = slot_problem(
            start, duration, busy=busy, closed_dates=closed_dates, now=now, hours=hours
        )
        if problem is None:
            slots.append(start)
        start += hours.slot_step
    return slots


# --- Database-backed helpers -------------------------------------------------------------


def find_available_slots(
    db: Session,
    duration: timedelta,
    *,
    location: BookingLocation = BookingLocation.CUSTOMER_HOME,
    date_from: date | None = None,
    days: int = 7,
    now: datetime | None = None,
    hours: BusinessHours = HOURS,
) -> list[tuple[date, list[datetime]]]:
    """Free start times for each open day in [date_from, date_from + days)."""
    now = now or clock.now()
    first = max(date_from or date.min, earliest_bookable_date(now, hours))
    last = first + timedelta(days=days)

    closed = _closed_dates(db, first, last)
    busy = _busy_periods(db, *_day_bounds(first, last, hours)) if _uses_team(location) else []

    result = []
    for offset in range(days):
        day = first + timedelta(days=offset)
        if is_open_day(day, closed, hours):
            slots = free_slots(day, duration, busy=busy, closed_dates=closed, now=now, hours=hours)
            result.append((day, slots))
    return result


def ensure_slot_available(
    db: Session,
    start: datetime,
    duration: timedelta,
    *,
    location: BookingLocation,
    now: datetime | None = None,
    hours: BusinessHours = HOURS,
) -> None:
    now = now or clock.now()
    day = start.astimezone(hours.timezone).date()
    closed = _closed_dates(db, day, day + timedelta(days=1))
    busy = _busy_periods(db, start, start + duration) if _uses_team(location) else []

    problem = slot_problem(start, duration, busy=busy, closed_dates=closed, now=now, hours=hours)
    if problem:
        raise SlotUnavailableError(problem)


def _uses_team(location: BookingLocation) -> bool:
    return location is BookingLocation.CUSTOMER_HOME


def _day_bounds(first: date, last: date, hours: BusinessHours) -> Period:
    return (
        datetime.combine(first, time.min, tzinfo=hours.timezone),
        datetime.combine(last, time.min, tzinfo=hours.timezone),
    )


def _busy_periods(db: Session, start: datetime, end: datetime) -> list[Period]:
    """Active home visits that overlap [start, end)."""
    rows = db.execute(
        select(Booking.scheduled_start, Booking.scheduled_end).where(
            Booking.location == BookingLocation.CUSTOMER_HOME,
            Booking.status.in_(BLOCKING_STATUSES),
            Booking.scheduled_start < end,
            Booking.scheduled_end > start,
        )
    )
    return [(row.scheduled_start, row.scheduled_end) for row in rows]


def _closed_dates(db: Session, first: date, last: date) -> set[date]:
    stmt = select(ClosedDate.day).where(ClosedDate.day >= first, ClosedDate.day < last)
    return set(db.scalars(stmt))
