"""Generate price-list chunks from the services table.

Prices are never written in the knowledge documents. They are rendered from the database at
ingestion time, so changing a price in one place updates both the API and the assistant.
"""

from collections.abc import Iterable
from decimal import Decimal

from app.ai.chunking import Chunk
from app.db.models import PricingUnit, Service

SOURCE = "price list (services database)"
TITLE = "Price list"

_UNIT = {
    PricingUnit.PER_SQFT: "per square foot",
    PricingUnit.PER_ITEM: "per item",
    PricingUnit.FLAT: "per job",
}


def price_list_chunks(services: Iterable[Service]) -> list[Chunk]:
    return [
        Chunk(SOURCE, TITLE, service.name, describe_service(service))
        for service in services
        if service.is_active
    ]


def describe_service(service: Service) -> str:
    sentences = [f"{service.name} costs {describe_price(service)}."]
    if service.minimum_charge > 0:
        sentences.append(f"Minimum charge {_rm(service.minimum_charge)}.")
    if service.description:
        sentences.append(service.description)
    return " ".join(sentences)


def describe_price(service: Service) -> str:
    unit = _UNIT[service.pricing_unit]
    if service.unit_price_max is not None:
        return f"{_rm(service.unit_price)} to {_rm(service.unit_price_max)} {unit}"
    return f"{_rm(service.unit_price)} {unit}"


def _rm(amount: Decimal) -> str:
    return f"RM{amount:.2f}"
