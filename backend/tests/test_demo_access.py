"""The public demo: a read-only login, and a reset that clears what visitors typed."""

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.models import Conversation, Customer, Owner, OwnerRole
from app.seed import seed_services
from app.seed_demo import (
    DEMO_OWNER_EMAIL,
    DEMO_OWNER_PASSWORD,
    SCENARIOS,
    ensure_demo_owner,
    reset_customer_data,
    seed_demo,
)
from tests.test_auth import PROTECTED_ROUTES

WRITE_ROUTES = [(m, p) for m, p in PROTECTED_ROUTES if m not in {"GET", "HEAD", "OPTIONS"}]


@pytest.fixture
def demo_client(anon_client: TestClient, db: Session) -> TestClient:
    demo = ensure_demo_owner(db)
    anon_client.headers["Authorization"] = f"Bearer {create_access_token(demo.id)[0]}"
    return anon_client


def test_demo_login_uses_the_published_password_and_reports_its_role(
    anon_client: TestClient, db: Session
) -> None:
    ensure_demo_owner(db)

    token = anon_client.post(
        "/api/auth/login", json={"email": DEMO_OWNER_EMAIL, "password": DEMO_OWNER_PASSWORD}
    ).json()["access_token"]
    me = anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()

    assert me["role"] == "demo"


def test_demo_account_can_read_the_dashboard(demo_client: TestClient, db: Session) -> None:
    seed_services(db)
    seed_demo(db)

    assert demo_client.get("/api/bookings").status_code == 200
    assert demo_client.get("/api/analytics").status_code == 200


def test_write_route_list_is_not_empty() -> None:
    assert len(WRITE_ROUTES) >= 5  # guards the test below against checking nothing


@pytest.mark.parametrize(("method", "path"), WRITE_ROUTES, ids=lambda value: value)
def test_demo_account_cannot_change_anything(
    demo_client: TestClient, method: str, path: str
) -> None:
    """Every owner route that writes refuses the demo account, including routes added
    later: the check is by HTTP method, not a list of routes to remember."""
    url = re.sub(r"\{[^}]+\}", "1", path)

    response = demo_client.request(method, url, json={})

    assert response.status_code == 403, f"demo account can call {method} {path}"
    assert response.json() == {"detail": "The demo account is read-only"}


def test_a_real_owner_can_still_write(client: TestClient) -> None:
    response = client.put("/api/closed-dates/2026-12-25", json={"reason": "Christmas"})

    assert response.status_code == 200


def test_ensure_demo_owner_is_idempotent_and_repairs_the_account(db: Session) -> None:
    first = ensure_demo_owner(db)
    first.role = OwnerRole.OWNER  # e.g. someone promoted it by mistake
    first.password_hash = "changed"
    db.flush()

    again = ensure_demo_owner(db)

    assert again.id == first.id
    assert again.role is OwnerRole.DEMO
    assert again.password_hash.startswith("$argon2id$")
    assert db.scalar(select(func.count()).select_from(Owner)) == 1


def test_reset_removes_visitor_data_and_keeps_owners(db: Session, owner: Owner) -> None:
    seed_services(db)
    visitor = Customer(name="A Recruiter", phone="+60111111111")
    db.add(visitor)
    db.flush()

    reset_customer_data(db)
    seed_demo(db)

    assert db.get(Customer, visitor.id) is None
    assert db.scalar(select(func.count()).select_from(Conversation)) == len(SCENARIOS)
    assert db.get(Owner, owner.id) is not None
