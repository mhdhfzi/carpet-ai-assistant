"""Business numbers from orders and payments. Clock frozen at Saturday 10 Oct 2026."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Service
from app.seed import seed_services

ALI = {"name": "Ali", "phone": "012-345 6789"}


@pytest.fixture(autouse=True)
def orders_on(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ORDERS_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def services(db: Session) -> dict[str, int]:
    seed_services(db)
    return {s.name: s.id for s in db.scalars(select(Service))}


def place(client: TestClient, items: list[dict], **extra) -> dict:
    response = client.post("/api/orders", json={"customer": ALI, "items": items, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_business_numbers_month_by_month(client: TestClient, services: dict[str, int]) -> None:
    carpet = {"service_id": services["Karpet Biasa"], "length_ft": "8", "width_ft": "10"}
    sofa = {"service_id": services["Cucian Sofa"], "quantity": "3"}
    # September: one carpet, paid.
    september = place(client, [carpet], received_on="2026-09-15")  # 144
    client.post(
        f"/api/orders/{september['id']}/payments",
        json={"amount": "144.00", "method": "cash", "paid_on": "2026-09-20"},
    )
    # October (the clock's month): two carpets, a kerja luar job and a cancelled order.
    first = place(client, [carpet], deposit="100.00", deposit_method="transfer")  # 144
    place(client, [sofa])  # 180, not done or paid yet
    second = place(client, [carpet])  # 144
    cancelled = place(client, [carpet])
    client.patch(f"/api/orders/{cancelled['id']}", json={"status": "cancelled"})
    client.post(f"/api/orders/{second['id']}/payments", json={"amount": "144.00", "method": "cash"})
    for status in ("washed", "ready"):
        client.patch(f"/api/orders/{first['id']}", json={"status": status})

    body = client.get("/api/analytics/business").json()

    # Totals for the whole business.
    assert body["revenue_total"] == "388.00"  # 144 in September + 244 in October
    assert (body["unpaid"], body["unpaid_orders"]) == ("224.00", 2)  # 144 - 100, and 180
    # The last 12 months side by side.
    months = {m["month"]: m for m in body["months"]}
    assert [m["month"] for m in body["months"]][0::11] == ["2025-11", "2026-10"]
    assert months["2026-09"] == {
        "month": "2026-09",
        "revenue": "144.00",
        "orders": 1,
        "top_service": "Karpet Biasa",
    }
    assert months["2026-10"] == {
        "month": "2026-10",
        "revenue": "244.00",
        "orders": 3,
        "top_service": "Cucian Sofa",  # 3 seats beat 2 carpets
    }
    assert months["2026-08"]["top_service"] is None
    # This month in detail.
    assert body["month"] == "2026-10"
    assert (body["revenue"], body["orders"], body["order_value"]) == ("244.00", 3, "468.00")
    assert body["revenue_by_method"] == {"cash": "144.00", "transfer": "100.00", "duitnow": "0"}
    assert body["cancelled"] == 1
    assert body["services"][0] == {"name": "Cucian Sofa", "items": 3, "value": "180.00"}
    assert body["services"][1] == {"name": "Karpet Biasa", "items": 2, "value": "288.00"}
    assert {d["weekday"]: d["orders"] for d in body["busy_days"]}["Sat"] == 3
    assert body["average_days_to_ready"] == 0.0  # washed and packed the same (frozen) day
    assert "in_progress" not in body  # the work pages' cards show that


def test_an_earlier_month_in_detail(client: TestClient, services: dict[str, int]) -> None:
    carpet = {"service_id": services["Karpet Biasa"], "length_ft": "8", "width_ft": "10"}
    september = place(client, [carpet], received_on="2026-09-15")
    client.post(
        f"/api/orders/{september['id']}/payments",
        json={"amount": "50.00", "method": "duitnow", "paid_on": "2026-09-30"},
    )
    place(client, [carpet])  # October: not in September's numbers

    body = client.get("/api/analytics/business", params={"month": "2026-09"}).json()
    bad = client.get("/api/analytics/business", params={"month": "2026-13"})

    assert (body["month"], body["start"], body["end"]) == ("2026-09", "2026-09-01", "2026-09-30")
    assert (body["revenue"], body["orders"]) == ("50.00", 1)
    assert body["revenue_by_method"]["duitnow"] == "50.00"
    assert body["revenue_total"] == "50.00"
    assert bad.status_code == 422


def test_business_analytics_is_owner_only_and_needs_the_back_office(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ORDERS_ENABLED", "false")
    get_settings.cache_clear()

    assert client.get("/api/analytics/business").status_code == 404
