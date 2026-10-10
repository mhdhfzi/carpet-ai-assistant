"""Business logic for bookings: creation (with server-side pricing) and status changes."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Booking, BookingItem, BookingStatus, Customer, Service
from app.schemas.booking import BookingCreate, BookingUpdate, CustomerIn
from app.services import pricing
from app.services.errors import BusinessRuleError, InvalidStatusTransitionError, NotFoundError

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


def create_booking(
    db: Session, data: BookingCreate, *, conversation_id: int | None = None
) -> Booking:
    """Create a pending booking. Prices come from the catalogue, never from the caller."""
    services = _load_bookable_services(db, {item.service_id for item in data.items})

    items = []
    for item in data.items:
        service = services[item.service_id]
        items.append(
            BookingItem(
                service=service,
                quantity=item.quantity,
                unit_price=service.unit_price,
                line_total=pricing.line_total(service, item.quantity),
            )
        )

    booking = Booking(
        customer=_find_or_create_customer(db, data.customer),
        conversation_id=conversation_id,
        scheduled_start=data.scheduled_start,
        scheduled_end=data.scheduled_end,
        estimated_price=sum((i.line_total for i in items), start=Decimal("0")),
        notes=data.notes,
        items=items,
    )
    db.add(booking)
    db.commit()
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


def _load_bookable_services(db: Session, service_ids: set[int]) -> dict[int, Service]:
    services = {s.id: s for s in db.scalars(select(Service).where(Service.id.in_(service_ids)))}
    missing = service_ids - services.keys()
    if missing:
        raise BusinessRuleError(f"Unknown service id(s): {sorted(missing)}")
    inactive = sorted(s.name for s in services.values() if not s.is_active)
    if inactive:
        raise BusinessRuleError(f"Service(s) no longer offered: {', '.join(inactive)}")
    return services


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
