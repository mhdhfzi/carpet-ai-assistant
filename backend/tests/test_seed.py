from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Service
from app.seed import SERVICES, seed_services


def test_seed_creates_all_services(db: Session) -> None:
    created, updated = seed_services(db)

    assert (created, updated) == (len(SERVICES), 0)
    handmade = db.scalar(select(Service).where(Service.name == "Karpet Handmade"))
    assert handmade is not None
    assert (handmade.unit_price, handmade.unit_price_max) == (Decimal("2.50"), Decimal("4.00"))


def test_seed_is_idempotent_and_restores_prices(db: Session) -> None:
    seed_services(db)
    biasa = db.scalar(select(Service).where(Service.name == "Karpet Biasa"))
    assert biasa is not None
    biasa.unit_price = Decimal("9.99")
    db.commit()

    created, updated = seed_services(db)

    assert (created, updated) == (0, len(SERVICES))
    assert db.scalar(select(func.count()).select_from(Service)) == len(SERVICES)
    db.refresh(biasa)
    assert biasa.unit_price == Decimal("1.80")


def test_seed_names_are_unique() -> None:
    names = [s["name"] for s in SERVICES]
    assert len(names) == len(set(names))


def test_car_prices_with_a_range_are_set_after_seeing_the_car(db: Session) -> None:
    seed_services(db)
    van = db.scalar(select(Service).where(Service.name == "Cucian Seat Van / Bas"))
    assert van is not None
    assert (van.unit_price, van.unit_price_max, van.on_site) == (
        Decimal("25.00"),
        Decimal("35.00"),
        True,
    )


def test_seed_switches_off_retired_services_but_keeps_them(db: Session) -> None:
    old = Service(
        name="Cucian Seat Kereta SUV",
        description="",
        pricing_unit="per_item",
        unit_price=Decimal("150"),
        on_site=True,
    )
    db.add(old)
    db.commit()

    seed_services(db)

    db.refresh(old)
    assert old.is_active is False  # hidden from the price list; old orders still show it
