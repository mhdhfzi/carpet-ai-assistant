"""Unit tests for booking business rules that don't need a database."""

import pytest

from app.db.models import BookingStatus
from app.schemas.booking import normalize_phone
from app.services.bookings import ALLOWED_TRANSITIONS


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("012-345 6789", "+60123456789"),
        ("0123456789", "+60123456789"),
        ("60123456789", "+60123456789"),
        ("+60 12-345 6789", "+60123456789"),
        ("(06) 761 2345", "+6067612345"),  # Seremban landline
        ("+6591234567", "+6591234567"),  # foreign numbers are kept as-is
    ],
)
def test_normalize_phone(raw: str, expected: str) -> None:
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", "0123", "+0123456789", "+60 12 345 6789 1234 5"])
def test_normalize_phone_rejects_invalid(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_phone(raw)


def test_every_status_has_transition_rules() -> None:
    assert set(ALLOWED_TRANSITIONS) == set(BookingStatus)


@pytest.mark.parametrize("final", [BookingStatus.DONE, BookingStatus.CANCELLED])
def test_final_statuses_cannot_change(final: BookingStatus) -> None:
    assert ALLOWED_TRANSITIONS[final] == set()
