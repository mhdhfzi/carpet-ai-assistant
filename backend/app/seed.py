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

CARPET_PROCESS = (
    "We collect the carpet from your home (or you can drop it off at our shop), clean it at "
    "our shop and return it in 5-7 days. The size is measured and the final price confirmed "
    "after collection."
)
ON_SITE_PROCESS = "Cleaned at your home (about 2 hours) or you can bring it to our shop."


def carpet(
    name: str, kind: str, price: str, price_max: str | None = None, *, fold: bool = False
) -> dict:
    priced = f"Priced per square foot. {CARPET_PROCESS}"
    if price_max:
        priced = (
            f"RM{price} to RM{price_max} per square foot depending on the carpet's material; "
            f"the owner confirms the price after inspecting it. {CARPET_PROCESS}"
        )
    return {
        "name": name,
        "description": f"{kind} cleaning. {priced}",
        "pricing_unit": PricingUnit.PER_SQFT,
        "unit_price": D(price),
        "unit_price_max": D(price_max) if price_max else None,
        "visit_minutes": 30,  # the visit is only to collect the carpet
        "needs_fold": fold,  # velvet: packed rolled (gulung) or folded (lipat)
    }


def on_site(name: str, kind: str, per: str, price: str) -> dict:
    return {
        "name": name,
        "description": f"{kind} cleaning, priced per {per}. {ON_SITE_PROCESS}",
        "pricing_unit": PricingUnit.PER_ITEM,
        "unit_price": D(price),
        "visit_minutes": 120,
        "on_site": True,  # done at the customer's home in one visit
    }


def car_seats(size: str, price: str) -> dict:
    return {
        "name": f"Cucian Seat Kereta {size}",
        "description": (
            f"Car interior cleaning for a {size}: fabric seats, car carpet and dashboard, "
            f"priced per car. {ON_SITE_PROCESS}"
        ),
        "pricing_unit": PricingUnit.PER_ITEM,
        "unit_price": D(price),
        "visit_minutes": 120,
        "on_site": True,
    }


SERVICES: list[dict] = [
    carpet("Karpet Biasa", "Standard carpet", "1.80"),
    carpet("Karpet Shaggy", "Shaggy (long-pile) carpet", "2.00"),
    carpet("Karpet Velvet", "Velvet carpet", "0.90", fold=True),
    carpet("Karpet Premium Velvet", "Premium velvet carpet", "1.00", fold=True),
    carpet("Karpet Span", "Span carpet", "0.90"),
    carpet("Karpet Tatami", "Tatami carpet", "0.90"),
    carpet("Karpet Handmade", "Handmade carpet", "2.50", price_max="4.00"),
    on_site("Cucian Sofa", "Sofa", "seat", "60.00"),
    on_site("Cucian Tilam Single", "Single mattress", "mattress", "100.00"),
    on_site("Cucian Tilam Queen", "Queen mattress", "mattress", "140.00"),
    on_site("Cucian Tilam King", "King mattress", "mattress", "160.00"),
    car_seats("Sedan", "130.00"),
    car_seats("SUV", "150.00"),
    car_seats("MPV", "170.00"),
    # Mosque/surau/office carpets are quoted after a site visit, so they have no catalogue
    # price (the assistant sends those requests to the owner).
]


def seed_services(db: Session) -> tuple[int, int]:
    """Insert or update every service in SERVICES. Returns (created, updated)."""
    existing = {s.name: s for s in db.scalars(select(Service))}
    created = updated = 0
    for data in SERVICES:
        values = {
            "unit_price_max": None,
            "minimum_charge": D("0"),
            "needs_fold": False,
            "on_site": False,
            **data,
        }
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
