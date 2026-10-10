from fastapi import APIRouter, status

from app.api.deps import DbSession
from app.db.models import Service
from app.schemas.service import ServiceCreate, ServiceRead, ServiceUpdate
from app.services import catalog

router = APIRouter(prefix="/api/services", tags=["services"])


@router.get("", response_model=list[ServiceRead])
def list_services(db: DbSession, include_inactive: bool = False) -> list[Service]:
    return catalog.list_services(db, include_inactive=include_inactive)


@router.get("/{service_id}", response_model=ServiceRead)
def get_service(service_id: int, db: DbSession) -> Service:
    return catalog.get_service(db, service_id)


@router.post("", response_model=ServiceRead, status_code=status.HTTP_201_CREATED)
def create_service(data: ServiceCreate, db: DbSession) -> Service:
    return catalog.create_service(db, data)


@router.patch("/{service_id}", response_model=ServiceRead)
def update_service(service_id: int, data: ServiceUpdate, db: DbSession) -> Service:
    return catalog.update_service(db, service_id, data)


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_service(service_id: int, db: DbSession) -> None:
    """Deactivates the service (soft delete); existing bookings keep referring to it."""
    catalog.deactivate_service(db, service_id)
