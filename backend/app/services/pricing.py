"""Price estimation.

Pure functions with no database access, so the rules are easy to unit test and the AI
agent's `estimate_price` tool can call them directly.

Every estimate is a range: fixed-price services give low == high, while services priced on
inspection (e.g. handmade carpet) give low < high. Prices are always estimates; the final
price is confirmed on site after measuring.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.db.models import PricingUnit, Service
from app.services.errors import BusinessRuleError

CENT = Decimal("0.01")
ZERO = Decimal("0")


@dataclass(frozen=True)
class PriceRange:
    low: Decimal
    high: Decimal

    @property
    def is_range(self) -> bool:
        return self.low != self.high

    def __add__(self, other: "PriceRange") -> "PriceRange":
        return PriceRange(self.low + other.low, self.high + other.high)


def unit_price_range(service: Service) -> PriceRange:
    high = service.unit_price_max if service.unit_price_max is not None else service.unit_price
    return PriceRange(service.unit_price, high)


def estimate_line(service: Service, quantity: Decimal) -> PriceRange:
    """Estimate for `quantity` units (sqft or items) of one service."""
    validate_quantity(service, quantity)
    unit = unit_price_range(service)
    return PriceRange(
        _apply_minimum(unit.low * quantity, service.minimum_charge),
        _apply_minimum(unit.high * quantity, service.minimum_charge),
    )


def estimate_total(lines: Iterable[PriceRange]) -> PriceRange:
    return sum(lines, start=PriceRange(ZERO, ZERO))


def validate_quantity(service: Service, quantity: Decimal) -> None:
    if quantity <= 0:
        raise BusinessRuleError(f"Quantity for {service.name} must be greater than zero")
    if service.pricing_unit is PricingUnit.PER_ITEM and quantity != quantity.to_integral_value():
        raise BusinessRuleError(f"Quantity for {service.name} must be a whole number")
    if service.pricing_unit is PricingUnit.FLAT and quantity != 1:
        raise BusinessRuleError(f"{service.name} is a fixed-price job; quantity must be 1")


def _apply_minimum(amount: Decimal, minimum_charge: Decimal) -> Decimal:
    return max(amount, minimum_charge).quantize(CENT, rounding=ROUND_HALF_UP)
