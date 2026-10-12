from typing import Annotated

from fastapi import APIRouter, Query
from fastapi import status as http_status
from pydantic import AwareDatetime

from app.api.deps import DbSession, RequireOwner
from app.db.models import Booking, BookingStatus
from app.schemas.booking import BookingCreate, BookingRead, BookingUpdate
from app.services import bookings

# Owner only: bookings hold customers' names, phone numbers and addresses.
router = APIRouter(prefix="/api/bookings", tags=["bookings"], dependencies=[RequireOwner])


@router.get("", response_model=list[BookingRead])
def list_bookings(
    db: DbSession,
    status: BookingStatus | None = None,
    start_from: AwareDatetime | None = None,
    start_to: AwareDatetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Booking]:
    return bookings.list_bookings(
        db, status=status, start_from=start_from, start_to=start_to, limit=limit, offset=offset
    )


@router.get("/{booking_id}", response_model=BookingRead)
def get_booking(booking_id: int, db: DbSession) -> Booking:
    return bookings.get_booking(db, booking_id)


@router.post("", response_model=BookingRead, status_code=http_status.HTTP_201_CREATED)
def create_booking(data: BookingCreate, db: DbSession) -> Booking:
    return bookings.create_booking(db, data)


@router.patch("/{booking_id}", response_model=BookingRead)
def update_booking(booking_id: int, data: BookingUpdate, db: DbSession) -> Booking:
    """Update status or notes. There is no DELETE: cancel instead, so history is kept."""
    return bookings.update_booking(db, booking_id, data)
