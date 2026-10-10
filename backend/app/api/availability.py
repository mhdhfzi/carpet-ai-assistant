from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.db.models import BookingLocation
from app.schemas.booking import DayAvailability
from app.services import availability, catalog

router = APIRouter(prefix="/api/availability", tags=["availability"])


@router.get("", response_model=list[DayAvailability])
def get_availability(
    db: DbSession,
    service_ids: Annotated[list[int], Query(min_length=1)],
    location: BookingLocation = BookingLocation.CUSTOMER_HOME,
    date_from: date | None = None,
    days: Annotated[int, Query(ge=1, le=31)] = 7,
) -> list[DayAvailability]:
    """Free visit start times per open day. Defaults to the earliest bookable date."""
    services = catalog.get_bookable_services(db, set(service_ids))
    duration = availability.visit_duration(services.values())
    found = availability.find_available_slots(
        db, duration, location=location, date_from=date_from, days=days
    )
    return [DayAvailability(day=day, slots=slots) for day, slots in found]
