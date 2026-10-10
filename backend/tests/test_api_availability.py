from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Booking, BookingLocation, BookingStatus, Customer
from tests.test_api_bookings import at, booking_payload
from tests.test_api_services import create_service

# Clock is frozen at Saturday 10 Oct 2026 10:00 MYT, so Monday 12 Oct is the first bookable day.
MONDAY = "2026-10-12"


@pytest.fixture
def sofa_id(client: TestClient) -> int:
    return create_service(client, name="Cucian Sofa", pricing_unit="per_item", unit_price="60")[
        "id"
    ]


@pytest.fixture
def carpet_id(client: TestClient) -> int:
    return create_service(client, name="Karpet Biasa", unit_price="1.80", visit_minutes=30)["id"]


def get_availability(client: TestClient, *service_ids: int, **params: Any) -> list[dict]:
    response = client.get("/api/availability", params={"service_ids": list(service_ids), **params})
    assert response.status_code == 200, response.text
    return response.json()


def book(client: TestClient, service_id: int, start: str, **overrides: Any):
    return client.post(
        "/api/bookings",
        json=booking_payload(
            service_id,
            scheduled_start=start,
            items=[{"service_id": service_id, "quantity": "1"}],
            **overrides,
        ),
    )


def test_availability_starts_after_notice_and_skips_fridays(
    client: TestClient, sofa_id: int
) -> None:
    days = get_availability(client, sofa_id, days=7)

    assert [d["day"] for d in days] == [
        "2026-10-12",  # Mon
        "2026-10-13",
        "2026-10-14",
        "2026-10-15",  # Thu; Fri 16th is skipped
        "2026-10-17",
        "2026-10-18",
    ]
    assert len(days[0]["slots"]) == 14  # 2-hour visits, 9:00 to 15:30


def test_cannot_ask_for_dates_before_the_notice_period(client: TestClient, sofa_id: int) -> None:
    days = get_availability(client, sofa_id, date_from="2026-10-10", days=3)

    assert days[0]["day"] == MONDAY


def test_booked_time_disappears_from_availability(client: TestClient, sofa_id: int) -> None:
    assert book(client, sofa_id, "2026-10-12T09:00:00+08:00").status_code == 201

    slots = get_availability(client, sofa_id, date_from=MONDAY, days=1)[0]["slots"]

    assert at(slots[0]) == at("2026-10-12T11:00:00+08:00")


def test_cancelled_booking_frees_its_slot(client: TestClient, sofa_id: int) -> None:
    booking = book(client, sofa_id, "2026-10-12T09:00:00+08:00").json()
    client.patch(f"/api/bookings/{booking['id']}", json={"status": "cancelled"})

    slots = get_availability(client, sofa_id, date_from=MONDAY, days=1)[0]["slots"]

    assert at(slots[0]) == at("2026-10-12T09:00:00+08:00")


def test_visit_length_follows_the_services(
    client: TestClient, sofa_id: int, carpet_id: int
) -> None:
    carpet_only = get_availability(client, carpet_id, date_from=MONDAY, days=1)[0]["slots"]
    with_sofa = get_availability(client, carpet_id, sofa_id, date_from=MONDAY, days=1)[0]["slots"]

    assert len(carpet_only) == 17  # 30-minute collection visits, up to 17:00
    assert len(with_sofa) == 14  # the sofa makes it a 2-hour visit

    booking = book(client, carpet_id, "2026-10-12T09:00:00+08:00").json()
    assert at(booking["scheduled_end"]) == at("2026-10-12T09:30:00+08:00")


def test_clashing_home_visit_is_rejected(client: TestClient, sofa_id: int) -> None:
    assert book(client, sofa_id, "2026-10-12T10:00:00+08:00").status_code == 201

    response = book(client, sofa_id, "2026-10-12T11:00:00+08:00")

    assert response.status_code == 422
    assert "clashes" in response.json()["detail"]


def test_shop_drop_off_does_not_need_the_team(client: TestClient, sofa_id: int) -> None:
    assert book(client, sofa_id, "2026-10-12T10:00:00+08:00").status_code == 201

    response = book(client, sofa_id, "2026-10-12T10:00:00+08:00", location="shop")

    assert response.status_code == 201
    assert response.json()["location"] == "shop"
    shop_slots = get_availability(client, sofa_id, location="shop", date_from=MONDAY, days=1)
    assert len(shop_slots[0]["slots"]) == 14


@pytest.mark.parametrize(
    ("start", "message"),
    [
        ("2026-10-11T10:00:00+08:00", "notice"),
        ("2026-10-16T10:00:00+08:00", "closed on Fridays"),
        ("2026-10-12T16:00:00+08:00", "opening hours"),
    ],
)
def test_booking_outside_business_rules_is_rejected(
    client: TestClient, sofa_id: int, start: str, message: str
) -> None:
    response = book(client, sofa_id, start)

    assert response.status_code == 422
    assert message in response.json()["detail"]


def test_closed_dates_block_bookings_and_availability(client: TestClient, sofa_id: int) -> None:
    response = client.put(f"/api/closed-dates/{MONDAY}", json={"reason": "Deepavali"})
    assert response.status_code == 200

    assert [c["reason"] for c in client.get("/api/closed-dates").json()] == ["Deepavali"]
    assert get_availability(client, sofa_id, date_from=MONDAY, days=1) == []
    assert book(client, sofa_id, "2026-10-12T10:00:00+08:00").status_code == 422

    assert client.delete(f"/api/closed-dates/{MONDAY}").status_code == 204
    assert book(client, sofa_id, "2026-10-12T10:00:00+08:00").status_code == 201


def test_closing_a_date_twice_updates_the_reason(client: TestClient) -> None:
    client.put(f"/api/closed-dates/{MONDAY}", json={"reason": "Holiday"})
    client.put(f"/api/closed-dates/{MONDAY}", json={"reason": "Deepavali"})

    assert [c["reason"] for c in client.get("/api/closed-dates").json()] == ["Deepavali"]


# --- Database-level guarantee ---------------------------------------------------------------


def _home_booking(customer: Customer, start: datetime, status=BookingStatus.PENDING) -> Booking:
    return Booking(
        customer=customer,
        scheduled_start=start,
        scheduled_end=start + timedelta(hours=2),
        location=BookingLocation.CUSTOMER_HOME,
        status=status,
        estimated_price=Decimal("0"),
        estimated_price_max=Decimal("0"),
    )


def test_database_rejects_overlapping_home_visits(db: Session) -> None:
    """Even if two requests pass the availability check at once, only one row can win."""
    customer = Customer(name="A", phone="+60123456789")
    db.add(_home_booking(customer, at("2026-10-12T10:00:00+08:00")))
    db.flush()
    db.add(_home_booking(customer, at("2026-10-12T11:00:00+08:00")))

    with pytest.raises(IntegrityError, match="ex_bookings_no_overlap"):
        db.flush()


def test_database_allows_overlap_with_cancelled_bookings(db: Session) -> None:
    customer = Customer(name="A", phone="+60123456789")
    start = at("2026-10-12T10:00:00+08:00")
    db.add(_home_booking(customer, start, status=BookingStatus.CANCELLED))
    db.add(_home_booking(customer, start))
    db.flush()

    assert db.scalar(text("SELECT count(*) FROM bookings")) == 2
