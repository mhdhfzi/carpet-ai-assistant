"""Unit tests for the scheduling rules. No database: busy periods are passed in directly."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.db.models import Service
from app.services.availability import (
    earliest_bookable_date,
    free_slots,
    slot_problem,
    visit_duration,
)

MYT = ZoneInfo("Asia/Kuala_Lumpur")
NOW = datetime(2026, 10, 10, 10, 0, tzinfo=MYT)  # Saturday
MONDAY = date(2026, 10, 12)
FRIDAY = date(2026, 10, 16)
TWO_HOURS = timedelta(hours=2)


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=MYT)


def problem(start: datetime, duration: timedelta = TWO_HOURS, busy=(), closed=()) -> str | None:
    return slot_problem(start, duration, busy=busy, closed_dates=set(closed), now=NOW)


def test_earliest_bookable_date_is_two_days_ahead() -> None:
    assert earliest_bookable_date(NOW) == MONDAY


def test_notice_is_counted_in_malaysian_dates_not_utc() -> None:
    # 23:30 Saturday in Malaysia is still Saturday 15:30 UTC; the local date is what counts.
    late_saturday = datetime(2026, 10, 10, 23, 30, tzinfo=MYT)
    assert earliest_bookable_date(late_saturday) == MONDAY


def test_valid_slot_has_no_problem() -> None:
    assert problem(at(MONDAY, 9)) is None


def test_slot_given_in_utc_is_converted_to_local_time() -> None:
    assert problem(datetime(2026, 10, 12, 1, 0, tzinfo=ZoneInfo("UTC"))) is None  # 09:00 MYT


@pytest.mark.parametrize(
    ("start", "duration", "expected"),
    [
        (at(date(2026, 10, 11), 10), TWO_HOURS, "2 days' notice"),  # tomorrow
        (at(FRIDAY, 10), TWO_HOURS, "closed on Fridays"),
        (at(MONDAY, 8, 30), TWO_HOURS, "opening hours"),  # starts before 9:00
        (at(MONDAY, 16), TWO_HOURS, "opening hours"),  # would end at 18:00
    ],
)
def test_slot_problems(start: datetime, duration: timedelta, expected: str) -> None:
    assert expected in (problem(start, duration) or "")


def test_job_may_end_exactly_at_closing_time() -> None:
    assert problem(at(MONDAY, 15, 30)) is None  # 15:30 + 2h = 17:30


def test_closed_date_is_rejected() -> None:
    assert "closed on 12 October 2026" in (problem(at(MONDAY, 10), closed=[MONDAY]) or "")


def test_overlapping_booking_is_rejected() -> None:
    busy = [(at(MONDAY, 10), at(MONDAY, 12))]

    assert "clashes" in (problem(at(MONDAY, 11), busy=busy) or "")
    assert "clashes" in (problem(at(MONDAY, 9), busy=busy) or "")  # 9-11 overlaps 10-12


def test_back_to_back_bookings_are_allowed() -> None:
    busy = [(at(MONDAY, 10), at(MONDAY, 12))]

    assert problem(at(MONDAY, 12), busy=busy) is None
    assert problem(at(MONDAY, 9, 30), duration=timedelta(minutes=30), busy=busy) is None


def test_free_slots_on_an_empty_day() -> None:
    slots = free_slots(MONDAY, TWO_HOURS, busy=[], closed_dates=set(), now=NOW)

    assert slots[0] == at(MONDAY, 9)
    assert slots[-1] == at(MONDAY, 15, 30)  # last start that still ends by 17:30
    assert len(slots) == 14  # every 30 minutes from 9:00 to 15:30


def test_free_slots_skip_times_that_clash() -> None:
    busy = [(at(MONDAY, 11), at(MONDAY, 13))]

    slots = free_slots(MONDAY, TWO_HOURS, busy=busy, closed_dates=set(), now=NOW)

    # 9:00 ends at 11:00 (back to back is fine); 9:30 to 12:30 would overlap.
    assert at(MONDAY, 9) in slots
    assert not any(at(MONDAY, 9, 30) <= s <= at(MONDAY, 12, 30) for s in slots)
    assert at(MONDAY, 13) in slots


def test_short_carpet_collection_visits_fit_more_slots() -> None:
    slots = free_slots(MONDAY, timedelta(minutes=30), busy=[], closed_dates=set(), now=NOW)

    assert slots[-1] == at(MONDAY, 17)
    assert len(slots) == 17


def test_no_slots_on_closed_days() -> None:
    assert free_slots(FRIDAY, TWO_HOURS, busy=[], closed_dates=set(), now=NOW) == []
    assert free_slots(MONDAY, TWO_HOURS, busy=[], closed_dates={MONDAY}, now=NOW) == []


def test_visit_duration_is_the_longest_item() -> None:
    carpet = Service(name="Karpet Biasa", visit_minutes=30)
    sofa = Service(name="Cucian Sofa", visit_minutes=120)

    assert visit_duration([carpet]) == timedelta(minutes=30)
    assert visit_duration([carpet, sofa]) == TWO_HOURS
