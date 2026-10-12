from decimal import Decimal

from app.ai.price_list import SOURCE, describe_service, price_list_chunks
from app.db.models import PricingUnit, Service

D = Decimal


def service(**overrides: object) -> Service:
    fields = {
        "name": "Karpet Shaggy",
        "description": "Shaggy carpet cleaning.",
        "pricing_unit": PricingUnit.PER_SQFT,
        "unit_price": D("2.00"),
        "unit_price_max": None,
        "minimum_charge": D("0"),
        "is_active": True,
    }
    return Service(**{**fields, **overrides})


def test_fixed_price_per_square_foot() -> None:
    assert describe_service(service()) == (
        "Karpet Shaggy costs RM2.00 per square foot. Shaggy carpet cleaning."
    )


def test_price_range_is_described_as_a_range() -> None:
    handmade = service(name="Karpet Handmade", unit_price=D("2.50"), unit_price_max=D("4.00"))

    assert "RM2.50 to RM4.00 per square foot" in describe_service(handmade)


def test_per_item_and_minimum_charge() -> None:
    sofa = service(
        name="Cucian Sofa",
        pricing_unit=PricingUnit.PER_ITEM,
        unit_price=D("60"),
        minimum_charge=D("50"),
        description="",
    )

    assert describe_service(sofa) == "Cucian Sofa costs RM60.00 per item. Minimum charge RM50.00."


def test_inactive_services_are_left_out() -> None:
    chunks = price_list_chunks([service(), service(name="Old service", is_active=False)])

    assert [(c.source, c.heading) for c in chunks] == [(SOURCE, "Karpet Shaggy")]
