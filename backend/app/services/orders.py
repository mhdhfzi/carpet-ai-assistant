"""Orders: the back office that replaces the owner's book.

Rules live here, not in the dashboard, so they hold whoever calls the API:
- order numbers run 1, 2, 3, ... with no repeats, even when two people save at once
- prices come from the price list and are copied onto each item when recorded
- staff record orders and move them one step along; the owner can set prices and
  discounts, cancel, and correct a status
- payments are never edited or deleted: the owner voids a wrong one, with a reason
- each item (each tagged carpet) is washed, dries and is packed on its own, recording who
  did each step (the washing and packing forms); velvet is packed rolled or folded, and
  staff must say which
- the order follows its slowest item, and is handed back only when every item is packed
"""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session, selectinload

from app.core import clock
from app.core.security import ForbiddenError
from app.db.models import (
    Customer,
    ItemFold,
    ItemStatus,
    Order,
    OrderEvent,
    OrderItem,
    OrderStatus,
    Owner,
    OwnerRole,
    Payment,
    PricingUnit,
    Service,
    UntaggedItem,
)
from app.schemas.booking import CustomerIn, normalize_phone
from app.schemas.order import OrderCreate, OrderItemIn, OrderUpdate, PaymentIn
from app.services.availability import HOURS
from app.services.errors import BusinessRuleError, InvalidStatusTransitionError, NotFoundError

CENT = Decimal("0.01")
# Carpets dry for 5-7 days after washing (the owner's estimate).
DRYING_DAYS = (5, 7)
# The normal path a job takes. Staff may only move an order one step along it.
NEXT_STATUS = {
    OrderStatus.RECEIVED: OrderStatus.WASHED,
    OrderStatus.WASHED: OrderStatus.READY,
    OrderStatus.READY: OrderStatus.COMPLETED,
}
CLOSED = {OrderStatus.COMPLETED, OrderStatus.CANCELLED}
ITEM_STEPS = [ItemStatus.RECEIVED, ItemStatus.WASHED, ItemStatus.READY]
# An open order's status is its slowest item's step.
ORDER_STEP = {
    ItemStatus.RECEIVED: OrderStatus.RECEIVED,
    ItemStatus.WASHED: OrderStatus.WASHED,
    ItemStatus.READY: OrderStatus.READY,
}
# Moving the whole order to a step moves its items there (handed back = all packed).
ITEM_STEP = {
    OrderStatus.RECEIVED: ItemStatus.RECEIVED,
    OrderStatus.WASHED: ItemStatus.WASHED,
    OrderStatus.READY: ItemStatus.READY,
    OrderStatus.COMPLETED: ItemStatus.READY,
}
# An item's progress: kept when the order's items are edited.
_PROGRESS = (
    "status",
    "washed_on",
    "washed_by_id",
    "wash_note",
    "ready_on",
    "packed_by_id",
    "fold",
)
# Any fixed number: serialises order creation so two saves never get the same number.
_NUMBER_LOCK = 774_101


@dataclass(frozen=True)
class Totals:
    subtotal: Decimal
    total: Decimal
    paid: Decimal
    balance: Decimal
    price_pending: bool


def today() -> date:
    return clock.now().astimezone(HOURS.timezone).date()


def is_owner(actor: Owner) -> bool:
    return actor.role is OwnerRole.OWNER


def _owner_only(actor: Owner, what: str) -> None:
    if not is_owner(actor):
        raise ForbiddenError(f"Only the owner can {what}")


# --- Reading ---------------------------------------------------------------------------------


def _with_details():
    return (
        selectinload(Order.customer),
        selectinload(Order.items).selectinload(OrderItem.service),
        selectinload(Order.items).selectinload(OrderItem.washed_by),
        selectinload(Order.items).selectinload(OrderItem.packed_by),
        selectinload(Order.events).selectinload(OrderEvent.by),
        selectinload(Order.payments).selectinload(Payment.received_by),
    )


def get_order(db: Session, order_id: int) -> Order:
    order = db.scalar(select(Order).where(Order.id == order_id).options(*_with_details()))
    if order is None:
        raise NotFoundError(f"Order {order_id} not found")
    return order


def list_orders(
    db: Session,
    *,
    statuses: Collection[OrderStatus] = (),
    q: str | None = None,
    customer_id: int | None = None,
    limit: int = 100,
) -> list[Order]:
    """Newest first. `q` finds an order by number, tag ("412-2"), phone or name."""
    query = select(Order).join(Order.customer).options(*_with_details())
    if customer_id is not None:
        query = query.where(Order.customer_id == customer_id)
    if statuses:
        query = query.where(Order.status.in_(statuses))
    if q and q.strip():
        query = query.where(_search(q.strip()))
    return list(db.scalars(query.order_by(Order.number.desc()).limit(limit)))


def _search(q: str):
    conditions = [Customer.name.ilike(f"%{q}%")]
    number = q.split("-")[0]  # a tag "412-2" belongs to order 412
    if number.isdigit():
        conditions.append(Order.number == int(number))
    digits = "".join(ch for ch in q if ch.isdigit())
    if len(digits) >= 4:  # part of a phone number, written any way
        conditions.append(Customer.phone.like(f"%{digits.lstrip('0')}%"))
    return or_(*conditions)


def work_items(db: Session, status: ItemStatus, *, limit: int = 300) -> list[OrderItem]:
    """Items waiting for their next step across open orders: the washing list (received)
    or the packing list (washed). Longest-waiting first."""
    query = (
        select(OrderItem)
        .join(OrderItem.order)
        .where(OrderItem.status == status, Order.status.not_in(CLOSED))
        .options(*_item_details())
        .order_by(OrderItem.washed_on.asc().nulls_first(), Order.number, OrderItem.position)
        .limit(limit)
    )
    return list(db.scalars(query))


def work_log(db: Session, day: date) -> tuple[list[OrderItem], list[OrderItem]]:
    """(items washed that day, items packed that day): the day's washing and packing forms."""

    def on(column) -> list[OrderItem]:
        query = (
            select(OrderItem)
            .join(OrderItem.order)
            .where(column == day)
            .options(*_item_details())
            .order_by(Order.number, OrderItem.position)
        )
        return list(db.scalars(query))

    return on(OrderItem.washed_on), on(OrderItem.ready_on)


@dataclass(frozen=True)
class WorkSummary:
    """The numbers at the top of the dashboard: what needs doing today."""

    to_wash: int  # items not washed yet
    to_pack: int  # washed at least 5 days ago (or not a carpet): pack them
    drying: int  # washed, still drying
    ready_orders: int  # every item packed: waiting to be picked up or delivered
    unpaid: Decimal  # still owed, across all orders except cancelled ones
    unpaid_orders: int


def work_summary(db: Session) -> WorkSummary:
    rows = db.execute(
        select(OrderItem.status, OrderItem.washed_on, Service.pricing_unit)
        .join(OrderItem.order)
        .join(OrderItem.service)
        .where(Order.status.not_in(CLOSED), OrderItem.status != ItemStatus.READY)
    ).all()
    to_wash = sum(1 for status, _, _ in rows if status is ItemStatus.RECEIVED)
    due = today() - timedelta(days=DRYING_DAYS[0])
    to_pack = sum(
        1
        for status, washed_on, unit in rows
        if status is ItemStatus.WASHED
        and (unit is not PricingUnit.PER_SQFT or washed_on is None or washed_on <= due)
    )
    ready = db.scalar(select(func.count()).where(Order.status == OrderStatus.READY)) or 0
    _, owed = _order_value_and_owed()
    owing = (
        select(owed.label("owed"))
        .select_from(Order)
        .where(Order.status != OrderStatus.CANCELLED)
        .subquery()
    )
    unpaid, unpaid_orders = db.execute(
        select(func.coalesce(func.sum(owing.c.owed), 0), func.count()).where(owing.c.owed > 0)
    ).one()
    return WorkSummary(
        to_wash=to_wash,
        to_pack=to_pack,
        drying=sum(1 for status, _, _ in rows if status is ItemStatus.WASHED) - to_pack,
        ready_orders=ready,
        unpaid=Decimal(unpaid),
        unpaid_orders=unpaid_orders,
    )


def _order_value_and_owed():
    """Per order, as SQL expressions over Order: its value (priced items less discount; an
    item without a price yet counts as 0) and what is still owed on it."""
    items = (
        select(func.coalesce(func.sum(func.round(OrderItem.unit_price * OrderItem.quantity, 2)), 0))
        .where(OrderItem.order_id == Order.id)
        .scalar_subquery()
    )
    paid = (
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(Payment.order_id == Order.id, Payment.voided_at.is_(None))
        .scalar_subquery()
    )
    value = func.greatest(items - Order.discount, 0)
    return value, func.greatest(value - paid, 0)


# --- Untagged carpets ------------------------------------------------------------------------


def list_untagged(db: Session) -> list[UntaggedItem]:
    """Carpets still waiting to be matched to their order, oldest first."""
    query = (
        select(UntaggedItem)
        .where(UntaggedItem.matched_tag.is_(None))
        .options(selectinload(UntaggedItem.found_by))
        .order_by(UntaggedItem.id)
    )
    return list(db.scalars(query))


def log_untagged(db: Session, description: str, actor: Owner) -> UntaggedItem:
    item = UntaggedItem(description=description, found_on=today(), found_by_id=actor.id)
    db.add(item)
    db.commit()
    return item


def match_untagged(db: Session, untagged_id: int, tag_text: str, actor: Owner) -> UntaggedItem:
    """Someone recognised the carpet: record which tag it is (it must exist)."""
    untagged = db.get(UntaggedItem, untagged_id)
    if untagged is None:
        raise NotFoundError(f"Untagged carpet {untagged_id} not found")
    if untagged.matched_tag is not None:
        raise BusinessRuleError(f"Already matched to {untagged.matched_tag}")
    number, _, position = tag_text.strip().partition("-")
    if not (number.isdigit() and position.isdigit()):
        raise BusinessRuleError("Write the tag as order-item, e.g. 412-2")
    exists = db.scalar(
        select(OrderItem.id)
        .join(OrderItem.order)
        .where(Order.number == int(number), OrderItem.position == int(position))
    )
    if exists is None:
        raise NotFoundError(f"There is no carpet {number}-{position}")
    untagged.matched_tag = f"{int(number)}-{int(position)}"
    untagged.matched_by_id = actor.id
    untagged.matched_at = clock.now()
    db.commit()
    return untagged


def _item_details():
    return (
        selectinload(OrderItem.order).selectinload(Order.customer),
        selectinload(OrderItem.service),
        selectinload(OrderItem.washed_by),
        selectinload(OrderItem.packed_by),
    )


def totals(order: Order) -> Totals:
    lines = [line_total(item) for item in order.items]
    subtotal = sum((line for line in lines if line is not None), Decimal("0"))
    total = max(subtotal - order.discount, Decimal("0"))
    paid = sum((p.amount for p in order.payments if p.voided_at is None), Decimal("0"))
    pending = any(line is None for line in lines)
    return Totals(subtotal, total, paid, total - paid, pending)


def line_total(item: OrderItem) -> Decimal | None:
    if item.unit_price is None:
        return None
    return (item.unit_price * item.quantity).quantize(CENT, ROUND_HALF_UP)


def ready_window(order: Order) -> tuple[date, date] | None:
    """When the carpets should all be dry enough to pack: 5-7 days after the last wash."""
    carpets = [i for i in order.items if i.service.pricing_unit is PricingUnit.PER_SQFT]
    if not carpets or any(i.washed_on is None for i in carpets):
        return None
    if all(i.status is ItemStatus.READY for i in carpets):  # all packed
        return None
    return item_ready_window(max(carpets, key=lambda i: i.washed_on))


def item_ready_window(item: OrderItem) -> tuple[date, date] | None:
    """When one washed carpet should be dry enough to pack."""
    if item.washed_on is None or item.status is not ItemStatus.WASHED:
        return None
    if item.service.pricing_unit is not PricingUnit.PER_SQFT:
        return None
    return item.washed_on + timedelta(days=DRYING_DAYS[0]), item.washed_on + timedelta(
        days=DRYING_DAYS[1]
    )


def progress(order: Order) -> tuple[int, int]:
    """(items washed or packed, items packed): shown as "2 / 3 siap" on the order list."""
    washed = sum(1 for i in order.items if i.status is not ItemStatus.RECEIVED)
    ready = sum(1 for i in order.items if i.status is ItemStatus.READY)
    return washed, ready


def tag(order: Order, item: OrderItem) -> str:
    return f"{order.number}-{item.position}"


def _tag(item: OrderItem) -> str:
    return tag(item.order, item)


# --- Customers -------------------------------------------------------------------------------


def find_customer(db: Session, phone: str) -> Customer | None:
    return db.scalar(select(Customer).where(Customer.phone == normalize_phone(phone)))


@dataclass(frozen=True)
class CustomerRow:
    customer: Customer
    orders: int
    last_order_on: date | None
    total_value: Decimal  # all their orders except cancelled ones
    unpaid: Decimal  # what they still owe on those orders


def list_customers(
    db: Session, q: str | None = None, *, limit: int = 50, offset: int = 0
) -> list[CustomerRow]:
    """Every customer (or those matching a name or phone), most recent first."""
    # Each order's value: its priced items less its discount (items without a price yet
    # count as 0), computed in the database so the whole table is one query.
    lines = (
        select(
            OrderItem.order_id,
            func.coalesce(
                func.sum(func.round(OrderItem.unit_price * OrderItem.quantity, 2)), 0
            ).label("items"),
        )
        .group_by(OrderItem.order_id)
        .subquery()
    )
    paid = (
        select(Payment.order_id, func.sum(Payment.amount).label("paid"))
        .where(Payment.voided_at.is_(None))
        .group_by(Payment.order_id)
        .subquery()
    )
    value = func.greatest(func.coalesce(lines.c["items"], 0) - Order.discount, 0)
    owed = func.greatest(value - func.coalesce(paid.c.paid, 0), 0)
    counted = Order.status != OrderStatus.CANCELLED
    query = (
        select(
            Customer,
            func.count(Order.id),
            func.max(Order.received_on),
            func.coalesce(func.sum(value).filter(counted), 0),
            func.coalesce(func.sum(owed).filter(counted), 0),
        )
        .outerjoin(Order, Order.customer_id == Customer.id)
        .outerjoin(lines, lines.c.order_id == Order.id)
        .outerjoin(paid, paid.c.order_id == Order.id)
        .group_by(Customer.id)
        .order_by(func.max(Order.received_on).desc().nulls_last(), Customer.name)
        .limit(limit)
        .offset(offset)
    )
    if q and q.strip():
        q = q.strip()
        digits = "".join(ch for ch in q if ch.isdigit())
        match = Customer.name.ilike(f"%{q}%")
        if len(digits) >= 4:
            match = or_(match, Customer.phone.like(f"%{digits.lstrip('0')}%"))
        query = query.where(match)
    return [
        CustomerRow(c, n, last, Decimal(total), Decimal(unpaid))
        for c, n, last, total, unpaid in db.execute(query)
    ]


def _save_customer(db: Session, data: CustomerIn) -> Customer:
    """Find the customer by phone, or add them. Staff and owner are trusted, so details they
    type (a new address, a corrected name) update the record."""
    customer = db.scalar(select(Customer).where(Customer.phone == data.phone))
    if customer is None:
        customer = Customer(**data.model_dump())
        db.add(customer)
        return customer
    customer.name = data.name
    if data.area:
        customer.area = data.area
    if data.address:
        customer.address = data.address
    return customer


# --- Writing ---------------------------------------------------------------------------------


def create_order(db: Session, data: OrderCreate, actor: Owner) -> Order:
    if data.discount > 0:
        _owner_only(actor, "give a discount")
    customer = _save_customer(db, data.customer)
    # One order number at a time: concurrent saves wait here for a few milliseconds.
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _NUMBER_LOCK})
    number = (db.scalar(select(func.max(Order.number))) or 0) + 1
    order = Order(
        number=number,
        customer=customer,
        received_on=data.received_on or today(),
        return_method=data.return_method,
        discount=data.discount,
        notes=data.notes,
        created_by_id=actor.id,
        items=_build_items(db, data.items, actor),
    )
    order.events.append(OrderEvent(status=OrderStatus.RECEIVED, by_id=actor.id))
    if data.deposit > 0:
        order.payments.append(
            Payment(
                amount=data.deposit,
                method=data.deposit_method,
                paid_on=order.received_on,
                note="Deposit",
                received_by_id=actor.id,
            )
        )
    db.add(order)
    db.commit()
    return get_order(db, order.id)


def update_order(db: Session, order: Order, data: OrderUpdate, actor: Owner) -> Order:
    sent = data.model_fields_set
    if order.status is OrderStatus.CANCELLED and sent - {"notes"}:
        raise BusinessRuleError("A cancelled order can't be changed")
    if "discount" in sent and data.discount != order.discount:
        _owner_only(actor, "give a discount")
        order.discount = data.discount or Decimal("0")
    if "items" in sent and data.items is not None:
        if order.status in CLOSED and not is_owner(actor):
            raise ForbiddenError("Only the owner can change a finished order")
        _replace_items(db, order, data.items, actor)
        _follow_items(order)
    if "return_method" in sent:
        order.return_method = data.return_method
    if "notes" in sent:
        order.notes = data.notes
    if data.status is not None and data.status is not order.status:
        _change_status(order, data.status, data.status_note, actor)
    db.commit()
    return get_order(db, order.id)


def record_payment(db: Session, order: Order, data: PaymentIn, actor: Owner) -> Order:
    """Money received. Staff may record it (they collect at pickup); it can't exceed what
    is owed, unless some price isn't set yet and the total isn't known."""
    if order.status is OrderStatus.CANCELLED:
        raise BusinessRuleError("A cancelled order can't take payments")
    owed = totals(order)
    if not owed.price_pending and data.amount > owed.balance:
        raise BusinessRuleError(f"That is more than the balance of RM{owed.balance:.2f}")
    order.payments.append(
        Payment(
            amount=data.amount,
            method=data.method,
            paid_on=data.paid_on or today(),
            note=data.note,
            received_by_id=actor.id,
        )
    )
    db.commit()
    return get_order(db, order.id)


def void_payment(db: Session, order: Order, payment_id: int, reason: str, actor: Owner) -> Order:
    """Cancel a wrongly recorded payment. It stays on record, marked void, with the reason."""
    _owner_only(actor, "void a payment")
    payment = next((p for p in order.payments if p.id == payment_id), None)
    if payment is None:
        raise NotFoundError(f"Payment {payment_id} not found on this order")
    if payment.voided_at is not None:
        raise BusinessRuleError("This payment is already void")
    payment.voided_at = clock.now()
    payment.voided_by_id = actor.id
    payment.void_reason = reason
    db.commit()
    return get_order(db, order.id)


def update_item_status(
    db: Session,
    order: Order,
    item_id: int,
    new: ItemStatus,
    note: str | None,
    actor: Owner,
    fold: ItemFold | None = None,
) -> Order:
    """Move one carpet along (e.g. "412-2 dicuci"). Staff go one step forward; going back is
    a correction for the owner. Packing a velvet carpet needs `fold` (gulung or lipat). The
    order then follows its slowest item."""
    if order.status in CLOSED:
        raise BusinessRuleError(f"This order is {order.status.value}")
    item = next((i for i in order.items if i.id == item_id), None)
    if item is None:
        raise NotFoundError(f"Item {item_id} not found on this order")
    if new is item.status:
        return get_order(db, order.id)
    step = ITEM_STEPS.index(item.status)
    if not is_owner(actor) and ITEM_STEPS.index(new) != step + 1:
        raise InvalidStatusTransitionError(
            f"{tag(order, item)}: the next step is {ITEM_STEPS[step + 1].value}"
            if step + 1 < len(ITEM_STEPS)
            else f"{tag(order, item)} is already {item.status.value}"
        )
    _move_item(item, new, actor, fold)
    if new is ItemStatus.WASHED and note:
        item.wash_note = note  # the washing form's "catatan"
    order.events.append(
        OrderEvent(status=ORDER_STEP[new], item_tag=tag(order, item), note=note, by_id=actor.id)
    )
    _follow_items(order)
    db.commit()
    return get_order(db, order.id)


def _change_status(order: Order, new: OrderStatus, note: str | None, actor: Owner) -> None:
    """Move the whole order: every item comes along (e.g. all carpets washed the same day)."""
    if new is OrderStatus.CANCELLED:
        _owner_only(actor, "cancel an order")
    elif NEXT_STATUS.get(order.status) is not new and not is_owner(actor):
        # Skipping a step or going back is a correction: the owner's call.
        raise InvalidStatusTransitionError(
            f"Can't go from {order.status.value} to {new.value}; the next step is "
            f"{NEXT_STATUS[order.status].value}"
            if order.status in NEXT_STATUS
            else f"This order is {order.status.value}"
        )
    if new is not OrderStatus.CANCELLED:
        target = ITEM_STEPS.index(ITEM_STEP[new])
        backward = _rank(new) < _rank(order.status)
        for item in order.items:
            here = ITEM_STEPS.index(item.status)
            # Forward: items behind catch up (items ahead stay ahead). Back, an owner's
            # correction: items ahead return to that step.
            if here < target or (backward and here > target):
                _move_item(item, ITEM_STEPS[target], actor)
    order.status = new
    _set_step_dates(order, new)
    order.events.append(OrderEvent(status=new, note=note, by_id=actor.id))
    _follow_items(order)


def _rank(status: OrderStatus) -> int:
    """How far along an order is; a cancelled one counts as not started."""
    path = [OrderStatus.RECEIVED, OrderStatus.WASHED, OrderStatus.READY, OrderStatus.COMPLETED]
    return path.index(status) if status in path else 0


def _move_item(
    item: OrderItem, new: ItemStatus, actor: Owner, fold: ItemFold | None = None
) -> None:
    """Set an item's step, recording the day each step was reached and who did it, as the
    washing and packing forms do. Going back clears the later steps."""
    reached = ITEM_STEPS.index(new)
    packing = reached >= 2 and item.ready_on is None
    fold = fold if item.service.needs_fold else None
    if packing and item.service.needs_fold and fold is None:
        raise BusinessRuleError(
            f"{_tag(item)}: {item.service.name} is packed rolled or folded; "
            "pack it on its own and choose which"
        )
    item.status = new
    if reached < 1:
        item.washed_on = item.washed_by_id = item.wash_note = None
    elif item.washed_on is None:
        item.washed_on, item.washed_by_id = today(), actor.id
    if reached < 2:
        item.ready_on = item.packed_by_id = item.fold = None
    elif packing:
        item.ready_on, item.packed_by_id, item.fold = today(), actor.id, fold


def _follow_items(order: Order) -> None:
    """An open order sits at its slowest item's step, so nothing is forgotten."""
    if order.status in CLOSED or not order.items:
        return
    slowest = min(order.items, key=lambda i: ITEM_STEPS.index(i.status)).status
    if ORDER_STEP[slowest] is not order.status:
        order.status = ORDER_STEP[slowest]
        _set_step_dates(order, order.status)


def _set_step_dates(order: Order, status: OrderStatus) -> None:
    """Record the day each step was reached; going back clears the later steps."""
    steps = [
        (OrderStatus.WASHED, "washed_on"),
        (OrderStatus.READY, "ready_on"),
        (OrderStatus.COMPLETED, "completed_on"),
    ]
    order_of = [OrderStatus.RECEIVED, *(s for s, _ in steps)]
    if status is OrderStatus.CANCELLED:
        return
    reached = order_of.index(status)
    for step, field in steps:
        if order_of.index(step) <= reached:
            if getattr(order, field) is None:
                setattr(order, field, today())
        else:
            setattr(order, field, None)


def _replace_items(db: Session, order: Order, items: list[OrderItemIn], actor: Owner) -> None:
    # An item that stays (same service, same place) keeps its price (not today's price
    # list, unless the owner sends a new one) and its progress.
    kept = {(i.service_id, i.position): i for i in order.items}
    order.items.clear()
    db.flush()
    order.items.extend(_build_items(db, items, actor, keep=kept))


def _build_items(
    db: Session,
    items: list[OrderItemIn],
    actor: Owner,
    keep: dict[tuple[int, int], OrderItem] | None = None,
) -> list[OrderItem]:
    built = []
    for position, data in enumerate(items, start=1):
        service = db.get(Service, data.service_id)
        if service is None:
            raise NotFoundError(f"Service {data.service_id} not found")
        quantity, length, width = _quantity(service, data)
        if data.unit_price is not None:
            _owner_only(actor, "set a price")
            unit_price = data.unit_price
        elif keep is not None and (service.id, position) in keep:
            unit_price = keep[(service.id, position)].unit_price
        else:
            # A fixed price comes from the price list; a range (handmade) waits for the owner.
            unit_price = service.unit_price if service.unit_price_max is None else None
        built.append(
            OrderItem(
                position=position,
                service=service,
                length_ft=length,
                width_ft=width,
                quantity=quantity,
                unit_price=unit_price,
                notes=data.notes,
                # Set here, not left to the column default: the order's step is worked out
                # from its items before they're saved.
                status=ItemStatus.RECEIVED,
            )
        )
        before = keep.get((service.id, position)) if keep else None
        if before is not None:
            for field in _PROGRESS:
                setattr(built[-1], field, getattr(before, field))
    return built


def _quantity(
    service: Service, data: OrderItemIn
) -> tuple[Decimal, Decimal | None, Decimal | None]:
    """Square feet from length x width for carpets; a count for everything else."""
    if service.pricing_unit is PricingUnit.PER_SQFT:
        if data.length_ft is not None and data.width_ft is not None:
            sqft = (data.length_ft * data.width_ft).quantize(CENT, ROUND_HALF_UP)
            return sqft, data.length_ft, data.width_ft
        if data.quantity is not None:
            return data.quantity, None, None
        raise BusinessRuleError(f"{service.name}: enter the size (length x width in feet)")
    if data.quantity is None:
        raise BusinessRuleError(f"{service.name}: enter how many")
    if data.quantity != data.quantity.to_integral_value():
        raise BusinessRuleError(f"{service.name}: the quantity must be a whole number")
    return data.quantity, None, None
