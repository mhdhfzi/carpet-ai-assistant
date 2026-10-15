"""The assistant's tools, called directly (no LLM). Clock frozen at Saturday 10 Oct 2026."""

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.embeddings import EmbeddingError
from app.ai.ingest import ingest
from app.ai.tools import TOOLS, ToolContext, run_tool, tool_definitions
from app.db.models import Booking, Channel, Conversation, Message, MessageRole, Service
from app.seed import seed_services
from tests.fakes import FakeEmbedder
from tests.test_ingest import write_doc


@pytest.fixture
def conversation(db: Session) -> Conversation:
    seed_services(db)
    conversation = Conversation(channel=Channel.WEB, external_id="test-session")
    db.add(conversation)
    db.flush()
    return conversation


def customer_says(db: Session, conversation: Conversation, text: str) -> ToolContext:
    """Store a customer message and return the tool context for the turn answering it."""
    message = Message(conversation=conversation, role=MessageRole.CUSTOMER, content=text)
    db.add(message)
    db.flush()
    return ToolContext(db=db, conversation=conversation, customer_message_id=message.id)


def service_id(db: Session, name: str) -> int:
    return db.scalar(select(Service.id).where(Service.name == name))


def call(ctx: ToolContext, name: str, **tool_input: Any) -> dict[str, Any]:
    result = run_tool(ctx, name, tool_input)
    assert not result.is_error, result.content
    return json.loads(result.content)


def call_error(ctx: ToolContext, name: str, **tool_input: Any) -> str:
    result = run_tool(ctx, name, tool_input)
    assert result.is_error, result.content
    return json.loads(result.content)["error"]


def booking_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Booking)) or 0


def booking_input(db: Session, **overrides: Any) -> dict[str, Any]:
    return {
        "customer_name": "Aminah",
        "phone": "012-345 6789",
        "area": "Seremban",
        "visit_date": "2026-10-12",  # Monday
        "start_time": "09:00",
        "items": [{"service_id": service_id(db, "Cucian Sofa"), "quantity": 3}],
        **overrides,
    }


# --- Definitions -----------------------------------------------------------------------------


def _objects(schema: dict[str, Any]):
    if schema.get("type") == "object":
        yield schema
    for value in schema.values():
        if isinstance(value, dict):
            yield from _objects(value)


def test_every_tool_schema_forbids_unknown_fields() -> None:
    definitions = tool_definitions()

    assert [d["name"] for d in definitions] == list(TOOLS)
    for definition in definitions:
        assert definition["description"]
        for obj in _objects(definition["input_schema"]):
            assert obj.get("additionalProperties") is False, definition["name"]


# --- Read-only tools -------------------------------------------------------------------------


def test_get_services_lists_prices(db: Session, conversation: Conversation) -> None:
    services = call(customer_says(db, conversation, "Hi"), "get_services")["services"]

    by_name = {s["name"]: s for s in services}
    assert by_name["Karpet Shaggy"]["price"] == "RM2.00 per square foot"
    assert by_name["Karpet Handmade"]["price"] == "RM2.50 to RM4.00 per square foot"


def test_estimate_price_mixes_fixed_and_ranged_lines(
    db: Session, conversation: Conversation
) -> None:
    ctx = customer_says(db, conversation, "How much?")

    result = call(
        ctx,
        "estimate_price",
        items=[
            {"service_id": service_id(db, "Karpet Handmade"), "quantity": 100},
            {"service_id": service_id(db, "Cucian Sofa"), "quantity": 3},
        ],
    )

    assert [line["estimate"] for line in result["lines"]] == ["RM250.00 - RM400.00", "RM180.00"]
    assert result["total"] == "RM430.00 - RM580.00"
    assert "measured" in result["note"]


def test_business_rule_errors_go_back_to_the_model(db: Session, conversation: Conversation) -> None:
    ctx = customer_says(db, conversation, "2.5 seats please")

    error = call_error(
        ctx,
        "estimate_price",
        items=[{"service_id": service_id(db, "Cucian Sofa"), "quantity": 2.5}],
    )

    assert "whole number" in error


def test_check_availability_returns_compact_time_ranges(
    db: Session, conversation: Conversation
) -> None:
    ctx = customer_says(db, conversation, "When are you free?")

    sofa = call(ctx, "check_availability", service_ids=[service_id(db, "Cucian Sofa")], days=7)
    carpet = call(ctx, "check_availability", service_ids=[service_id(db, "Karpet Biasa")], days=1)

    assert sofa["visit_length_minutes"] == 120
    assert sofa["days"][0] == {
        "date": "2026-10-12",
        "weekday": "Monday",
        "free_start_times": ["09:00-15:30"],
    }
    assert "Friday" not in [d["weekday"] for d in sofa["days"]]
    assert carpet["days"][0]["free_start_times"] == ["09:00-17:00"]  # 30-minute collection


@pytest.mark.parametrize(
    ("name", "tool_input", "message"),
    [
        ("no_such_tool", {}, "Unknown tool"),
        ("estimate_price", {"items": []}, "Invalid input"),
        ("get_services", {"surprise": 1}, "Invalid input"),
        ("handoff_to_human", {}, "Invalid input"),
    ],
)
def test_bad_tool_calls_return_errors(
    db: Session, conversation: Conversation, name: str, tool_input: dict, message: str
) -> None:
    ctx = customer_says(db, conversation, "Hi")

    assert message in call_error(ctx, name, **tool_input)


# --- Booking with confirmation ---------------------------------------------------------------


def test_prepare_booking_returns_a_summary_and_creates_nothing(
    db: Session, conversation: Conversation
) -> None:
    ctx = customer_says(db, conversation, "Book sofa cleaning Monday 9am, Aminah 012-3456789")

    result = call(ctx, "prepare_booking", **booking_input(db))

    assert result["status"] == "awaiting_customer_confirmation"
    summary = result["summary"]
    assert summary["when"] == "Monday, 12 October 2026, 09:00-11:00"
    assert summary["phone"] == "+60123456789"
    assert summary["estimated_total"] == "RM180.00"
    assert booking_count(db) == 0
    assert conversation.booking_draft is not None


def test_create_booking_in_the_same_turn_is_refused(
    db: Session, conversation: Conversation
) -> None:
    ctx = customer_says(db, conversation, "Book sofa cleaning Monday 9am")
    call(ctx, "prepare_booking", **booking_input(db))

    error = call_error(ctx, "create_booking")

    assert "hasn't confirmed" in error
    assert booking_count(db) == 0


def test_create_booking_after_the_customer_replies(db: Session, conversation: Conversation) -> None:
    call(
        customer_says(db, conversation, "Book sofa Monday 9am"),
        "prepare_booking",
        **booking_input(db),
    )

    result = call(customer_says(db, conversation, "Yes, confirm"), "create_booking")

    booking = db.get(Booking, result["booking_id"])
    assert booking is not None
    assert result["status"] == "pending"
    assert booking.conversation_id == conversation.id
    assert booking.estimated_price == 180
    assert conversation.customer is not None and conversation.customer.phone == "+60123456789"
    assert conversation.booking_draft is None


def test_changed_details_need_a_new_confirmation(db: Session, conversation: Conversation) -> None:
    call(customer_says(db, conversation, "Book Monday 9am"), "prepare_booking", **booking_input(db))
    ctx = customer_says(db, conversation, "Actually make it 2pm")
    call(ctx, "prepare_booking", **booking_input(db, start_time="14:00"))

    assert "hasn't confirmed" in call_error(ctx, "create_booking")

    result = call(customer_says(db, conversation, "Yes"), "create_booking")
    booking = db.get(Booking, result["booking_id"])
    assert booking is not None and booking.scheduled_start.hour == 6  # 14:00 MYT = 06:00 UTC


def test_create_booking_without_a_draft_is_refused(db: Session, conversation: Conversation) -> None:
    assert "prepare_booking first" in call_error(
        customer_says(db, conversation, "Yes"), "create_booking"
    )


def test_unavailable_slot_is_rejected_at_prepare_time(
    db: Session, conversation: Conversation
) -> None:
    ctx = customer_says(db, conversation, "Friday 10am please")

    error = call_error(ctx, "prepare_booking", **booking_input(db, visit_date="2026-10-16"))

    assert "closed on Fridays" in error
    assert conversation.booking_draft is None


@pytest.mark.parametrize("start_time", ["25:00", "9am"])
def test_invalid_times_are_rejected(
    db: Session, conversation: Conversation, start_time: str
) -> None:
    ctx = customer_says(db, conversation, "Book")

    call_error(ctx, "prepare_booking", **booking_input(db, start_time=start_time))


def test_handoff_marks_the_conversation(db: Session, conversation: Conversation) -> None:
    ctx = customer_says(db, conversation, "I want to talk to a real person!")

    call(ctx, "handoff_to_human", reason="Customer asked for a person")

    assert conversation.handed_off is True
    assert conversation.handoff_reason == "Customer asked for a person"


def test_search_knowledge_finds_what_the_message_documents_missed(
    db: Session, conversation: Conversation, tmp_path: Path
) -> None:
    write_doc(tmp_path, "hours.md", {"Opening hours": "We are closed on Friday (Jumaat)."})
    embedder = FakeEmbedder()
    ingest(db, embedder, tmp_path)
    ctx = customer_says(db, conversation, "Hari Jumaat buka tak?")
    ctx.embedder = embedder

    results = call(ctx, "search_knowledge", query="open on Friday Jumaat")["results"]

    assert results[0]["source"].endswith("Opening hours")
    assert "closed on Friday" in results[0]["text"]


def test_search_knowledge_without_an_embedder_is_a_clean_error(
    db: Session, conversation: Conversation
) -> None:
    error = call_error(customer_says(db, conversation, "Hi"), "search_knowledge", query="hours")

    assert "not available" in error


def test_a_failed_search_is_an_error_result_not_a_failed_reply(
    db: Session, conversation: Conversation
) -> None:
    class RateLimitedEmbedder(FakeEmbedder):
        def embed_query(self, text: str) -> list[float]:
            raise EmbeddingError("Voyage AI returned 429")

    ctx = customer_says(db, conversation, "Hi")
    ctx.embedder = RateLimitedEmbedder()

    assert "not available" in call_error(ctx, "search_knowledge", query="hours")
