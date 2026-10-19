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
    assert order["payments"][0] | {"id": 0} == {
        "id": 0,
        "amount": "50.00",
        "method": "cash",
        "paid_on": TODAY.isoformat(),
        "note": "Deposit",
        "received_by": "Test Owner",
        "voided": False,
        "void_reason": None,
    }
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

    change = client.patch(f"/api/orders/{order['id']}", json={"return_method": "pickup"})
    payment = client.post(
        f"/api/orders/{order['id']}/payments", json={"amount": "10.00", "method": "cash"}
    )

    assert change.status_code == payment.status_code == 422


# --- Each carpet on its own ------------------------------------------------------------------


def two_carpets(client: TestClient, services: dict[str, int]) -> dict:
    return client.post(
        "/api/orders",
        json={
            "customer": ALI,
            "items": [
                carpet(services, "Karpet Biasa", "8", "10"),
                carpet(services, "Karpet Shaggy", "5", "8"),
            ],
        },
    ).json()


def move(client: TestClient, order: dict, position: int, status: str):
    item_id = order["items"][position - 1]["id"]
    return client.patch(f"/api/orders/{order['id']}/items/{item_id}", json={"status": status})


def test_each_carpet_is_washed_on_its_own_and_the_order_waits_for_the_last(
    client: TestClient, services: dict[str, int]
) -> None:
    order = two_carpets(client, services)

    one_washed = move(client, order, 1, "washed").json()

    assert [i["status"] for i in one_washed["items"]] == ["washed", "received"]
    assert one_washed["status"] == "received"  # still on the "belum dicuci" list
    assert (one_washed["items_washed"], one_washed["items_ready"]) == (1, 0)
    assert one_washed["events"][-1]["item_tag"] == "1-1"
    assert one_washed["items"][0]["ready_from"] == "2026-10-15"

    both_washed = move(client, order, 2, "washed").json()

    assert both_washed["status"] == "washed"
    assert both_washed["washed_on"] == TODAY.isoformat()


def test_the_order_is_ready_only_when_every_carpet_is_dry(
    staff_client: TestClient, services: dict[str, int]
) -> None:
    order = two_carpets(staff_client, services)
    staff_client.patch(f"/api/orders/{order['id']}", json={"status": "washed"})

    one_dry = move(staff_client, order, 1, "ready").json()
    too_early = staff_client.patch(f"/api/orders/{order['id']}", json={"status": "completed"})
    all_dry = move(staff_client, order, 2, "ready").json()

    assert one_dry["status"] == "washed" and one_dry["items_ready"] == 1
    assert too_early.status_code == 409  # handed back only when every carpet is dry
    assert all_dry["status"] == "ready"
    assert all_dry["ready_from"] is None  # nothing left drying


def test_washing_the_whole_order_moves_every_carpet(
    client: TestClient, services: dict[str, int]
) -> None:
    order = two_carpets(client, services)
    move(client, order, 1, "washed")
    move(client, order, 1, "ready")

    washed = client.patch(f"/api/orders/{order['id']}", json={"status": "washed"}).json()

    assert [i["status"] for i in washed["items"]] == ["ready", "washed"]  # ahead stays ahead
    assert washed["status"] == "washed"


def test_staff_move_a_carpet_one_step_and_the_owner_corrects(
    client: TestClient, staff_client: TestClient, services: dict[str, int]
) -> None:
    order = two_carpets(client, services)

    skipped = move(staff_client, order, 1, "ready")
    move(client, order, 1, "washed")
    back = move(client, order, 1, "received").json()

    assert skipped.status_code == 409
    assert back["items"][0]["status"] == "received"
    assert back["items"][0]["washed_on"] is None


def test_editing_items_keeps_each_carpets_progress(
    client: TestClient, services: dict[str, int]
) -> None:
    order = two_carpets(client, services)
    move(client, order, 1, "washed")

    edited = client.patch(
        f"/api/orders/{order['id']}",
        json={
            "items": [
                carpet(services, "Karpet Biasa", "8", "10"),
                carpet(services, "Karpet Shaggy", "5", "8"),
                counted(services, "Cucian Sofa", 2),
            ]
        },
    ).json()

    assert [i["status"] for i in edited["items"]] == ["washed", "received", "received"]


def test_a_finished_order_s_carpets_cannot_move(
    client: TestClient, services: dict[str, int]
) -> None:
    order = two_carpets(client, services)
    client.patch(f"/api/orders/{order['id']}", json={"status": "completed"})

    assert move(client, order, 1, "received").status_code == 422


# --- Washing and packing forms --------------------------------------------------------------


def velvet_order(client: TestClient, services: dict[str, int]) -> dict:
    response = client.post(
        "/api/orders",
        json={
            "customer": ALI,
            "items": [
                carpet(services, "Karpet Velvet", "5", "8"),
                carpet(services, "Karpet Biasa", "8", "10"),
            ],
        },
    )
    return response.json()


def pack(client: TestClient, order: dict, position: int, fold: str | None = None):
    item_id = order["items"][position - 1]["id"]
    return client.patch(
        f"/api/orders/{order['id']}/items/{item_id}", json={"status": "ready", "fold": fold}
    )


def test_washing_and_packing_record_the_day_and_who_did_it(
    staff_client: TestClient, services: dict[str, int]
) -> None:
    order = two_carpets(staff_client, services)

    washed = move(staff_client, order, 1, "washed").json()["items"][0]
    packed = move(staff_client, order, 1, "ready").json()["items"][0]

    assert (washed["washed_on"], washed["washed_by"]) == (TODAY.isoformat(), "Worker")
    assert (packed["ready_on"], packed["packed_by"]) == (TODAY.isoformat(), "Worker")


def test_a_velvet_carpet_is_packed_rolled_or_folded(
    staff_client: TestClient, services: dict[str, int]
) -> None:
    order = velvet_order(staff_client, services)
    staff_client.patch(f"/api/orders/{order['id']}", json={"status": "washed"})

    unsaid = pack(staff_client, order, 1)
    rolled = pack(staff_client, order, 1, "rolled").json()
    other = pack(staff_client, order, 2, "folded").json()

    assert unsaid.status_code == 422
    assert "1-1" in unsaid.json()["detail"]
    assert rolled["items"][0]["fold"] == "rolled"
    assert rolled["items"][0]["service"]["needs_fold"] is True
    assert other["items"][1]["fold"] is None  # only velvet is rolled or folded


def test_the_whole_order_cannot_be_packed_without_choosing_for_velvet(
    client: TestClient, services: dict[str, int]
) -> None:
    order = velvet_order(client, services)
    client.patch(f"/api/orders/{order['id']}", json={"status": "washed"})

    response = client.patch(f"/api/orders/{order['id']}", json={"status": "ready"})

    assert response.status_code == 422
    assert client.get(f"/api/orders/{order['id']}").json()["status"] == "washed"


def test_going_back_clears_the_packing_record(client: TestClient, services: dict[str, int]) -> None:
    order = velvet_order(client, services)
    move(client, order, 1, "washed")
    pack(client, order, 1, "folded")

    back = move(client, order, 1, "washed").json()["items"][0]

    assert (back["status"], back["ready_on"], back["packed_by"], back["fold"]) == (
        "washed",
        None,
        None,
        None,
    )
    assert back["washed_on"] == TODAY.isoformat()  # the wash still happened


def test_the_washing_and_packing_lists(staff_client: TestClient, services: dict[str, int]) -> None:
    first = two_carpets(staff_client, services)
    second = new_order(staff_client, services)
    move(staff_client, first, 1, "washed")

    to_wash = staff_client.get("/api/work/items", params={"status": "received"}).json()
    to_pack = staff_client.get("/api/work/items", params={"status": "washed"}).json()

    assert [i["tag"] for i in to_wash] == ["1-2", "2-1", "2-2"]
    assert to_wash[0]["customer_name"] == "Ali"
    assert to_wash[1]["order_id"] == second["id"]
    assert [i["tag"] for i in to_pack] == ["1-1"]
    assert to_pack[0]["ready_from"] == "2026-10-15"  # 5 days after washing


def test_a_cancelled_order_is_not_on_the_washing_list(
    client: TestClient, services: dict[str, int]
) -> None:
    order = two_carpets(client, services)
    client.patch(f"/api/orders/{order['id']}", json={"status": "cancelled"})

    assert client.get("/api/work/items", params={"status": "received"}).json() == []


def test_the_day_s_forms_list_what_was_washed_and_packed(
    staff_client: TestClient, services: dict[str, int]
) -> None:
    order = two_carpets(staff_client, services)
    move(staff_client, order, 1, "washed")
    move(staff_client, order, 2, "washed")
    move(staff_client, order, 1, "ready")

    today = staff_client.get("/api/work/log").json()
    other_day = staff_client.get("/api/work/log", params={"day": "2026-10-09"}).json()

    assert today["day"] == TODAY.isoformat()
    assert [(i["tag"], i["washed_by"]) for i in today["washed"]] == [
        ("1-1", "Worker"),
        ("1-2", "Worker"),
    ]
    assert [(i["tag"], i["packed_by"]) for i in today["packed"]] == [("1-1", "Worker")]
    assert other_day["washed"] == other_day["packed"] == []


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


# --- Payments and receipts -------------------------------------------------------------------


def pay(client: TestClient, order: dict, amount: str, method: str = "cash"):
    return client.post(
        f"/api/orders/{order['id']}/payments", json={"amount": amount, "method": method}
    )


def test_paying_the_balance_at_pickup(client: TestClient, services: dict[str, int]) -> None:
    order = new_order(client, services, deposit="50.00", deposit_method="transfer")

    paid = pay(client, order, "274.00", "duitnow").json()

    assert (paid["paid"], paid["balance"]) == ("324.00", "0.00")
    assert [(p["amount"], p["method"]) for p in paid["payments"]] == [
        ("50.00", "transfer"),
        ("274.00", "duitnow"),
    ]


def test_a_payment_cannot_exceed_the_balance(client: TestClient, services: dict[str, int]) -> None:
    order = new_order(client, services, deposit="300.00")

    response = pay(client, order, "30.00")

    assert response.status_code == 422
    assert "balance of RM24.00" in response.json()["detail"]


def test_the_owner_voids_a_wrong_payment_and_it_stays_on_record(
    client: TestClient, services: dict[str, int]
) -> None:
    order = new_order(client, services)
    wrong = pay(client, order, "100.00").json()["payments"][0]

    voided = client.post(
        f"/api/orders/{order['id']}/payments/{wrong['id']}/void",
        json={"reason": "salah masuk"},
    ).json()

    assert voided["balance"] == "324.00"
    assert voided["payments"][0]["voided"] is True
    assert voided["payments"][0]["void_reason"] == "salah masuk"


def test_staff_record_payments_but_cannot_void_them(
    staff_client: TestClient, services: dict[str, int]
) -> None:
    order = new_order(staff_client, services)
    payment = pay(staff_client, order, "100.00").json()["payments"][0]

    response = staff_client.post(
        f"/api/orders/{order['id']}/payments/{payment['id']}/void", json={"reason": "salah"}
    )

    assert payment["received_by"] == "Worker"
    assert response.status_code == 403


def test_the_customer_table_shows_what_each_customer_still_owes(
    client: TestClient, services: dict[str, int]
) -> None:
    first = new_order(client, services, deposit="24.00")  # owes 300
    second = new_order(client, services)
    pay(client, second, "324.00")  # settled

    row = client.get("/api/customers").json()[0]

    assert first["customer"]["id"] == row["id"]
    assert (row["total_value"], row["unpaid"]) == ("648.00", "300.00")


def test_a_receipt_has_the_business_details_and_the_order(
    client: TestClient, services: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BUSINESS_NAME", "Cuci-Cuci Senawang")
    monkeypatch.setenv("BUSINESS_REG_NO", "201903262495 (NS0229212-P)")
    monkeypatch.setenv("PAYMENT_DETAILS", "Maybank 1234")
    get_settings.cache_clear()
    order = new_order(client, services)

    receipt = client.get(f"/api/orders/{order['id']}/receipt").json()

    assert receipt["business"]["name"] == "Cuci-Cuci Senawang"
    assert receipt["business"]["reg_no"] == "201903262495 (NS0229212-P)"
    assert receipt["business"]["payment_details"] == "Maybank 1234"
    assert receipt["order"]["number"] == order["number"]
    assert receipt["issued_on"] == TODAY.isoformat()


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
STAFF_READS = {
    ("GET", "/api/services"),
    ("GET", "/api/services/{service_id}"),
    ("GET", "/api/work/items"),
    ("GET", "/api/work/log"),
}
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
