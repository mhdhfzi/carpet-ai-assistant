"""Load the business's real price list into the database.

Run with:  python -m app.seed

Idempotent: services are matched by name, so re-running updates prices instead of
creating duplicates. The database (not the RAG documents) is the source of truth for
prices; the AI reads them through tools.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PricingUnit, Service
from app.db.session import SessionLocal

D = Decimal

SERVICES: list[dict] = [
    # Carpets: priced per square foot. The size is recorded on site and the final
    # price confirmed to the customer afterwards.
    {
        "name": "Karpet Biasa",
        "description": "Standard carpet cleaning, priced per square foot.",
        "pricing_unit": PricingUnit.PER_SQFT,
        "unit_price": D("1.80"),
    },
    {
        "name": "Karpet Shaggy",
        "description": "Shaggy (long-pile) carpet cleaning, priced per square foot.",
        "pricing_unit": PricingUnit.PER_SQFT,
        "unit_price": D("2.00"),
    },
    {
        "name": "Karpet Velvet",
        "description": "Velvet carpet cleaning, priced per square foot.",
        "pricing_unit": PricingUnit.PER_SQFT,
        "unit_price": D("0.90"),
    },
    {
        "name": "Karpet Premium Velvet",
        "description": "Premium velvet carpet cleaning, priced per square foot.",
        "pricing_unit": PricingUnit.PER_SQFT,
        "unit_price": D("1.00"),
    },
    {
        "name": "Karpet Span",
        "description": "Span carpet cleaning, priced per square foot.",
        "pricing_unit": PricingUnit.PER_SQFT,
        "unit_price": D("0.90"),
    },
    {
        "name": "Karpet Tatami",
        "description": "Tatami carpet cleaning, priced per square foot.",
        "pricing_unit": PricingUnit.PER_SQFT,
        "unit_price": D("0.90"),
    },
    {
        "name": "Karpet Handmade",
        "description": (
            "Handmade carpet cleaning, RM2.50 to RM4.00 per square foot depending on the "
            "carpet's material. The owner confirms the final price after inspecting it."
        ),
        "pricing_unit": PricingUnit.PER_SQFT,
        "unit_price": D("2.50"),
        "unit_price_max": D("4.00"),
    },
    # Furniture: priced per item.
    {
        "name": "Cucian Sofa",
        "description": "Sofa cleaning, priced per seat.",
        "pricing_unit": PricingUnit.PER_ITEM,
        "unit_price": D("60.00"),
    },
    {
        "name": "Cucian Tilam Single",
        "description": "Single mattress cleaning, priced per mattress.",
        "pricing_unit": PricingUnit.PER_ITEM,
        "unit_price": D("100.00"),
    },
    {
        "name": "Cucian Tilam Queen",
        "description": "Queen mattress cleaning, priced per mattress.",
        "pricing_unit": PricingUnit.PER_ITEM,
        "unit_price": D("140.00"),
    },
    {
        "name": "Cucian Tilam King",
        "description": "King mattress cleaning, priced per mattress.",
        "pricing_unit": PricingUnit.PER_ITEM,
        "unit_price": D("160.00"),
    },
    # TODO: Cucian Kereta (car cleaning) by vehicle size (sedan, MPV, ...): waiting for prices.
]


def seed_services(db: Session) -> tuple[int, int]:
    """Insert or update every service in SERVICES. Returns (created, updated)."""
    existing = {s.name: s for s in db.scalars(select(Service))}
    created = updated = 0
    for data in SERVICES:
        values = {"unit_price_max": None, "minimum_charge": D("0"), **data}
        service = existing.get(data["name"])
        if service is None:
            db.add(Service(**values))
            created += 1
        else:
            for field, value in values.items():
                setattr(service, field, value)
            updated += 1
    db.commit()
    return created, updated


def main() -> None:
    with SessionLocal() as db:
        created, updated = seed_services(db)
    print(f"Services seeded: {created} created, {updated} updated.")


if __name__ == "__main__":
    main()
