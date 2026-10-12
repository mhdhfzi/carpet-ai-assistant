"""Business logic for bookings: creation (with server-side pricing) and status changes."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.models import Booking, BookingItem, BookingStatus, Customer, Service
from app.schemas.booking import BookingCreate, BookingUpdate, CustomerIn
from app.services import availability, catalog, pricing
from app.services.errors import ConflictError, InvalidStatusTransitionError, NotFoundError

# Which statuses a booking may move to from each status. Done and cancelled are final.
ALLOWED_TRANSITIONS: dict[BookingStatus, set[BookingStatus]] = {
    BookingStatus.PENDING: {BookingStatus.CONFIRMED, BookingStatus.CANCELLED},
    BookingStatus.CONFIRMED: {BookingStatus.DONE, BookingStatus.CANCELLED},
    BookingStatus.DONE: set(),
    BookingStatus.CANCELLED: set(),
}

# Eager-load everything a BookingRead needs in a fixed number of queries (avoids N+1).
_FULL_BOOKING = (
    selectinload(Booking.customer),
    selectinload(Booking.items).selectinload(BookingItem.service),
)


def list_bookings(
    db: Session,
    *,
    status: BookingStatus | None = None,
    start_from: datetime | None = None,
    start_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Booking]:
    stmt = select(Booking).options(*_FULL_BOOKING).order_by(Booking.scheduled_start, Booking.id)
    if status is not None:
        stmt = stmt.where(Booking.status == status)
    if start_from is not None:
        stmt = stmt.where(Booking.scheduled_start >= start_from)
    if start_to is not None:
        stmt = stmt.where(Booking.scheduled_start < start_to)
    return list(db.scalars(stmt.limit(limit).offset(offset)))


def get_booking(db: Session, booking_id: int) -> Booking:
    booking = db.get(Booking, booking_id, options=_FULL_BOOKING)
    if booking is None:
        raise NotFoundError(f"Booking {booking_id} not found")
    return booking


@dataclass(frozen=True)
class QuoteLine:
    service: Service
    quantity: Decimal
    unit_price: pricing.PriceRange
    line_total: pricing.PriceRange


@dataclass(frozen=True)
class BookingQuote:
    """Everything a booking would contain, computed without saving anything."""

    scheduled_start: datetime
    scheduled_end: datetime
    lines: list[QuoteLine]
    total: pricing.PriceRange


def quote_booking(db: Session, data: BookingCreate) -> BookingQuote:
    """Validate a booking request, check the slot is free, and price it. Saves nothing.

    Used both to create bookings and to show the customer a summary to confirm first.
    """
    services = catalog.get_bookable_services(db, {item.service_id for item in data.items})
    duration = availability.visit_duration(services.values())
    availability.ensure_slot_available(db, data.scheduled_start, duration, location=data.location)

    lines = []
    for item in data.items:
        service = services[item.service_id]
        lines.append(
            QuoteLine(
                service=service,
                quantity=item.quantity,
                unit_price=pricing.unit_price_range(service),
                line_total=pricing.estimate_line(service, item.quantity),
            )
        )
    return BookingQuote(
        scheduled_start=data.scheduled_start,
        scheduled_end=data.scheduled_start + duration,
        lines=lines,
        total=pricing.estimate_total(line.line_total for line in lines),
    )


def create_booking(
    db: Session, data: BookingCreate, *, conversation_id: int | None = None
) -> Booking:
    """Create a pending booking for the owner to confirm with the customer.

    Prices and the visit's end time come from the catalogue, never from the caller.
    """
    quote = quote_booking(db, data)
    booking = Booking(
        customer=_find_or_create_customer(db, data.customer),
        conversation_id=conversation_id,
        scheduled_start=quote.scheduled_start,
        scheduled_end=quote.scheduled_end,
        location=data.location,
        estimated_price=quote.total.low,
        estimated_price_max=quote.total.high,
        notes=data.notes,
        items=[
            BookingItem(
                service=line.service,
                quantity=line.quantity,
                unit_price=line.unit_price.low,
                unit_price_max=line.unit_price.high,
                line_total=line.line_total.low,
                line_total_max=line.line_total.high,
            )
            for line in quote.lines
        ],
    )
    db.add(booking)
    try:
        db.commit()
    except IntegrityError as exc:
        # The check above passed, but another booking took the slot in the meantime;
        # the database's exclusion constraint is the final guard against double-booking.
        db.rollback()
        if "ex_bookings_no_overlap" in str(exc.orig):
            raise ConflictError("That time was just booked; please choose another.") from exc
        raise
    return get_booking(db, booking.id)


def update_booking(db: Session, booking_id: int, data: BookingUpdate) -> Booking:
    booking = get_booking(db, booking_id)
    changes = data.model_dump(exclude_unset=True)

    new_status = changes.pop("status", None)
    if new_status is not None and new_status != booking.status:
        if new_status not in ALLOWED_TRANSITIONS[booking.status]:
            raise InvalidStatusTransitionError(
                f"Cannot change booking from '{booking.status}' to '{new_status}'"
            )
        booking.status = new_status

    for field, value in changes.items():
        setattr(booking, field, value)

    db.commit()
    return get_booking(db, booking_id)


def _find_or_create_customer(db: Session, data: CustomerIn) -> Customer:
    """Customers are identified by phone number (their WhatsApp ID).

    An existing customer's stored details are not overwritten from a booking request, so a
    request can't tamper with someone else's record just by knowing their number.
    """
    customer = db.scalar(select(Customer).where(Customer.phone == data.phone))
    if customer is None:
        customer = Customer(**data.model_dump())
        db.add(customer)
    return customer
