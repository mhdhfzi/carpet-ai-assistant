"""The agent loop with a scripted fake model. Clock frozen at Saturday 10 Oct 2026, 10:00."""

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import agent
from app.ai.llm import ChatTurn, ModelTurn, ToolCall
from app.ai.prompts import HANDOFF_MESSAGE
from app.ai.tools import ToolContext
from app.db.models import (
    Booking,
    BookingStatus,
    Channel,
    Conversation,
    Message,
    MessageRole,
    Service,
)
from app.seed import seed_services
from tests.fakes import FakeChatModel, FakeEmbedder, tool_turn


@pytest.fixture
def ctx(db: Session) -> ToolContext:
    seed_services(db)
    conversation = Conversation(channel=Channel.WEB, external_id="agent-test")
    message = Message(conversation=conversation, role=MessageRole.CUSTOMER, content="Hi")
    db.add_all([conversation, message])
    db.flush()
    return ToolContext(db=db, conversation=conversation, customer_message_id=message.id)


def run(ctx: ToolContext, llm: FakeChatModel, text: str = "Hi") -> agent.AgentReply:
    return agent.run(ctx, FakeEmbedder(), llm, [ChatTurn("user", text)])


def service_id(db: Session, name: str) -> int:
    return db.scalar(select(Service.id).where(Service.name == name))


def test_plain_answer_needs_one_model_call(ctx: ToolContext) -> None:
    llm = FakeChatModel(ModelTurn("We're closed on Fridays."))

    reply = run(ctx, llm, "Are you open Friday?")

    assert reply.text == "We're closed on Fridays."
    assert len(llm.calls) == 1
    assert reply.tools_used == []


def test_model_gets_tools_prompt_and_todays_date(ctx: ToolContext) -> None:
    llm = FakeChatModel()

    run(ctx, llm)

    call = llm.calls[0]
    assert {t["name"] for t in call.tools} >= {
        "estimate_price",
        "prepare_booking",
        "create_booking",
    }
    assert "Call create_booking only after the customer replies" in call.system
    assert call.context == "[Context: it is now Saturday, 10 October 2026, 10:00 in Malaysia.]"


def test_tool_results_are_fed_back_until_the_model_answers(ctx: ToolContext) -> None:
    sofa = service_id(ctx.db, "Cucian Sofa")
    llm = FakeChatModel(
        tool_turn("estimate_price", items=[{"service_id": sofa, "quantity": 3}]),
        ModelTurn("Cleaning a 3-seater sofa is about RM180."),
    )

    reply = run(ctx, llm, "How much for a 3 seater sofa?")

    assert reply.text == "Cleaning a 3-seater sofa is about RM180."
    assert reply.tools_used == ["estimate_price"]
    assert reply.grounded  # backed by business data from a tool, even without citations
    turn, outcomes = llm.calls[1].exchanges[0]
    assert turn.tool_calls[0].name == "estimate_price"
    assert json.loads(outcomes[0].content)["total"] == "RM180.00"
    assert not outcomes[0].is_error


def test_several_tool_calls_in_one_turn_all_get_results(ctx: ToolContext) -> None:
    llm = FakeChatModel(
        ModelTurn(
            "",
            tool_calls=[
                ToolCall("a", "get_services", {}),
                ToolCall("b", "check_availability", {"service_ids": [1_000_000]}),
            ],
        ),
        ModelTurn("Here you go."),
    )

    run(ctx, llm)

    _, outcomes = llm.calls[1].exchanges[0]
    assert [(o.call_id, o.is_error) for o in outcomes] == [("a", False), ("b", True)]


def test_tool_errors_go_back_to_the_model(ctx: ToolContext) -> None:
    llm = FakeChatModel(tool_turn("no_such_tool"), ModelTurn("Sorry about that."))

    reply = run(ctx, llm)

    _, outcomes = llm.calls[1].exchanges[0]
    assert outcomes[0].is_error and "Unknown tool" in outcomes[0].content
    assert reply.tools_used == []
    assert not reply.grounded


def test_runaway_tool_loop_is_capped(ctx: ToolContext) -> None:
    llm = FakeChatModel(*[tool_turn("get_services") for _ in range(50)])

    reply = run(ctx, llm)

    assert len(llm.calls) == agent.MAX_TOOL_ROUNDS + 1
    assert reply.gave_up and reply.text == HANDOFF_MESSAGE


@pytest.mark.parametrize("turn", [ModelTurn("", refused=True), ModelTurn("")])
def test_refusal_or_empty_reply_falls_back_to_the_handoff_message(
    ctx: ToolContext, turn: ModelTurn
) -> None:
    reply = run(ctx, FakeChatModel(turn))

    assert reply.text == HANDOFF_MESSAGE
    assert reply.gave_up


# --- Full conversations through the API ------------------------------------------------------


def send(client: TestClient, message: str, session_id: str | None = None) -> dict[str, Any]:
    response = client.post("/api/chat", json={"session_id": session_id, "message": message})
    assert response.status_code == 200, response.text
    return response.json()


def booking_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Booking)) or 0


def test_booking_conversation_requires_the_customers_confirmation(
    client: TestClient, db: Session, fake_llm: FakeChatModel
) -> None:
    seed_services(db)
    details = {
        "customer_name": "Aminah",
        "phone": "012-345 6789",
        "address": "12 Jalan Mawar, Seremban",
        "visit_date": "2026-10-12",
        "start_time": "09:00",
        "items": [{"service_id": service_id(db, "Cucian Sofa"), "quantity": 3}],
    }
    # Turn 1: the model prepares the booking and (wrongly) tries to book straight away.
    fake_llm.script += [
        tool_turn("prepare_booking", **details),
        tool_turn("create_booking", call_id="call_2"),
        ModelTurn("Monday 12 Oct, 9:00-11:00, sofa 3 seats, about RM180. Shall I book it?"),
    ]

    first = send(client, "Book sofa cleaning Monday 9am. Aminah, 012-345 6789, 12 Jalan Mawar")

    refused = fake_llm.calls[2].exchanges[1][1][0]
    assert refused.is_error and "hasn't confirmed" in refused.content
    assert booking_count(db) == 0

    # Turn 2: the customer confirms, and now create_booking works.
    fake_llm.script += [
        tool_turn("create_booking", call_id="call_3"),
        ModelTurn("Done! Your booking is received; the owner will contact you to confirm."),
    ]

    second = send(client, "Yes, confirm", first["session_id"])

    assert second["reply"].startswith("Done!")
    booking = db.scalar(select(Booking))
    assert booking is not None
    assert booking.status is BookingStatus.PENDING
    assert booking.customer.phone == "+60123456789"
    conversation = db.scalar(
        select(Conversation).where(Conversation.external_id == first["session_id"])
    )
    assert conversation is not None
    assert booking.conversation_id == conversation.id  # for chat-to-booking analytics


def test_handoff_tool_stops_ai_replies(
    client: TestClient, db: Session, fake_llm: FakeChatModel
) -> None:
    fake_llm.script += [
        tool_turn("handoff_to_human", reason="Customer is unhappy with a previous job"),
        ModelTurn("I'm sorry about that. The owner will reply to you here soon."),
    ]

    first = send(client, "Your team ruined my carpet!!")
    second = send(client, "Hello??", first["session_id"])

    assert first["handed_off"] is True
    assert first["reply"].startswith("I'm sorry")
    assert second == {"session_id": first["session_id"], "reply": None, "handed_off": True}
    conversation = db.scalar(
        select(Conversation).where(Conversation.external_id == first["session_id"])
    )
    assert conversation is not None
    assert conversation.handoff_reason == "Customer is unhappy with a previous job"
