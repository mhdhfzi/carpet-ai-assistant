from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    Booking,
    BookingItem,
    BookingStatus,
    Channel,
    Conversation,
    Customer,
    Message,
    MessageRole,
    PricingUnit,
    Service,
)

START = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)


def make_customer(phone: str = "+60123456789") -> Customer:
    return Customer(name="Aminah", phone=phone, area="Seremban")


def make_service() -> Service:
    return Service(
        name="Carpet shampoo",
        pricing_unit=PricingUnit.PER_SQFT,
        unit_price=Decimal("1.20"),
        minimum_charge=Decimal("80.00"),
    )


def test_booking_with_items_round_trip(db: Session) -> None:
    customer, service = make_customer(), make_service()
    booking = Booking(
        customer=customer,
        scheduled_start=START,
        scheduled_end=START + timedelta(hours=2),
        estimated_price=Decimal("120.00"),
        items=[
            BookingItem(
                service=service,
                quantity=Decimal("100"),
                unit_price=Decimal("1.20"),
                line_total=Decimal("120.00"),
            )
        ],
    )
    db.add(booking)
    db.commit()
    db.expire_all()

    loaded = db.get(Booking, booking.id)
    assert loaded is not None
    assert loaded.status is BookingStatus.PENDING
    assert loaded.estimated_price == Decimal("120.00")
    assert loaded.customer.phone == "+60123456789"
    assert [item.service.name for item in loaded.items] == ["Carpet shampoo"]
    assert loaded.created_at is not None


def test_customer_phone_is_unique(db: Session) -> None:
    db.add(make_customer())
    db.flush()
    db.add(make_customer())

    with pytest.raises(IntegrityError, match="uq_customers_phone"):
        db.flush()


def test_booking_must_end_after_it_starts(db: Session) -> None:
    db.add(
        Booking(
            customer=make_customer(),
            scheduled_start=START,
            scheduled_end=START,
            estimated_price=Decimal("100.00"),
        )
    )

    with pytest.raises(IntegrityError, match="ck_bookings_end_after_start"):
        db.flush()


def test_database_rejects_unknown_booking_status(db: Session) -> None:
    """The CHECK constraint protects the data even if something bypasses the ORM."""
    customer = make_customer()
    db.add(customer)
    db.flush()

    with pytest.raises(IntegrityError, match="ck_bookings_booking_status"):
        db.execute(
            text(
                "INSERT INTO bookings (customer_id, scheduled_start, scheduled_end, status,"
                " estimated_price) VALUES (:cid, :start, :end, 'bogus', 100)"
            ),
            {"cid": customer.id, "start": START, "end": START + timedelta(hours=1)},
        )


def test_deleting_conversation_deletes_its_messages(db: Session) -> None:
    conversation = Conversation(
        channel=Channel.WHATSAPP,
        external_id="+60123456789",
        messages=[
            Message(role=MessageRole.CUSTOMER, content="Berapa harga cuci karpet?"),
            Message(role=MessageRole.ASSISTANT, content="Carpet shampoo is RM1.20 per sqft."),
        ],
    )
    db.add(conversation)
    db.flush()

    db.delete(conversation)
    db.flush()

    assert db.scalar(select(func.count()).select_from(Message)) == 0


def test_cannot_delete_customer_with_bookings(db: Session) -> None:
    customer = make_customer()
    db.add(
        Booking(
            customer=customer,
            scheduled_start=START,
            scheduled_end=START + timedelta(hours=1),
            estimated_price=Decimal("100.00"),
        )
    )
    db.flush()

    with pytest.raises(IntegrityError, match="fk_bookings_customer_id_customers"):
        db.execute(text("DELETE FROM customers WHERE id = :id"), {"id": customer.id})
