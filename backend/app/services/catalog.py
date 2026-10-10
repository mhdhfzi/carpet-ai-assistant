"""Business logic for the service catalogue (the services the business offers)."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Service
from app.schemas.service import ServiceCreate, ServiceUpdate
from app.services.errors import BusinessRuleError, ConflictError, NotFoundError


def list_services(db: Session, *, include_inactive: bool = False) -> list[Service]:
    stmt = select(Service).order_by(Service.name)
    if not include_inactive:
        stmt = stmt.where(Service.is_active)
    return list(db.scalars(stmt))


def get_service(db: Session, service_id: int) -> Service:
    service = db.get(Service, service_id)
    if service is None:
        raise NotFoundError(f"Service {service_id} not found")
    return service


def create_service(db: Session, data: ServiceCreate) -> Service:
    _check_price_range(data.unit_price, data.unit_price_max)
    service = Service(**data.model_dump())
    db.add(service)
    _commit_or_conflict(db, data.name)
    db.refresh(service)
    return service


def update_service(db: Session, service_id: int, data: ServiceUpdate) -> Service:
    service = get_service(db, service_id)
    changes = data.model_dump(exclude_unset=True)
    # Validate the merged result, e.g. a PATCH that only lowers unit_price_max.
    _check_price_range(
        changes.get("unit_price", service.unit_price),
        changes.get("unit_price_max", service.unit_price_max),
    )
    for field, value in changes.items():
        setattr(service, field, value)
    _commit_or_conflict(db, service.name)
    db.refresh(service)
    return service


def deactivate_service(db: Session, service_id: int) -> None:
    """Soft delete: past bookings still reference the service, so the row must stay."""
    service = get_service(db, service_id)
    service.is_active = False
    db.commit()


def _check_price_range(unit_price: Decimal, unit_price_max: Decimal | None) -> None:
    if unit_price_max is not None and unit_price_max < unit_price:
        raise BusinessRuleError("unit_price_max must be greater than or equal to unit_price")


def _commit_or_conflict(db: Session, name: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "uq_services_name" in str(exc.orig):
            raise ConflictError(f"A service named '{name}' already exists") from exc
        raise
