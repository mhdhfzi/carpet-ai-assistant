"""The back office: orders as in the owner's book, and what staff may and may not do.
Clock frozen at Saturday 10 Oct 2026 (Malaysia)."""

import re
from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.models import Owner, OwnerRole, Service
from app.seed import seed_services
from tests.conftest import _OWNER_PASSWORD_HASH
from tests.test_auth import PROTECTED_ROUTES

TODAY = date(2026, 10, 10)
ALI = {"name": "Ali", "phone": "012-345 6789", "area": "Seremban 2", "address": "5, Jalan A"}


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


@pytest.fixture
def staff_client(anon_client: TestClient, db: Session) -> TestClient:
    staff = Owner(
        email="worker@example.com",
        name="Worker",
        password_hash=_OWNER_PASSWORD_HASH,
        role=OwnerRole.STAFF,
    )
    db.add(staff)
    db.flush()
    anon_client.headers["Authorization"] = f"Bearer {create_access_token(staff.id)[0]}"
    return anon_client


def carpet(services: dict[str, int], name: str, length: str, width: str, **extra) -> dict:
    return {"service_id": services[name], "length_ft": length, "width_ft": width, **extra}


def counted(services: dict[str, int], name: str, quantity: int) -> dict:
    return {"service_id": services[name], "quantity": quantity}


def new_order(client: TestClient, services: dict[str, int], **extra) -> dict:
    body = {
        "customer": ALI,
        "items": [
            carpet(services, "Karpet Biasa", "8", "10", notes="tompok kopi"),
            counted(services, "Cucian Sofa", 3),
        ],
        **extra,
    }
    response = client.post("/api/orders", json=body)
    assert response.status_code == 201, response.text
    return response.json()


# --- Recording an order ----------------------------------------------------------------------


def test_an_order_is_priced_from_the_measured_sizes(
    client: TestClient, services: dict[str, int]
) -> None:
    order = new_order(client, services, deposit="50.00")

    carpet_line, sofa_line = order["items"]
    assert carpet_line["quantity"] == "80.00"  # 8 x 10 ft
    assert carpet_line["line_total"] == "144.00"  # RM1.80 per sq ft
    assert carpet_line["notes"] == "tompok kopi"
    assert sofa_line["line_total"] == "180.00"  # 3 seats x RM60
    assert (order["subtotal"], order["total"], order["balance"]) == ("324.00", "324.00", "274.00")
    assert order["received_on"] == TODAY.isoformat()
    assert order["status"] == "received"
    assert order["events"][0]["by"] == "Test Owner"


def test_orders_are_numbered_in_sequence_and_items_tagged(
    client: TestClient, services: dict[str, int]
) -> None:
    first = new_order(client, services)
    second = new_order(client, services)

    assert (first["number"], second["number"]) == (1, 2)
    assert [item["tag"] for item in second["items"]] == ["2-1", "2-2"]


def test_a_returning_customer_is_found_by_phone(
    client: TestClient, services: dict[str, int]
) -> None:
    first = new_order(client, services)
    moved = {**ALI, "phone": "+60 12-3456789", "address": "9, Jalan Baru"}
    second = client.post(
        "/api/orders", json={"customer": moved, "items": [counted(services, "Cucian Sofa", 2)]}
    ).json()

    assert second["customer"]["id"] == first["customer"]["id"]
    assert second["customer"]["address"] == "9, Jalan Baru"


def test_handmade_carpet_waits_for_the_owner_to_price_it(
    client: TestClient, services: dict[str, int]
) -> None:
    order = client.post(
        "/api/orders",
        json={"customer": ALI, "items": [carpet(services, "Karpet Handmade", "5", "8")]},
    ).json()
    assert order["price_pending"] is True
    assert order["items"][0]["unit_price"] is None

    priced = client.patch(
        f"/api/orders/{order['id']}",
        json={"items": [carpet(services, "Karpet Handmade", "5", "8", unit_price="3.20")]},
    ).json()

    assert priced["price_pending"] is False
    assert priced["total"] == "128.00"  # 40 sq ft x RM3.20


def test_car_seats_are_priced_per_car(client: TestClient, services: dict[str, int]) -> None:
    order = client.post(
        "/api/orders",
        json={"customer": ALI, "items": [counted(services, "Cucian Seat Kereta MPV", 1)]},
    ).json()

    assert order["total"] == "170.00"


@pytest.mark.parametrize(
    ("item", "message"),
    [
        ({"service": "Karpet Biasa"}, "enter the size"),
        ({"service": "Cucian Sofa", "quantity": 1.5}, "whole number"),
        ({"service": "Cucian Sofa"}, "enter how many"),
    ],
)
def test_items_need_a_size_or_a_whole_count(
    client: TestClient, services: dict[str, int], item: dict, message: str
) -> None:
    body_item = {"service_id": services[item.pop("service")], **item}

    response = client.post("/api/orders", json={"customer": ALI, "items": [body_item]})

    assert response.status_code == 422
    assert message in response.json()["detail"]


def test_old_orders_keep_their_prices_when_the_price_list_changes(
    client: TestClient, services: dict[str, int], db: Session
) -> None:
    order = new_order(client, services)
    db.get(Service, services["Cucian Sofa"]).unit_price = 75
    db.flush()

    edited = client.patch(
        f"/api/orders/{order['id']}",
        json={
            "items": [
                carpet(services, "Karpet Biasa", "8", "10"),
                counted(services, "Cucian Sofa", 3),
            ]
        },
    ).json()

    assert edited["items"][1]["unit_price"] == "60.00"


# --- Status ----------------------------------------------------------------------------------


def test_status_steps_record_their_dates_and_the_ready_window(
    client: TestClient, services: dict[str, int]
) -> None:
    order = new_order(client, services)

    washed = client.patch(f"/api/orders/{order['id']}", json={"status": "washed"}).json()

    assert washed["washed_on"] == "2026-10-10"
    assert (washed["ready_from"], washed["ready_by"]) == ("2026-10-15", "2026-10-17")
    assert [e["status"] for e in washed["events"]] == ["received", "washed"]


def test_the_owner_can_correct_a_status_backwards(
    client: TestClient, services: dict[str, int]
) -> None:
    order = new_order(client, services)
    for status in ("washed", "ready"):
        client.patch(f"/api/orders/{order['id']}", json={"status": status})

    back = client.patch(
        f"/api/orders/{order['id']}", json={"status": "washed", "status_note": "masih basah"}
    ).json()

    assert back["status"] == "washed" and back["ready_on"] is None
    assert back["events"][-1]["note"] == "masih basah"


def test_a_cancelled_order_cannot_change(client: TestClient, services: dict[str, int]) -> None:
    order = new_order(client, services)
    client.patch(f"/api/orders/{order['id']}", json={"status": "cancelled"})

    response = client.patch(f"/api/orders/{order['id']}", json={"deposit": "10.00"})

    assert response.status_code == 422


# --- Finding orders and customers ------------------------------------------------------------


@pytest.mark.parametrize("q", ["1-2", "1", "3456789", "ali"])
def test_orders_are_found_by_tag_number_phone_or_name(
    client: TestClient, services: dict[str, int], q: str
) -> None:
    new_order(client, services)

    found = client.get("/api/orders", params={"q": q}).json()

    assert [o["number"] for o in found] == [1]


def test_the_order_list_filters_by_status(client: TestClient, services: dict[str, int]) -> None:
    first = new_order(client, services)
    new_order(client, services)
    client.patch(f"/api/orders/{first['id']}", json={"status": "washed"})

    washed = client.get("/api/orders", params={"status": "washed"}).json()

    assert [o["number"] for o in washed] == [1]


def test_a_customer_page_shows_their_order_history(
    client: TestClient, services: dict[str, int]
) -> None:
    new_order(client, services)
    new_order(client, services)

    match = client.get("/api/customers", params={"q": "0123456789"}).json()
    detail = client.get(f"/api/customers/{match[0]['id']}").json()

    assert match[0]["orders"] == 2
    assert [o["number"] for o in detail["order_history"]] == [2, 1]


def test_history_holds_finished_and_cancelled_orders(
    client: TestClient, services: dict[str, int]
) -> None:
    done, cancelled, active = (new_order(client, services) for _ in range(3))
    for status in ("washed", "ready", "completed"):
        client.patch(f"/api/orders/{done['id']}", json={"status": status})
    client.patch(f"/api/orders/{cancelled['id']}", json={"status": "cancelled"})

    history = client.get(
        "/api/orders", params=[("status", "completed"), ("status", "cancelled")]
    ).json()

    assert [o["number"] for o in history] == [cancelled["number"], done["number"]]
    assert active["number"] not in [o["number"] for o in history]


def test_the_customer_table_lists_everyone_with_their_order_value(
    client: TestClient, services: dict[str, int]
) -> None:
    new_order(client, services)  # RM324
    cancelled = new_order(client, services)
    client.patch(f"/api/orders/{cancelled['id']}", json={"status": "cancelled"})
    client.post(
        "/api/orders",
        json={
            "customer": {"name": "Siti", "phone": "019-111 2222"},
            "items": [counted(services, "Cucian Tilam Queen", 1)],
            "discount": "20.00",
        },
    )

    table = client.get("/api/customers").json()

    by_name = {row["name"]: row for row in table}
    assert by_name["Ali"]["orders"] == 2
    assert by_name["Ali"]["total_value"] == "324.00"  # the cancelled order doesn't count
    assert by_name["Siti"]["total_value"] == "120.00"  # RM140 less the RM20 discount
    detail = client.get(f"/api/customers/{by_name['Ali']['id']}").json()
    assert detail["total_value"] == "324.00"


# --- Staff -----------------------------------------------------------------------------------


def test_staff_record_orders_and_move_them_one_step(
    staff_client: TestClient, services: dict[str, int]
) -> None:
    order = new_order(staff_client, services, deposit="20.00")

    washed = staff_client.patch(f"/api/orders/{order['id']}", json={"status": "washed"})

    assert washed.status_code == 200
    assert washed.json()["events"][0]["by"] == "Worker"


@pytest.mark.parametrize(
    ("change", "status_code"),
    [
        ({"discount": "10.00"}, 403),
        ({"status": "cancelled"}, 403),
        ({"status": "ready"}, 409),  # skips "washed"
    ],
)
def test_staff_cannot_do_the_owners_part(
    staff_client: TestClient, services: dict[str, int], change: dict, status_code: int
) -> None:
    order = new_order(staff_client, services)

    assert staff_client.patch(f"/api/orders/{order['id']}", json=change).status_code == status_code


def test_staff_cannot_set_prices(staff_client: TestClient, services: dict[str, int]) -> None:
    item = carpet(services, "Karpet Handmade", "5", "8", unit_price="1.00")

    response = staff_client.post("/api/orders", json={"customer": ALI, "items": [item]})

    assert response.status_code == 403


STAFF_ROUTES = re.compile(r"^/api/(orders|customers)(/|$)")
STAFF_READS = {("GET", "/api/services"), ("GET", "/api/services/{service_id}")}
OFF_LIMITS = [
    (method, path)
    for method, path in PROTECTED_ROUTES
    if not STAFF_ROUTES.match(path) and (method, path) not in STAFF_READS and path != "/api/auth/me"
]


def test_off_limits_list_is_not_empty() -> None:
    assert len(OFF_LIMITS) >= 10  # guards the test below against checking nothing


@pytest.mark.parametrize(("method", "path"), OFF_LIMITS, ids=lambda value: value)
def test_staff_are_refused_everything_else(
    staff_client: TestClient, method: str, path: str
) -> None:
    """Chats, analytics, bookings and settings are the owner's. Deny by default: a route
    added later is refused too unless it is put on the staff list on purpose."""
    url = re.sub(r"\{[^}]+\}", "1", path)

    response = staff_client.request(method, url, json={})

    assert response.status_code == 403, f"staff can call {method} {path}"


def test_staff_can_read_the_price_list(staff_client: TestClient, services: dict[str, int]) -> None:
    assert staff_client.get("/api/services").status_code == 200
    assert staff_client.post("/api/services", json={}).status_code == 403


# --- Switched off ----------------------------------------------------------------------------


def test_the_back_office_is_hidden_unless_switched_on(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ORDERS_ENABLED", "false")
    get_settings.cache_clear()

    assert client.get("/api/orders").status_code == 404
    assert client.get("/api/business").json()["orders"] is False
