"""Which business this deployment serves. Public, so the dashboard can show the right name
(and, on the demo only, the demo login) before anyone signs in."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.business import BusinessInfo

router = APIRouter(prefix="/api/business", tags=["meta"])


@router.get("", response_model=BusinessInfo)
def business() -> BusinessInfo:
    settings = get_settings()
    return BusinessInfo(
        name=settings.business_name,
        demo=settings.demo_business,
        bookings=settings.bookings_enabled,
        orders=settings.orders_enabled,
    )
