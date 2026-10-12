"""Analytics on hand-built data. The clock is frozen at Saturday 10 Oct 2026, 10:00 MYT."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import (
    Booking,
    BookingStatus,
    Channel,
    Conversation,
    Customer,
    Message,
    MessageRole,
    UnansweredQuestion,
    UnansweredReason,
)
from tests.conftest import FROZEN_NOW


def days_ago(days: float) -> datetime:
    return FROZEN_NOW - timedelta(days=days)


def chat(
    db: Session, channel: Channel, created: datetime, handed_off: bool = False
) -> Conversation:
    conversation = Conversation(
        channel=channel,
        external_id=f"c{created.timestamp()}{channel}",
        handed_off=handed_off,
        created_at=created,
    )
    db.add(conversation)
    db.flush()
    return conversation


def booking(
    db: Session,
    start: datetime,
    *,
    created: datetime,
    conversation: Conversation | None = None,
    status: BookingStatus = BookingStatus.DONE,
) -> Booking:
    customer = Customer(name="C", phone=f"+601{int(start.timestamp()) % 10**8:08d}")
    row = Booking(
        customer=customer,
        conversation=conversation,
        scheduled_start=start,
        scheduled_end=start + timedelta(hours=2),
        status=status,
        estimated_price=Decimal("100"),
        estimated_price_max=Decimal("100"),
        created_at=created,
    )
    db.add(row)
    db.flush()
    return row


def cited_reply(
    db: Session, conversation: Conversation, created: datetime, *headings: str
) -> Message:
    message = Message(
        conversation=conversation,
        role=MessageRole.ASSISTANT,
        content="...",
        sources=[
            {"source": "faq.md", "title": "FAQ", "heading": h, "cited_text": "x"} for h in headings
        ],
        grounded=True,
        created_at=created,
    )
    db.add(message)
    db.flush()
    return message


def summary(client: TestClient, days: int = 30) -> dict:
    response = client.get("/api/analytics", params={"days": days})
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_period(client: TestClient) -> None:
    body = summary(client)

    assert body["conversations"] == body["bookings"] == body["handed_off"] == 0
    assert body["conversion_rate"] is None  # no chats: a rate would be meaningless
    assert [c["rate"] for c in body["conversion"]] == [None, None]
    assert [d["weekday"] for d in body["busy_days"]] == [
        "Mon",
        "Tue",
        "Wed",
        "Thu",
        "Fri",
        "Sat",
        "Sun",
    ]
    assert body["top_topics"] == []
    assert body["open_unanswered"] == {"no_answer": 0, "handed_off": 0, "gave_up": 0}


def test_period_starts_at_malaysian_midnight(client: TestClient, db: Session) -> None:
    # days=1 means "today": from 00:00 MYT on Sat 10 Oct (= 16:00 UTC on Fri 9 Oct).
    chat(db, Channel.WEB, datetime(2026, 10, 9, 16, 30, tzinfo=UTC))  # 00:30 MYT today
    chat(db, Channel.WEB, datetime(2026, 10, 9, 15, 30, tzinfo=UTC))  # 23:30 MYT yesterday

    assert summary(client, days=1)["conversations"] == 1
    assert summary(client, days=2)["conversations"] == 2


def test_conversion_per_channel(client: TestClient, db: Session) -> None:
    web_booked = chat(db, Channel.WEB, days_ago(3))
    chat(db, Channel.WEB, days_ago(2))
    chat(db, Channel.WEB, days_ago(1), handed_off=True)
    whatsapp_booked = chat(db, Channel.WHATSAPP, days_ago(5))
    old = chat(db, Channel.WHATSAPP, days_ago(40))  # outside the 30-day period
    booking(db, days_ago(-3), created=days_ago(3), conversation=web_booked)
    booking(
        db, days_ago(-4), created=days_ago(3), conversation=web_booked
    )  # 2nd booking, same chat
    booking(db, days_ago(-6), created=days_ago(5), conversation=whatsapp_booked)
    booking(db, days_ago(30), created=days_ago(39), conversation=old)

    body = summary(client)

    assert body["conversations"] == 4
    assert body["handed_off"] == 1
    assert body["bookings"] == 3
    by_channel = {c["channel"]: c for c in body["conversion"]}
    assert by_channel["web"] == {
        "channel": "web",
        "conversations": 3,
        "converted": 1,
        "rate": 0.3333,
    }
    assert by_channel["whatsapp"] == {
        "channel": "whatsapp",
        "conversations": 1,
        "converted": 1,
        "rate": 1.0,
    }
    assert body["conversion_rate"] == 0.5  # 2 of 4 chats led to a booking


def test_busy_days_use_malaysian_weekdays_and_skip_cancellations(
    client: TestClient, db: Session
) -> None:
    # Mon 12 Oct 17:30 UTC is already Tuesday 01:30 in Malaysia.
    booking(db, datetime(2026, 10, 12, 17, 30, tzinfo=UTC), created=days_ago(1))
    booking(db, datetime(2026, 10, 12, 2, 0, tzinfo=UTC), created=days_ago(1))  # Mon 10:00 MYT
    booking(
        db,
        datetime(2026, 10, 13, 2, 0, tzinfo=UTC),
        created=days_ago(1),
        status=BookingStatus.CANCELLED,
    )

    days = {d["weekday"]: d["bookings"] for d in summary(client)["busy_days"]}

    assert days["Mon"] == 1
    assert days["Tue"] == 1  # the cancelled Tuesday booking isn't counted


def test_top_topics_count_each_cited_section_once_per_reply(
    client: TestClient, db: Session
) -> None:
    conversation = chat(db, Channel.WEB, days_ago(2))
    cited_reply(db, conversation, days_ago(2), "Opening hours", "Opening hours", "Pickup")
    cited_reply(db, conversation, days_ago(1), "Opening hours")
    cited_reply(db, conversation, days_ago(45), "Old topic")  # outside the period

    topics = summary(client)["top_topics"]

    assert topics == [
        {"title": "FAQ", "heading": "Opening hours", "count": 2},
        {"title": "FAQ", "heading": "Pickup", "count": 1},
    ]


def test_open_unanswered_counts_ignore_resolved(client: TestClient, db: Session) -> None:
    conversation = chat(db, Channel.WEB, days_ago(1))
    message = Message(conversation=conversation, role=MessageRole.CUSTOMER, content="Curtains?")
    db.add(message)
    db.flush()
    for reason, resolved in [
        (UnansweredReason.NO_ANSWER, False),
        (UnansweredReason.NO_ANSWER, True),
        (UnansweredReason.HANDED_OFF, False),
    ]:
        db.add(
            UnansweredQuestion(
                conversation=conversation,
                message_id=message.id,
                reason=reason,
                question="Curtains?",
                resolved=resolved,
            )
        )
    db.flush()

    assert summary(client)["open_unanswered"] == {"no_answer": 1, "handed_off": 1, "gave_up": 0}


@pytest.mark.parametrize("days", [0, 366])
def test_period_is_validated(client: TestClient, days: int) -> None:
    assert client.get("/api/analytics", params={"days": days}).status_code == 422
