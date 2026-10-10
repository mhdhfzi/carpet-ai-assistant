"""Unit tests for the pricing rules. No database: Service objects are built in memory."""

from decimal import Decimal

import pytest

from app.db.models import PricingUnit, Service
from app.services.errors import BusinessRuleError
from app.services.pricing import PriceRange, estimate_line, estimate_total, unit_price_range

D = Decimal


def service(
    unit: PricingUnit = PricingUnit.PER_SQFT,
    price: str = "1.80",
    price_max: str | None = None,
    minimum: str = "0",
) -> Service:
    return Service(
        name="Test service",
        pricing_unit=unit,
        unit_price=D(price),
        unit_price_max=D(price_max) if price_max else None,
        minimum_charge=D(minimum),
    )


@pytest.mark.parametrize(
    ("price", "sqft", "expected"),
    [
        ("1.80", "100", "180.00"),  # Karpet Biasa
        ("2.00", "48", "96.00"),  # Karpet Shaggy, 6 x 8 ft rug
        ("0.90", "35.5", "31.95"),  # fractional sqft is fine
        ("0.90", "0.5", "0.45"),
    ],
)
def test_per_sqft_fixed_price(price: str, sqft: str, expected: str) -> None:
    estimate = estimate_line(service(price=price), D(sqft))

    assert estimate == PriceRange(D(expected), D(expected))
    assert not estimate.is_range


def test_handmade_carpet_gives_a_range() -> None:
    handmade = service(price="2.50", price_max="4.00")

    estimate = estimate_line(handmade, D("100"))

    assert estimate == PriceRange(D("250.00"), D("400.00"))
    assert estimate.is_range


def test_unit_price_range_for_fixed_and_ranged_services() -> None:
    assert unit_price_range(service(price="1.80")) == PriceRange(D("1.80"), D("1.80"))
    assert unit_price_range(service(price="2.50", price_max="4.00")) == PriceRange(
        D("2.50"), D("4.00")
    )


def test_per_item_price() -> None:
    sofa = service(unit=PricingUnit.PER_ITEM, price="60.00")

    assert estimate_line(sofa, D("3")) == PriceRange(D("180.00"), D("180.00"))


def test_flat_price() -> None:
    job = service(unit=PricingUnit.FLAT, price="150.00")

    assert estimate_line(job, D("1")) == PriceRange(D("150.00"), D("150.00"))


def test_minimum_charge_raises_small_jobs_only() -> None:
    with_minimum = service(price="1.00", price_max="2.00", minimum="80.00")

    assert estimate_line(with_minimum, D("50")) == PriceRange(D("80.00"), D("100.00"))
    assert estimate_line(with_minimum, D("10")) == PriceRange(D("80.00"), D("80.00"))


def test_rounds_half_up_to_the_cent() -> None:
    # 0.90 x 0.05 = 0.045 -> 0.05 (banker's rounding would give 0.04)
    assert estimate_line(service(price="0.90"), D("0.05")).low == D("0.05")


@pytest.mark.parametrize(
    ("unit", "quantity", "message"),
    [
        (PricingUnit.PER_ITEM, "2.5", "whole number"),
        (PricingUnit.FLAT, "2", "quantity must be 1"),
        (PricingUnit.PER_SQFT, "0", "greater than zero"),
        (PricingUnit.PER_SQFT, "-5", "greater than zero"),
    ],
)
def test_invalid_quantities_are_rejected(unit: PricingUnit, quantity: str, message: str) -> None:
    with pytest.raises(BusinessRuleError, match=message):
        estimate_line(service(unit=unit), D(quantity))


def test_whole_number_written_with_decimals_is_accepted_for_items() -> None:
    sofa = service(unit=PricingUnit.PER_ITEM, price="60.00")

    assert estimate_line(sofa, D("2.00")).low == D("120.00")


def test_estimate_total_mixes_fixed_and_ranged_lines() -> None:
    lines = [
        estimate_line(service(price="1.80"), D("100")),  # 180.00
        estimate_line(service(price="2.50", price_max="4.00"), D("20")),  # 50.00 - 80.00
        estimate_line(service(unit=PricingUnit.PER_ITEM, price="60.00"), D("3")),  # 180.00
    ]

    assert estimate_total(lines) == PriceRange(D("410.00"), D("440.00"))


def test_estimate_total_of_nothing_is_zero() -> None:
    assert estimate_total([]) == PriceRange(D("0"), D("0"))
