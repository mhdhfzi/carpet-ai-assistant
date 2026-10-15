"""The chat hides itself when it can't answer: switched off, out of AI credit, or over the
daily cap. Clock frozen at Saturday 10 Oct 2026, 10:00 (Malaysia)."""

from datetime import timedelta

import anthropic
import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.llm import LLMCreditError, _out_of_credit
from app.core.config import get_settings
from app.db.models import AssistantPause
from app.services import assistant_status
from app.services.chat import UNAVAILABLE_REPLY
from tests.conftest import FROZEN_NOW
from tests.fakes import FakeChatModel


def status(client: TestClient) -> bool:
    return client.get("/api/chat/status").json()["available"]


def ask(client: TestClient, text: str = "Berapa harga cuci sofa?") -> str:
    return client.post("/api/chat", json={"message": text}).json()["reply"]


@pytest.fixture
def out_of_credit(fake_llm: FakeChatModel) -> list[int]:
    """Make the fake model fail like an account with no credit; returns a call counter."""
    calls: list[int] = []

    def respond(**_: object) -> None:
        calls.append(1)
        raise LLMCreditError("Claude API account is out of credit")

    fake_llm.respond = respond  # type: ignore[method-assign]
    return calls


def test_chat_is_available_normally(anon_client: TestClient) -> None:
    assert status(anon_client) is True


def test_owner_can_switch_the_chat_off(
    anon_client: TestClient, fake_llm: FakeChatModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHAT_ENABLED", "false")
    get_settings.cache_clear()

    assert status(anon_client) is False
    assert ask(anon_client) == UNAVAILABLE_REPLY  # a page opened earlier still gets an answer
    assert fake_llm.calls == []


def test_running_out_of_credit_pauses_the_chat(
    anon_client: TestClient, out_of_credit: list[int], db: Session
) -> None:
    assert ask(anon_client) == UNAVAILABLE_REPLY  # not a 503: the customer gets a reply
    assert status(anon_client) is False
    assert assistant_status.paused_until(db) == FROZEN_NOW + timedelta(minutes=30)

    ask(anon_client)  # while paused, the AI isn't called again
    assert len(out_of_credit) == 1


def test_each_pause_in_a_row_lasts_longer_up_to_six_hours(db: Session) -> None:
    lengths = []
    for _ in range(6):
        until = assistant_status.pause(db, "out of credit")
        lengths.append(until - FROZEN_NOW)

    assert lengths[:4] == [timedelta(minutes=m) for m in (30, 60, 120, 240)]
    assert lengths[4:] == [timedelta(hours=6)] * 2


def test_the_chat_returns_by_itself_once_the_pause_ends(
    anon_client: TestClient, fake_llm: FakeChatModel, db: Session
) -> None:
    db.add(AssistantPause(id=1, paused_until=FROZEN_NOW - timedelta(minutes=1), consecutive=3))
    db.flush()

    assert status(anon_client) is True
    assert ask(anon_client) == "Hello from the fake model."
    assert db.get(AssistantPause, 1).consecutive == 0  # topped up: next pause starts short


def test_resume_ends_a_pause_straight_away(anon_client: TestClient, db: Session) -> None:
    assistant_status.pause(db, "out of credit")

    assistant_status.resume(db)

    assert status(anon_client) is True


def test_chat_hides_once_the_daily_cap_is_reached(
    anon_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AI_DAILY_REPLY_LIMIT", "1")
    get_settings.cache_clear()

    ask(anon_client)

    assert status(anon_client) is False


def _api_error(status_code: int, error_type: str, message: str) -> anthropic.APIStatusError:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(status_code, request=request)
    body = {"type": "error", "error": {"type": error_type, "message": message}}
    return anthropic.APIStatusError(message, response=response, body=body)


@pytest.mark.parametrize(
    ("error", "is_credit"),
    [
        (_api_error(402, "billing_error", "Billing problem"), True),
        (_api_error(400, "invalid_request_error", "Your credit balance is too low"), True),
        (_api_error(529, "overloaded_error", "Overloaded"), False),  # temporary: keep the chat
        (_api_error(401, "authentication_error", "invalid x-api-key"), False),
    ],
    ids=["billing_error", "old-credit-message", "overloaded", "bad-key"],
)
def test_only_billing_errors_count_as_out_of_credit(
    error: anthropic.APIStatusError, is_credit: bool
) -> None:
    assert _out_of_credit(error) is is_credit
