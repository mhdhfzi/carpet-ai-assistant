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
BADRUL = {"name": "Badrul", "phone": "013-111 2222"}


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


def place(client: TestClient, items: list[dict], customer: dict = ALI, **extra) -> dict:
    response = client.post("/api/orders", json={"customer": customer, "items": items, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_business_numbers_for_the_year(client: TestClient, services: dict[str, int]) -> None:
    carpet = {"service_id": services["Karpet Biasa"], "length_ft": "8", "width_ft": "10"}
    sofa = {"service_id": services["Cucian Sofa"], "quantity": "3"}
    # Last year: paid in part. Not in this year's numbers.
    old = place(client, [carpet], received_on="2025-12-20", deposit="40.00")
    assert old["balance"] == "104.00"
    # September: one carpet, paid.
    september = place(client, [carpet], received_on="2026-09-15")  # 144
    client.post(
        f"/api/orders/{september['id']}/payments",
        json={"amount": "144.00", "method": "cash", "paid_on": "2026-09-20"},
    )
    # October (the clock's month): two carpets, a kerja luar job and a cancelled order.
    first = place(client, [carpet], deposit="100.00", deposit_method="transfer")  # 144
    place(client, [sofa], BADRUL)  # 180, not done or paid yet
    second = place(client, [carpet])  # 144
    cancelled = place(client, [carpet])
    client.patch(f"/api/orders/{cancelled['id']}", json={"status": "cancelled"})
    client.post(f"/api/orders/{second['id']}/payments", json={"amount": "144.00", "method": "cash"})
    for status in ("washed", "ready"):
        client.patch(f"/api/orders/{first['id']}", json={"status": status})

    body = client.get("/api/analytics/business").json()

    # This year (the default), and the years that can be picked.
    assert (body["year"], body["years"]) == (2026, [2026, 2025])
    assert body["revenue_total"] == "388.00"  # 144 in September + 244 in October
    assert (body["unpaid"], body["unpaid_orders"]) == ("224.00", 2)  # 144 - 100, and 180
    assert body["customers_total"] == 2  # Ali came back three times: still one customer
    # January up to this month, side by side.
    months = {m["month"]: m for m in body["months"]}
    assert [m["month"] for m in body["months"]] == [f"2026-{m:02}" for m in range(1, 11)]
    assert months["2026-09"] == {
        "month": "2026-09",
        "revenue": "144.00",
        "orders": 1,
        "order_value": "144.00",
        "customers": 1,
        "top_service": "Karpet Biasa",
        "items_by_service": {"Karpet Biasa": 1},
    }
    assert months["2026-10"] == {
        "month": "2026-10",
        "revenue": "244.00",
        "orders": 3,
        "order_value": "468.00",
        "customers": 2,  # the cancelled order doesn't count
        "top_service": "Cucian Sofa",  # 3 seats beat 2 carpets
        "items_by_service": {"Cucian Sofa": 3, "Karpet Biasa": 2},
    }
    assert months["2026-08"]["top_service"] is None
    # The December before, for January's change.
    december = body["month_before"]
    assert (december["month"], december["revenue"], december["customers"]) == (
        "2025-12",
        "40.00",
        1,
    )
    # The whole year in detail.
    assert (body["month"], body["start"], body["end"]) == (None, "2026-01-01", "2026-12-31")
    assert (body["revenue"], body["orders"], body["order_value"]) == ("388.00", 4, "612.00")
    assert body["customers"] == 2
    assert body["revenue_by_method"] == {"cash": "288.00", "transfer": "100.00", "duitnow": "0"}
    assert body["cancelled"] == 1
    assert body["services"][0] == {"name": "Karpet Biasa", "items": 3, "value": "432.00"}
    assert body["services"][1] == {"name": "Cucian Sofa", "items": 3, "value": "180.00"}
    assert {d["weekday"]: d["orders"] for d in body["busy_days"]}["Sat"] == 3

    # Last year: its own money, owed balance and all twelve months.
    last = client.get("/api/analytics/business", params={"year": 2025}).json()
    assert (last["revenue_total"], last["unpaid"], last["orders"]) == ("40.00", "104.00", 1)
    assert [m["month"] for m in last["months"]][0::11] == ["2025-01", "2025-12"]
    assert "in_progress" not in body  # the work pages' cards show that


def test_one_month_in_detail(client: TestClient, services: dict[str, int]) -> None:
    carpet = {"service_id": services["Karpet Biasa"], "length_ft": "8", "width_ft": "10"}
    september = place(client, [carpet], received_on="2026-09-15")
    client.post(
        f"/api/orders/{september['id']}/payments",
        json={"amount": "50.00", "method": "duitnow", "paid_on": "2026-09-30"},
    )
    place(client, [carpet])  # October: not in September's numbers

    body = client.get("/api/analytics/business", params={"year": 2026, "month": 9}).json()
    bad = client.get("/api/analytics/business", params={"month": 13})

    assert (body["month"], body["start"], body["end"]) == (9, "2026-09-01", "2026-09-30")
    assert (body["revenue"], body["orders"], body["customers"]) == ("50.00", 1, 1)
    assert body["revenue_by_method"]["duitnow"] == "50.00"
    assert body["revenue_total"] == "50.00"  # the year's totals stay the year's
    assert bad.status_code == 422


def test_a_measured_lain_lain_counts_as_one_item(
    client: TestClient, services: dict[str, int]
) -> None:
    shaggy = {"service_id": services["Lain-lain (kedai)"], "length_ft": "5", "width_ft": "8"}
    curtains = {"service_id": services["Lain-lain (kedai)"], "quantity": "3"}
    place(client, [shaggy | {"notes": "Shaggy"}, curtains | {"notes": "Langsir"}])

    body = client.get("/api/analytics/business").json()

    assert body["services"][0]["items"] == 4  # the shaggy rug (not its 40 sq ft) + 3 curtains


def test_business_analytics_is_owner_only_and_needs_the_back_office(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ORDERS_ENABLED", "false")
    get_settings.cache_clear()

    assert client.get("/api/analytics/business").status_code == 404
