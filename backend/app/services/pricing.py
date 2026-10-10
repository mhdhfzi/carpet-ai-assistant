"""Price calculation. Kept deliberately small for now; extended by the pricing-service step."""

from decimal import ROUND_HALF_UP, Decimal

from app.db.models import Service

CENT = Decimal("0.01")


def line_total(service: Service, quantity: Decimal) -> Decimal:
    """Price for `quantity` units of a service, with the service's minimum charge applied."""
    base = service.unit_price * quantity
    return max(base, service.minimum_charge).quantize(CENT, rounding=ROUND_HALF_UP)
