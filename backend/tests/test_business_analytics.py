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


def test_business_numbers_from_orders_and_payments(
    client: TestClient, services: dict[str, int]
) -> None:
    carpet = {"service_id": services["Karpet Biasa"], "length_ft": "8", "width_ft": "10"}
    sofa = {"service_id": services["Cucian Sofa"], "quantity": "3"}
    first = place(client, [carpet, sofa], deposit="100.00", deposit_method="transfer")  # 324
    second = place(client, [carpet])  # 144
    cancelled = place(client, [carpet])
    client.patch(f"/api/orders/{cancelled['id']}", json={"status": "cancelled"})
    client.post(f"/api/orders/{second['id']}/payments", json={"amount": "144.00", "method": "cash"})
    for status in ("washed", "ready"):
        client.patch(f"/api/orders/{first['id']}", json={"status": status})

    body = client.get("/api/analytics/business", params={"days": 7}).json()

    assert (body["revenue"], body["orders"], body["order_value"]) == ("244.00", 2, "468.00")
    assert body["revenue_by_method"] == {"cash": "144.00", "transfer": "100.00", "duitnow": "0"}
    assert body["cancelled"] == 1
    assert (body["unpaid"], body["unpaid_orders"]) == ("224.00", 1)  # 324 - 100
    assert body["in_progress"] == {"received": 1, "washed": 0, "ready": 1}
    assert body["services"][0] == {"name": "Cucian Sofa", "items": 3, "value": "180.00"}
    assert body["services"][1] == {"name": "Karpet Biasa", "items": 2, "value": "288.00"}
    assert {d["weekday"]: d["orders"] for d in body["busy_days"]}["Sat"] == 2
    assert body["average_days_to_ready"] == 0.0  # washed and dried the same (frozen) day


def test_revenue_is_daily_for_a_week_and_weekly_for_longer(
    client: TestClient, services: dict[str, int]
) -> None:
    week = client.get("/api/analytics/business", params={"days": 7}).json()
    month = client.get("/api/analytics/business", params={"days": 30}).json()

    assert [b["label"] for b in week["revenue_over_time"]] == [
        "Sun 4", "Mon 5", "Tue 6", "Wed 7", "Thu 8", "Fri 9", "Sat 10",
    ]  # fmt: skip
    assert month["revenue_over_time"][0]["start"] == "2026-09-07"  # the Monday of 11 Sep
    assert month["revenue_over_time"][-1]["label"] == "5 Oct"


def test_business_analytics_is_owner_only_and_needs_the_back_office(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ORDERS_ENABLED", "false")
    get_settings.cache_clear()

    assert client.get("/api/analytics/business").status_code == 404
