"""One codebase, several businesses: the demo defaults, and an answers-only deployment for a
real business that sends customers to WhatsApp to book."""

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import seed_demo
from app.ai import agent
from app.ai.chunking import BACKEND_DIR, KNOWLEDGE_DIR, knowledge_dir
from app.ai.llm import ChatTurn, ModelTurn
from app.ai.prompts import HANDOFF_MESSAGE, system_prompt
from app.ai.tools import ANSWER_TOOLS, ToolContext, run_tool
from app.core.config import Settings, get_settings
from app.db.models import Booking, Channel, Conversation, Message, MessageRole
from app.main import create_app
from app.seed import seed_services
from app.services.chat import DAILY_LIMIT_REPLY, daily_limit_reply
from tests.fakes import FakeChatModel, FakeEmbedder, tool_turn

CONTACT = "012-345 6789"
REAL = {
    "BUSINESS_NAME": "Cuci-Cuci Senawang",
    "BUSINESS_LOCATION": "Senawang, Negeri Sembilan, Malaysia",
    "DEMO_BUSINESS": "false",
    "BOOKINGS_ENABLED": "false",
    "CONTACT_WHATSAPP": CONTACT,
}


@pytest.fixture
def real_business(monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    for key, value in REAL.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
def ctx(db: Session) -> ToolContext:
    seed_services(db)
    conversation = Conversation(channel=Channel.WEB, external_id="config-test")
    message = Message(conversation=conversation, role=MessageRole.CUSTOMER, content="Hi")
    db.add_all([conversation, message])
    db.flush()
    return ToolContext(db=db, conversation=conversation, customer_message_id=message.id)


def run(ctx: ToolContext, llm: FakeChatModel) -> agent.AgentReply:
    return agent.run(ctx, FakeEmbedder(), llm, [ChatTurn("user", "Boleh tempah Sabtu ni?")])


# --- Settings --------------------------------------------------------------------------------


def test_answers_only_mode_requires_a_whatsapp_contact() -> None:
    with pytest.raises(ValidationError, match="CONTACT_WHATSAPP"):
        Settings(_env_file=None, bookings_enabled=False)


def test_knowledge_dir_defaults_to_the_demo_and_resolves_relative_paths() -> None:
    assert knowledge_dir(Settings(_env_file=None)) == KNOWLEDGE_DIR
    relative = Settings(_env_file=None, knowledge_dir="knowledge-real")
    assert knowledge_dir(relative) == BACKEND_DIR / "knowledge-real"
    absolute = Path("/srv/docs").resolve()
    assert knowledge_dir(Settings(_env_file=None, knowledge_dir=str(absolute))) == absolute


# --- Prompt ----------------------------------------------------------------------------------


def test_demo_prompt_takes_bookings_and_says_it_is_fictional() -> None:
    prompt = system_prompt(Settings(_env_file=None))

    assert "Kilau Carpet Care" in prompt
    assert "Call create_booking only after the customer replies" in prompt
    assert "fictional business" in prompt


def test_real_business_prompt_sends_bookings_to_whatsapp(real_business: Settings) -> None:
    prompt = system_prompt(real_business)

    assert "Cuci-Cuci Senawang" in prompt
    assert "Kilau" not in prompt
    assert "fictional" not in prompt
    assert f"WhatsApp the owner at {CONTACT}" in prompt
    for booking_tool in ("check_availability", "prepare_booking", "create_booking"):
        assert booking_tool not in prompt


# --- Agent -----------------------------------------------------------------------------------


def test_answers_only_agent_is_offered_no_booking_tools(
    ctx: ToolContext, real_business: Settings
) -> None:
    llm = FakeChatModel()

    run(ctx, llm)

    assert {t["name"] for t in llm.calls[0].tools} == set(ANSWER_TOOLS)
    assert "Cuci-Cuci Senawang" in llm.calls[0].system


def test_booking_tool_is_refused_even_if_the_model_calls_it(
    ctx: ToolContext, real_business: Settings, db: Session
) -> None:
    """Enforced in code, not only by which tools the model was shown."""
    llm = FakeChatModel(tool_turn("create_booking"), ModelTurn("Please WhatsApp us."))

    reply = run(ctx, llm)

    assert "create_booking" not in reply.tools_used
    tool_result = llm.calls[1].exchanges[0][1][0]
    assert tool_result.is_error and "Unknown tool" in tool_result.content
    assert db.scalar(select(func.count()).select_from(Booking)) == 0


def test_run_tool_without_a_restriction_still_runs_every_tool(ctx: ToolContext) -> None:
    assert not run_tool(ctx, "get_services", {}).is_error
    assert not run_tool(ctx, "get_services", {}, allowed=ANSWER_TOOLS).is_error
    assert run_tool(ctx, "check_availability", {}, allowed=ANSWER_TOOLS).is_error


def test_fallback_and_daily_limit_replies_point_to_whatsapp(
    ctx: ToolContext, real_business: Settings
) -> None:
    llm = FakeChatModel(ModelTurn("", refused=True))

    reply = run(ctx, llm)

    assert reply.gave_up and CONTACT in reply.text and reply.text != HANDOFF_MESSAGE
    assert CONTACT in daily_limit_reply() and "demo" not in daily_limit_reply()


def test_demo_keeps_its_own_fixed_replies() -> None:
    assert daily_limit_reply() == DAILY_LIMIT_REPLY


# --- Deployment surface ------------------------------------------------------------------


def test_business_endpoint_describes_the_demo(db: Session) -> None:
    body = TestClient(create_app()).get("/api/business").json()

    assert body == {"name": "Kilau Carpet Care", "demo": True, "bookings": True}


def test_real_business_endpoint_and_no_demo_landing_page(
    real_business: Settings, db: Session
) -> None:
    client = TestClient(create_app())

    assert client.get("/api/business").json() == {
        "name": "Cuci-Cuci Senawang",
        "demo": False,
        "bookings": False,
    }
    landing = client.get("/", follow_redirects=False)
    assert landing.status_code == 307 and landing.headers["location"] == "/admin.html"


def test_demo_seed_refuses_to_run_for_a_real_business(
    real_business: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """seed_demo --reset deletes every customer: it must never touch real data."""
    monkeypatch.setattr(sys, "argv", ["seed_demo", "--reset"])

    with pytest.raises(SystemExit, match="DEMO_BUSINESS is false"):
        seed_demo.main()
