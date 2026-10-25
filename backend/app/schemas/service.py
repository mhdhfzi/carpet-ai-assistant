from datetime import datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models import PricingUnit

# Matches the NUMERIC(10, 2) columns. Money is serialised to JSON as a string ("120.00")
# so no precision is lost in JavaScript clients.
Money = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]
Name = Annotated[str, Field(min_length=1, max_length=100)]
VisitMinutes = Annotated[int, Field(gt=0, le=600)]


class ServiceCreate(BaseModel):
    name: Name
    description: str = ""
    pricing_unit: PricingUnit
    unit_price: Money
    # Only for services priced on inspection; unit_price is then the lower bound.
    unit_price_max: Money | None = None
    minimum_charge: Money = Decimal("0")
    visit_minutes: VisitMinutes = 120
    on_site: bool = False  # done at the customer's home (no washing or packing forms)


class ServiceUpdate(BaseModel):
    """Partial update: only fields present in the request body are changed.

    unit_price_max may be sent as null to turn a price range back into a fixed price.
    """

    name: Name | None = None
    description: str | None = None
    pricing_unit: PricingUnit | None = None
    unit_price: Money | None = None
    unit_price_max: Money | None = None
    minimum_charge: Money | None = None
    visit_minutes: VisitMinutes | None = None
    on_site: bool | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _reject_explicit_nulls(self) -> Self:
        nulls = sorted(
            field
            for field in self.model_fields_set - {"unit_price_max"}
            if getattr(self, field) is None
        )
        if nulls:
            raise ValueError(f"These fields cannot be null: {', '.join(nulls)}")
        return self


class ServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    pricing_unit: PricingUnit
    on_site: bool
    needs_fold: bool  # velvet: packed rolled (gulung) or folded (lipat)
    custom: bool  # "Lain-lain": described and priced when the order is taken
    unit_price: Decimal
    unit_price_max: Decimal | None
    minimum_charge: Decimal
    visit_minutes: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
