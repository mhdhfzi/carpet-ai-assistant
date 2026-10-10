from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.test_api_services import create_service


def booking_payload(service_id: int, **overrides: Any) -> dict[str, Any]:
    return {
        "customer": {"name": "Aminah", "phone": "012-345 6789", "area": "Seremban"},
        "scheduled_start": "2026-11-02T09:00:00+08:00",
        "scheduled_end": "2026-11-02T11:00:00+08:00",
        "items": [{"service_id": service_id, "quantity": "100"}],
        **overrides,
    }


@pytest.fixture
def service_id(client: TestClient) -> int:
    return create_service(client)["id"]  # RM1.20 per sqft, RM80 minimum


def create_booking(client: TestClient, service_id: int, **overrides: Any) -> dict[str, Any]:
    response = client.post("/api/bookings", json=booking_payload(service_id, **overrides))
    assert response.status_code == 201, response.text
    return response.json()


def test_create_booking_prices_on_server(client: TestClient, service_id: int) -> None:
    booking = create_booking(client, service_id)

    assert booking["status"] == "pending"
    assert booking["estimated_price"] == "120.00"  # 100 sqft x RM1.20
    assert booking["items"][0]["service"]["name"] == "Carpet shampoo"
    assert booking["items"][0]["unit_price"] == "1.20"
    assert booking["customer"]["phone"] == "+60123456789"  # normalised


def test_minimum_charge_applies_to_small_jobs(client: TestClient, service_id: int) -> None:
    booking = create_booking(
        client, service_id, items=[{"service_id": service_id, "quantity": "10"}]
    )

    assert booking["estimated_price"] == "80.00"  # 10 x 1.20 = 12, below the RM80 minimum


def test_client_supplied_price_is_ignored(client: TestClient, service_id: int) -> None:
    booking = create_booking(client, service_id, estimated_price="1.00")

    assert booking["estimated_price"] == "120.00"


def test_existing_customer_is_reused_by_phone(client: TestClient, service_id: int) -> None:
    first = create_booking(client, service_id)
    second = create_booking(
        client,
        service_id,
        customer={"name": "Someone Else", "phone": "+60123456789", "address": "Somewhere"},
    )

    assert second["customer"]["id"] == first["customer"]["id"]
    assert second["customer"]["name"] == "Aminah"  # stored details are not overwritten


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"scheduled_end": "2026-11-02T08:00:00+08:00"}, "scheduled_end must be after"),
        ({"scheduled_start": "2026-11-02T09:00:00"}, "timezone"),
        ({"items": []}, "at least 1 item"),
        ({"customer": {"name": "A", "phone": "abc"}}, "Invalid phone number"),
    ],
)
def test_invalid_booking_requests_are_rejected(
    client: TestClient, service_id: int, overrides: dict[str, Any], message: str
) -> None:
    response = client.post("/api/bookings", json=booking_payload(service_id, **overrides))

    assert response.status_code == 422
    assert message in response.text


def test_booking_unknown_or_inactive_service_is_rejected(
    client: TestClient, service_id: int
) -> None:
    unknown = client.post("/api/bookings", json=booking_payload(999999))
    assert unknown.status_code == 422
    assert "Unknown service" in unknown.json()["detail"]

    client.delete(f"/api/services/{service_id}")
    inactive = client.post("/api/bookings", json=booking_payload(service_id))
    assert inactive.status_code == 422
    assert "no longer offered" in inactive.json()["detail"]


def test_status_lifecycle(client: TestClient, service_id: int) -> None:
    booking_id = create_booking(client, service_id)["id"]

    for new_status in ("confirmed", "done"):
        response = client.patch(f"/api/bookings/{booking_id}", json={"status": new_status})
        assert response.status_code == 200
        assert response.json()["status"] == new_status

    # A finished job can't be reopened or cancelled.
    response = client.patch(f"/api/bookings/{booking_id}", json={"status": "cancelled"})
    assert response.status_code == 409


def test_update_notes(client: TestClient, service_id: int) -> None:
    booking_id = create_booking(client, service_id)["id"]

    response = client.patch(f"/api/bookings/{booking_id}", json={"notes": "Gate code 1234"})

    assert response.json()["notes"] == "Gate code 1234"
    assert response.json()["status"] == "pending"


def test_list_bookings_filters(client: TestClient, service_id: int) -> None:
    early = create_booking(client, service_id)
    late = create_booking(
        client,
        service_id,
        scheduled_start="2026-11-05T09:00:00+08:00",
        scheduled_end="2026-11-05T10:00:00+08:00",
    )
    client.patch(f"/api/bookings/{late['id']}", json={"status": "confirmed"})

    def ids(**params: str) -> list[int]:
        return [b["id"] for b in client.get("/api/bookings", params=params).json()]

    assert ids() == [early["id"], late["id"]]
    assert ids(status="confirmed") == [late["id"]]
    assert ids(start_from="2026-11-03T00:00:00+08:00") == [late["id"]]
    assert ids(start_to="2026-11-03T00:00:00+08:00") == [early["id"]]


def test_missing_booking_returns_404(client: TestClient) -> None:
    assert client.get("/api/bookings/999999").status_code == 404
