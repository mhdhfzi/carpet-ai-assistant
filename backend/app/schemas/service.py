from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import PricingUnit

# Matches the NUMERIC(10, 2) columns. Money is serialised to JSON as a string ("120.00")
# so no precision is lost in JavaScript clients.
Money = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]
Name = Annotated[str, Field(min_length=1, max_length=100)]


class ServiceCreate(BaseModel):
    name: Name
    description: str = ""
    pricing_unit: PricingUnit
    unit_price: Money
    minimum_charge: Money = Decimal("0")


class ServiceUpdate(BaseModel):
    """Partial update: only fields present in the request body are changed."""

    name: Name | None = None
    description: str | None = None
    pricing_unit: PricingUnit | None = None
    unit_price: Money | None = None
    minimum_charge: Money | None = None
    is_active: bool | None = None


class ServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    pricing_unit: PricingUnit
    unit_price: Decimal
    minimum_charge: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime
