"""Owner login: tokens, password checks, and which routes need a login."""

import re
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Owner
from app.main import create_app
from app.services.errors import ConflictError
from app.services.owners import create_owner
from tests.conftest import OWNER_EMAIL, OWNER_PASSWORD, TEST_JWT_SECRET

# Routes anyone may call. Every other route must refuse requests without a valid token.
PUBLIC_ROUTES = {
    ("GET", "/health"),
    ("POST", "/api/auth/login"),
    ("GET", "/api/business"),  # name and mode, so the dashboard can brand itself
    ("POST", "/api/chat"),
    ("GET", "/api/chat/status"),  # whether the widget should show itself
    ("GET", "/api/chat/{session_id}"),
    ("GET", "/api/services"),
    ("GET", "/api/services/{service_id}"),
    ("GET", "/api/availability"),
    ("GET", "/api/whatsapp/webhook"),  # protected by Meta's verify token
    ("POST", "/api/whatsapp/webhook"),  # protected by Meta's request signature
}


def login(client: TestClient, email: str = OWNER_EMAIL, password: str = OWNER_PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def me(client: TestClient, token: str):
    return client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})


def claims_for(owner: Owner) -> dict:
    return {"sub": str(owner.id), "exp": datetime.now(UTC) + timedelta(hours=1), "type": "access"}


def token_with(**claims) -> str:
    now = datetime.now(UTC)
    base = {"sub": "1", "iat": now, "exp": now + timedelta(hours=1), "type": "access"}
    return jwt.encode({**base, **claims}, TEST_JWT_SECRET, algorithm="HS256")


# --- Logging in ------------------------------------------------------------------------------


def test_login_returns_a_token_that_identifies_the_owner(
    anon_client: TestClient, owner: Owner
) -> None:
    response = login(anon_client)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 8 * 60 * 60
    assert me(anon_client, body["access_token"]).json() == {
        "id": owner.id,
        "email": OWNER_EMAIL,
        "name": "Test Owner",
        "role": "owner",
    }


def test_email_is_case_insensitive(anon_client: TestClient, owner: Owner) -> None:
    assert login(anon_client, email="  Owner@Example.COM ").status_code == 200


def test_wrong_password_and_unknown_email_get_the_same_answer(
    anon_client: TestClient, owner: Owner
) -> None:
    wrong_password = login(anon_client, password="not the password")
    unknown_email = login(anon_client, email="nobody@example.com")

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert (
        wrong_password.json() == unknown_email.json() == {"detail": "Incorrect email or password"}
    )
    assert wrong_password.headers["www-authenticate"] == "Bearer"


def test_password_is_stored_hashed(owner: Owner) -> None:
    assert OWNER_PASSWORD not in owner.password_hash
    assert owner.password_hash.startswith("$argon2id$")


def test_login_is_refused_when_no_secret_is_configured(
    anon_client: TestClient, owner: Owner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JWT_SECRET", "")
    get_settings.cache_clear()

    response = login(anon_client)

    assert response.status_code == 503
    assert "JWT_SECRET" not in response.text


# --- Rejected tokens -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "make_token",
    [
        pytest.param(lambda owner: "not-a-jwt", id="garbage"),
        pytest.param(
            lambda owner: token_with(
                sub=str(owner.id), exp=datetime.now(UTC) - timedelta(minutes=1)
            ),
            id="expired",
        ),
        pytest.param(
            lambda owner: jwt.encode(
                {
                    "sub": str(owner.id),
                    "exp": datetime.now(UTC) + timedelta(hours=1),
                    "type": "access",
                },
                "some-other-secret-that-is-long-enough-x",
                algorithm="HS256",
            ),
            id="wrong-secret",
        ),
        pytest.param(
            lambda owner: jwt.encode(
                {
                    "sub": str(owner.id),
                    "exp": datetime.now(UTC) + timedelta(hours=1),
                    "type": "access",
                },
                None,
                algorithm="none",
            ),
            id="alg-none",
        ),
        pytest.param(lambda owner: token_with(sub=str(owner.id), type="refresh"), id="wrong-type"),
        pytest.param(lambda owner: token_with(sub=str(owner.id + 999)), id="unknown-owner"),
    ],
)
def test_invalid_tokens_are_rejected(anon_client: TestClient, owner: Owner, make_token) -> None:
    assert me(anon_client, make_token(owner)).status_code == 401


def test_tampered_token_is_rejected(anon_client: TestClient, owner: Owner) -> None:
    token = login(anon_client).json()["access_token"]
    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload}.{signature[:-2]}xx"

    assert me(anon_client, tampered).status_code == 401


def test_token_stops_working_when_the_account_is_deleted(
    anon_client: TestClient, db: Session, owner: Owner
) -> None:
    token = login(anon_client).json()["access_token"]
    db.delete(owner)
    db.flush()

    assert me(anon_client, token).status_code == 401


# --- Which routes need a login ---------------------------------------------------------------


def all_routes() -> list[tuple[str, str]]:
    """Every API route, read from the OpenAPI schema (public and stable, unlike FastAPI's
    internal route objects, which changed shape in recent versions)."""
    paths = create_app().openapi()["paths"]
    return sorted((method.upper(), path) for path, ops in paths.items() for method in ops)


PROTECTED_ROUTES = [r for r in all_routes() if r not in PUBLIC_ROUTES]


def test_route_lists_are_up_to_date() -> None:
    """Fails if a public route is renamed or removed, or if route discovery breaks and the
    protection test below would silently check nothing."""
    assert set(all_routes()) >= PUBLIC_ROUTES
    assert len(PROTECTED_ROUTES) >= 10


@pytest.mark.parametrize(
    ("method", "path"),
    PROTECTED_ROUTES,
    ids=lambda value: value,
)
def test_owner_routes_require_a_login(anon_client: TestClient, method: str, path: str) -> None:
    """Every route not listed as public refuses anonymous requests, including routes added
    later: forgetting to protect a new owner endpoint fails this test."""
    url = re.sub(r"\{[^}]+\}", "1", path)

    response = anon_client.request(method, url, json={})

    assert response.status_code == 401, f"{method} {path} is reachable without logging in"


def test_customer_routes_work_without_a_login(anon_client: TestClient) -> None:
    assert anon_client.get("/api/services").status_code == 200
    assert anon_client.post("/api/chat", json={"message": "Hi"}).status_code == 200


# --- Creating owners -------------------------------------------------------------------------


def test_create_owner_validates_and_rejects_duplicates(db: Session) -> None:
    owner = create_owner(db, " Boss@Example.com ", "Boss", "a-long-enough-password")
    assert owner.email == "boss@example.com"

    with pytest.raises(ConflictError):
        create_owner(db, "boss@example.com", "Boss again", "a-long-enough-password")
    with pytest.raises(ValueError, match="at least"):
        create_owner(db, "short@example.com", "Short", "short")
    with pytest.raises(ValueError, match="valid email"):
        create_owner(db, "not-an-email", "No", "a-long-enough-password")
