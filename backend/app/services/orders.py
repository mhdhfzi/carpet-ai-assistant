"""Orders: the back office that replaces the owner's book.

Rules live here, not in the dashboard, so they hold whoever calls the API:
- order numbers run 1, 2, 3, ... with no repeats, even when two people save at once
- prices come from the price list and are copied onto each item when recorded
- staff record orders and move them one step along; the owner can set prices and
  discounts, cancel, and correct a status
- payments are never edited or deleted: the owner voids a wrong one, with a reason
- each item (each tagged carpet) is washed and dries on its own; the order follows its
  slowest item, and is handed back only when every item is dry
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
# Moving the whole order to a step moves its items there (handed back = all dry).
ITEM_STEP = {
    OrderStatus.RECEIVED: ItemStatus.RECEIVED,
    OrderStatus.WASHED: ItemStatus.WASHED,
    OrderStatus.READY: ItemStatus.READY,
    OrderStatus.COMPLETED: ItemStatus.READY,
}
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
    """When the carpets should all be dry: 5-7 days after the last one was washed."""
    carpets = [i for i in order.items if i.service.pricing_unit is PricingUnit.PER_SQFT]
    if not carpets or any(i.washed_on is None for i in carpets):
        return None
    if all(i.status is ItemStatus.READY for i in carpets):
        return None
    return item_ready_window(max(carpets, key=lambda i: i.washed_on))


def item_ready_window(item: OrderItem) -> tuple[date, date] | None:
    """When one washed carpet should be dry."""
    if item.washed_on is None or item.status is not ItemStatus.WASHED:
        return None
    if item.service.pricing_unit is not PricingUnit.PER_SQFT:
        return None
    return item.washed_on + timedelta(days=DRYING_DAYS[0]), item.washed_on + timedelta(
        days=DRYING_DAYS[1]
    )


def progress(order: Order) -> tuple[int, int]:
    """(items washed or dry, items dry): shown as "2 / 3 siap" on the order list."""
    washed = sum(1 for i in order.items if i.status is not ItemStatus.RECEIVED)
    ready = sum(1 for i in order.items if i.status is ItemStatus.READY)
    return washed, ready


def tag(order: Order, item: OrderItem) -> str:
    return f"{order.number}-{item.position}"


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
) -> Order:
    """Move one carpet along (e.g. "412-2 dicuci"). Staff go one step forward; going back is
    a correction for the owner. The order then follows its slowest item."""
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
    _move_item(item, new)
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
                _move_item(item, ITEM_STEPS[target])
    order.status = new
    _set_step_dates(order, new)
    order.events.append(OrderEvent(status=new, note=note, by_id=actor.id))
    _follow_items(order)


def _rank(status: OrderStatus) -> int:
    """How far along an order is; a cancelled one counts as not started."""
    path = [OrderStatus.RECEIVED, OrderStatus.WASHED, OrderStatus.READY, OrderStatus.COMPLETED]
    return path.index(status) if status in path else 0


def _move_item(item: OrderItem, new: ItemStatus) -> None:
    """Set an item's step, recording the day each step was reached (going back clears)."""
    reached = ITEM_STEPS.index(new)
    item.status = new
    item.washed_on = (item.washed_on or today()) if reached >= 1 else None
    item.ready_on = (item.ready_on or today()) if reached >= 2 else None


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
            built[-1].status = before.status
            built[-1].washed_on = before.washed_on
            built[-1].ready_on = before.ready_on
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
