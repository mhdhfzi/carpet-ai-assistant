"""Production hardening: rate limits, the daily AI cap, request IDs, logging and errors."""

import json
import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import JsonFormatter, RequestIdFilter, request_id_var
from app.core.rate_limit import RateLimiter, RateLimitExceeded
from app.main import create_app
from app.services.chat import DAILY_LIMIT_REPLY
from tests.conftest import OWNER_EMAIL
from tests.fakes import FakeChatModel

# --- Rate limiter (unit) ---------------------------------------------------------------------


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_limiter_allows_up_to_the_limit_then_reports_when_to_retry() -> None:
    clock = FakeClock()
    limiter = RateLimiter(limit=3, window=60, clock=clock)

    for _ in range(3):
        limiter.check("1.2.3.4")
    clock.now += 10
    with pytest.raises(RateLimitExceeded) as exc:
        limiter.check("1.2.3.4")

    assert exc.value.retry_after == 50  # the oldest hit leaves the window in 50 s


def test_limiter_window_slides_and_clients_are_separate() -> None:
    clock = FakeClock()
    limiter = RateLimiter(limit=1, window=60, clock=clock)

    limiter.check("1.1.1.1")
    limiter.check("2.2.2.2")  # another client has its own budget
    clock.now += 60
    limiter.check("1.1.1.1")  # the first hit has left the window


def test_limiter_forgets_idle_clients_to_bound_memory() -> None:
    clock = FakeClock()
    limiter = RateLimiter(limit=5, window=60, clock=clock)
    limiter.MAX_TRACKED_CLIENTS = 3
    for i in range(4):
        limiter.check(f"10.0.0.{i}")
    clock.now += 61

    limiter.check("10.0.0.99")  # over the bound: idle clients are swept

    assert set(limiter._hits) == {"10.0.0.99"}


# --- Rate limits on the API ------------------------------------------------------------------


def test_chat_is_rate_limited_per_client(anon_client: TestClient) -> None:
    for _ in range(20):
        assert anon_client.post("/api/chat", json={"message": "Hi"}).status_code == 200

    response = anon_client.post("/api/chat", json={"message": "Hi"})

    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0
    assert "Too many requests" in response.json()["detail"]


def test_login_is_rate_limited_even_with_the_right_password(anon_client: TestClient, owner) -> None:
    for _ in range(10):
        anon_client.post("/api/auth/login", json={"email": OWNER_EMAIL, "password": "guess"})

    response = anon_client.post(
        "/api/auth/login", json={"email": OWNER_EMAIL, "password": "correct horse battery staple"}
    )

    assert response.status_code == 429


# --- Daily AI cap ----------------------------------------------------------------------------


def test_daily_ai_limit_stops_calling_the_model(
    anon_client: TestClient, fake_llm: FakeChatModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AI_DAILY_REPLY_LIMIT", "2")
    get_settings.cache_clear()

    replies = [
        anon_client.post("/api/chat", json={"message": f"Q{i}"}).json()["reply"] for i in range(3)
    ]

    assert replies[:2] == ["Hello from the fake model."] * 2
    assert replies[2] == DAILY_LIMIT_REPLY
    assert len(fake_llm.calls) == 2  # the third question never reached the AI
    # The fixed reply doesn't count as AI output, so it doesn't push the counter further.
    anon_client.post("/api/chat", json={"message": "Q3"})
    assert len(fake_llm.calls) == 2


def test_daily_limit_of_zero_means_unlimited(
    anon_client: TestClient, fake_llm: FakeChatModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AI_DAILY_REPLY_LIMIT", "0")
    get_settings.cache_clear()

    for i in range(3):
        anon_client.post("/api/chat", json={"message": f"Q{i}"})

    assert len(fake_llm.calls) == 3


# --- Request IDs, headers and logs -----------------------------------------------------------


def test_every_response_has_a_request_id_and_security_headers(anon_client: TestClient) -> None:
    response = anon_client.get("/health")

    assert len(response.headers["x-request-id"]) == 32
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_a_well_formed_incoming_request_id_is_kept(anon_client: TestClient) -> None:
    kept = anon_client.get("/health", headers={"X-Request-ID": "trace-12345678"})
    replaced = anon_client.get("/health", headers={"X-Request-ID": "bad id\nINJECTED log line"})

    assert kept.headers["x-request-id"] == "trace-12345678"
    assert "INJECTED" not in replaced.headers["x-request-id"]


def test_json_logs_carry_severity_request_id_and_extra_fields() -> None:
    record = logging.makeLogRecord(
        {
            "name": "app.request",
            "levelname": "INFO",
            "levelno": 20,
            "msg": "GET %s",
            "args": ("/x",),
        }
    )
    record.status = 200
    token = request_id_var.set("req-abc12345")
    try:
        RequestIdFilter().filter(record)
        entry = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)

    assert entry["severity"] == "INFO"
    assert entry["message"] == "GET /x"
    assert entry["request_id"] == "req-abc12345"
    assert entry["status"] == 200


# --- Unexpected errors -----------------------------------------------------------------------


def test_unexpected_errors_return_a_safe_500_with_a_request_id(db: Session) -> None:
    app = create_app()

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret internal details")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/boom")

    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "Internal server error"
    assert body["request_id"] == response.headers["x-request-id"]  # quote it to find the log
    assert "secret" not in response.text
