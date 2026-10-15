"""Tools the assistant can call: look up services, quote prices, check availability, book,
and hand over to a human.

Each tool's input is a Pydantic model. The same model produces the JSON schema Claude sees
and validates what Claude sends back, so the two can never drift apart. Handlers call the
existing service layer; business rules (prices, opening hours, double-booking) live there,
not in the prompt.
"""

import json
from collections.abc import Callable, Collection
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from app.ai.price_list import describe_price
from app.db.models import BookingLocation, Conversation, UnansweredReason
from app.schemas.booking import BookingCreate
from app.services import availability, bookings, catalog, pricing, unanswered
from app.services.errors import DomainError

ESTIMATE_NOTE = (
    "This is an estimate. Carpet prices are confirmed after the carpet is measured, and "
    "handmade carpet prices after the owner inspects the material."
)


@dataclass
class ToolContext:
    db: Session
    conversation: Conversation
    # The customer message this turn is answering; used by the booking confirmation guard.
    customer_message_id: int
    # Similarity of the best knowledge chunk retrieved this turn (for the unanswered log).
    top_score: float | None = None


@dataclass(frozen=True)
class ToolResult:
    content: str  # JSON text sent back to the model
    is_error: bool = False


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Inputs ----------------------------------------------------------------------------------


class NoInput(ToolInput):
    pass


class ItemInput(ToolInput):
    service_id: int = Field(description="Service id from get_services.")
    quantity: float = Field(
        gt=0,
        description="Square feet for carpets (per_sqft), or number of items (per_item: sofa "
        "seats, mattresses).",
    )


class EstimateInput(ToolInput):
    items: list[ItemInput] = Field(min_length=1)


class AvailabilityInput(ToolInput):
    service_ids: list[int] = Field(min_length=1, description="Services the visit is for.")
    location: BookingLocation = Field(
        default=BookingLocation.CUSTOMER_HOME,
        description="customer_home: the team visits. shop: the customer drops items off.",
    )
    date_from: date | None = Field(
        default=None, description="First date to check (YYYY-MM-DD). Defaults to the earliest."
    )
    days: int = Field(default=7, ge=1, le=14, description="How many days to check.")


class PrepareBookingInput(ToolInput):
    customer_name: str = Field(min_length=1, max_length=100)
    phone: str = Field(description="Customer's phone / WhatsApp number, e.g. 012-345 6789.")
    area: str | None = Field(default=None, description="Town or area, e.g. Seremban.")
    address: str | None = Field(default=None, description="Address for home visits.")
    visit_date: date = Field(description="Visit date, YYYY-MM-DD (Malaysia time).")
    start_time: str = Field(
        pattern=r"^\d{2}:\d{2}$", description="Visit start time, HH:MM, 24-hour."
    )
    location: BookingLocation = BookingLocation.CUSTOMER_HOME
    items: list[ItemInput] = Field(min_length=1)
    notes: str | None = Field(default=None, description="Anything the owner should know.")


class FlagUnansweredInput(ToolInput):
    question: str = Field(
        min_length=1,
        description="The question you couldn't answer, summarised in English for the owner.",
    )


class HandoffInput(ToolInput):
    reason: str = Field(min_length=1, description="Short reason, shown to the owner.")


# --- Handlers --------------------------------------------------------------------------------


def get_services(ctx: ToolContext, _: NoInput) -> dict[str, Any]:
    return {
        "services": [
            {
                "service_id": s.id,
                "name": s.name,
                "price": describe_price(s),
                "pricing_unit": s.pricing_unit.value,
                "description": s.description,
            }
            for s in catalog.list_services(ctx.db)
        ]
    }


def estimate_price(ctx: ToolContext, data: EstimateInput) -> dict[str, Any]:
    services = catalog.get_bookable_services(ctx.db, {i.service_id for i in data.items})
    estimates = [
        (
            item,
            services[item.service_id],
            pricing.estimate_line(services[item.service_id], _decimal(item.quantity)),
        )
        for item in data.items
    ]
    return {
        "lines": [
            {"service": service.name, "quantity": item.quantity, "estimate": _rm(estimate)}
            for item, service, estimate in estimates
        ],
        "total": _rm(pricing.estimate_total(estimate for _, _, estimate in estimates)),
        "note": ESTIMATE_NOTE,
    }


def check_availability(ctx: ToolContext, data: AvailabilityInput) -> dict[str, Any]:
    services = catalog.get_bookable_services(ctx.db, set(data.service_ids))
    duration = availability.visit_duration(services.values())
    found = availability.find_available_slots(
        ctx.db, duration, location=data.location, date_from=data.date_from, days=data.days
    )
    return {
        "visit_length_minutes": int(duration.total_seconds() // 60),
        "days": [
            {
                "date": day.isoformat(),
                "weekday": f"{day:%A}",
                "free_start_times": _time_ranges(slots),
            }
            for day, slots in found
        ],
        "rules": "Closed on Fridays and public holidays. Open 9:00-17:30. "
        "Bookings need at least 2 days' notice.",
    }


def prepare_booking(ctx: ToolContext, data: PrepareBookingInput) -> dict[str, Any]:
    """Check the booking is possible and store it as a draft. Creates nothing yet."""
    request = BookingCreate.model_validate(
        {
            "customer": {
                "name": data.customer_name,
                "phone": data.phone,
                "area": data.area,
                "address": data.address,
            },
            "scheduled_start": _local_datetime(data.visit_date, data.start_time),
            "location": data.location,
            "items": [
                {"service_id": i.service_id, "quantity": _decimal(i.quantity)} for i in data.items
            ],
            "notes": data.notes,
        }
    )
    quote = bookings.quote_booking(ctx.db, request)

    ctx.conversation.booking_draft = request.model_dump(mode="json")
    ctx.conversation.booking_draft_after_message_id = ctx.customer_message_id
    ctx.db.commit()

    start = quote.scheduled_start.astimezone(availability.HOURS.timezone)
    end = quote.scheduled_end.astimezone(availability.HOURS.timezone)
    return {
        "status": "awaiting_customer_confirmation",
        "summary": {
            "name": request.customer.name,
            "phone": request.customer.phone,
            "area": request.customer.area,
            "address": request.customer.address,
            "when": f"{start:%A, %d %B %Y}, {start:%H:%M}-{end:%H:%M}",
            "location": request.location.value,
            "items": [
                f"{line.service.name} x {line.quantity}: {_rm(line.line_total)}"
                for line in quote.lines
            ],
            "estimated_total": _rm(quote.total),
            "notes": request.notes,
        },
        "next_step": "Show this summary to the customer and ask them to confirm. Call "
        "create_booking only after they reply to confirm. If they want changes, call "
        "prepare_booking again with the new details.",
        "note": ESTIMATE_NOTE,
    }


def create_booking(ctx: ToolContext, _: NoInput) -> dict[str, Any]:
    """Create the booking from the stored draft, once the customer has replied to it.

    Takes no input on purpose: the model can't change any detail between the summary the
    customer confirmed and the booking that gets created.
    """
    conversation = ctx.conversation
    if conversation.booking_draft is None:
        raise DomainError("There is no booking to create. Call prepare_booking first.")
    if ctx.customer_message_id <= (conversation.booking_draft_after_message_id or 0):
        raise DomainError(
            "The customer hasn't confirmed yet. Show them the booking summary and wait for "
            "their reply before calling create_booking."
        )

    request = BookingCreate.model_validate(conversation.booking_draft)
    booking = bookings.create_booking(ctx.db, request, conversation_id=conversation.id)

    conversation.customer = booking.customer
    conversation.booking_draft = None
    conversation.booking_draft_after_message_id = None
    ctx.db.commit()
    return {
        "booking_id": booking.id,
        "status": booking.status.value,
        "next_step": "Tell the customer the booking is received and pending: the owner will "
        "contact them to confirm the time.",
    }


def flag_unanswered_question(ctx: ToolContext, data: FlagUnansweredInput) -> dict[str, Any]:
    unanswered.log_question(
        ctx.db,
        ctx.conversation,
        ctx.customer_message_id,
        UnansweredReason.NO_ANSWER,
        question=data.question,
        top_score=ctx.top_score,
    )
    ctx.db.commit()
    return {
        "logged": True,
        "next_step": "Tell the customer you're not sure and the owner will get back to them.",
    }


def handoff_to_human(ctx: ToolContext, data: HandoffInput) -> dict[str, Any]:
    ctx.conversation.handed_off = True
    ctx.conversation.handoff_reason = data.reason
    unanswered.log_question(
        ctx.db,
        ctx.conversation,
        ctx.customer_message_id,
        UnansweredReason.HANDED_OFF,
        detail=data.reason,
        top_score=ctx.top_score,
    )
    ctx.db.commit()
    return {
        "handed_off": True,
        "next_step": "Tell the customer the owner will reply to them here soon. Don't promise "
        "anything else.",
    }


# --- Registry --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_model: type[ToolInput]
    handler: Callable[[ToolContext, Any], dict[str, Any]]

    def definition(self) -> dict[str, Any]:
        schema = self.input_model.model_json_schema()
        schema.pop("title", None)
        return {"name": self.name, "description": self.description, "input_schema": schema}


TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in [
        Tool(
            "get_services",
            "List the services offered with their ids and prices. Call this before quoting, "
            "checking availability or booking, to get service ids.",
            NoInput,
            get_services,
        ),
        Tool(
            "estimate_price",
            "Estimate the price for given services and quantities (square feet for carpets, "
            "number of items for sofas and mattresses). Use whenever the customer asks how much.",
            EstimateInput,
            estimate_price,
        ),
        Tool(
            "check_availability",
            "Find free visit start times for the given services. Use before suggesting or "
            "agreeing on a date and time.",
            AvailabilityInput,
            check_availability,
        ),
        Tool(
            "prepare_booking",
            "Check a booking is possible and get a summary to show the customer. Does NOT "
            "create the booking. Needs name, phone, visit date, start time, location and items.",
            PrepareBookingInput,
            prepare_booking,
        ),
        Tool(
            "create_booking",
            "Create the booking prepared with prepare_booking. Only call after the customer "
            "has seen the summary and replied to confirm it.",
            NoInput,
            create_booking,
        ),
        Tool(
            "flag_unanswered_question",
            "Record a question you can't answer from the information and tools you have, so "
            "the owner can follow up and add the answer. Call it before telling the customer "
            "you're not sure. Not needed for greetings or small talk.",
            FlagUnansweredInput,
            flag_unanswered_question,
        ),
        Tool(
            "handoff_to_human",
            "Hand the conversation over to the owner. Use when the customer is upset, asks "
            "for a person, or needs something you can't answer from the information you have.",
            HandoffInput,
            handoff_to_human,
        ),
    ]
}


# What a deployment that doesn't take bookings offers: read-only answers, plus logging the
# questions it couldn't answer. Hand-offs go to WhatsApp instead (see app/ai/prompts.py).
ANSWER_TOOLS = ("get_services", "estimate_price", "flag_unanswered_question")


def available_tools(bookings_enabled: bool) -> tuple[str, ...]:
    return tuple(TOOLS) if bookings_enabled else ANSWER_TOOLS


def tool_definitions(names: Collection[str] | None = None) -> list[dict[str, Any]]:
    return [tool.definition() for tool in TOOLS.values() if names is None or tool.name in names]


def run_tool(
    ctx: ToolContext,
    name: str,
    raw_input: dict[str, Any],
    *,
    allowed: Collection[str] | None = None,
) -> ToolResult:
    """Run a tool call from the model. Never raises for bad input or business-rule errors:
    those go back to the model as error results so it can correct itself or explain.

    `allowed` is enforced here, not just by which tools the model was shown: a model that
    names a tool it wasn't offered (e.g. create_booking in an answers-only deployment)
    gets an error, never the tool."""
    tool = TOOLS.get(name)
    if tool is None or (allowed is not None and name not in allowed):
        return _error(f"Unknown tool: {name}")
    try:
        data = tool.input_model.model_validate(raw_input)
        result = tool.handler(ctx, data)
    except ValidationError as exc:
        problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        return _error(f"Invalid input: {problems}")
    except (DomainError, ValueError) as exc:
        ctx.db.rollback()
        return _error(str(exc))
    return ToolResult(json.dumps(result, default=str))


# --- Helpers ---------------------------------------------------------------------------------


def _error(message: str) -> ToolResult:
    return ToolResult(json.dumps({"error": message}), is_error=True)


def _decimal(value: float) -> Decimal:
    return Decimal(str(value))


def _rm(price: pricing.PriceRange) -> str:
    if price.is_range:
        return f"RM{price.low:.2f} - RM{price.high:.2f}"
    return f"RM{price.low:.2f}"


def _local_datetime(day: date, hhmm: str) -> datetime:
    """The model gives a date and a wall-clock time; the server attaches Malaysia's timezone,
    so the model never has to reason about UTC offsets."""
    hour, minute = (int(part) for part in hhmm.split(":"))
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=availability.HOURS.timezone)


def _time_ranges(slots: list[datetime]) -> list[str]:
    """Collapse 30-minute slots into ranges ("09:00-11:00"), saving tokens in tool results."""
    step = availability.HOURS.slot_step
    ranges: list[list[datetime]] = []
    for slot in slots:
        if ranges and slot - ranges[-1][-1] == step:
            ranges[-1].append(slot)
        else:
            ranges.append([slot])
    return [f"{r[0]:%H:%M}" if len(r) == 1 else f"{r[0]:%H:%M}-{r[-1]:%H:%M}" for r in ranges]
