"""The back office: orders, customers and the day's work, for the owner and staff
(ORDERS_ENABLED)."""

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.business import initials
from app.api.deps import CurrentOwner, DbSession, RequireOrdersEnabled, RequireOwner
from app.core.config import get_settings
from app.db.models import Customer, ItemStatus, Order, OrderItem, OrderStatus, UntaggedItem
from app.schemas.order import (
    CustomerDetail,
    CustomerSummary,
    ItemStatusUpdate,
    OrderCreate,
    OrderCustomerRead,
    OrderEventRead,
    OrderItemRead,
    OrderRead,
    OrderServiceRead,
    OrderUpdate,
    PaymentIn,
    PaymentRead,
    PaymentVoid,
    ReceiptBusiness,
    ReceiptRead,
    UntaggedIn,
    UntaggedMatch,
    UntaggedRead,
    WorkItemRead,
    WorkLogRead,
    WorkSummaryRead,
)
from app.services import orders
from app.services.errors import NotFoundError

# The owner check runs first, so a visitor gets 401 whether or not the back office is on.
router = APIRouter(
    prefix="/api/orders", tags=["orders"], dependencies=[RequireOwner, RequireOrdersEnabled]
)
customers_router = APIRouter(
    prefix="/api/customers", tags=["orders"], dependencies=[RequireOwner, RequireOrdersEnabled]
)
work_router = APIRouter(
    prefix="/api/work", tags=["orders"], dependencies=[RequireOwner, RequireOrdersEnabled]
)


@router.get("", response_model=list[OrderRead])
def list_orders(
    db: DbSession,
    status: Annotated[list[OrderStatus] | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> list[OrderRead]:
    """Newest first; filter by one or more statuses (?status=completed&status=cancelled for
    the history), or find by order number, tag, phone or name."""
    return [to_read(order) for order in orders.list_orders(db, statuses=status or (), q=q)]


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def create_order(data: OrderCreate, db: DbSession, actor: CurrentOwner) -> OrderRead:
    return to_read(orders.create_order(db, data, actor))


@router.get("/{order_id}", response_model=OrderRead)
def get_order(order_id: int, db: DbSession) -> OrderRead:
    return to_read(orders.get_order(db, order_id))


@router.patch("/{order_id}", response_model=OrderRead)
def update_order(order_id: int, data: OrderUpdate, db: DbSession, actor: CurrentOwner) -> OrderRead:
    order = orders.get_order(db, order_id)
    return to_read(orders.update_order(db, order, data, actor))


@router.patch("/{order_id}/items/{item_id}", response_model=OrderRead)
def update_item_status(
    order_id: int, item_id: int, data: ItemStatusUpdate, db: DbSession, actor: CurrentOwner
) -> OrderRead:
    """Move one carpet along (dicuci, siap). The order follows its slowest item."""
    order = orders.get_order(db, order_id)
    return to_read(
        orders.update_item_status(db, order, item_id, data.status, data.note, actor, data.fold)
    )


@router.post("/{order_id}/payments", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def record_payment(order_id: int, data: PaymentIn, db: DbSession, actor: CurrentOwner) -> OrderRead:
    """Money received (staff may record it, e.g. cash at pickup)."""
    order = orders.get_order(db, order_id)
    return to_read(orders.record_payment(db, order, data, actor))


@router.post("/{order_id}/payments/{payment_id}/void", response_model=OrderRead)
def void_payment(
    order_id: int, payment_id: int, data: PaymentVoid, db: DbSession, actor: CurrentOwner
) -> OrderRead:
    """Owner only: mark a wrongly recorded payment void. It stays on record."""
    order = orders.get_order(db, order_id)
    return to_read(orders.void_payment(db, order, payment_id, data.reason, actor))


@router.get("/{order_id}/receipt", response_model=ReceiptRead)
def receipt(order_id: int, db: DbSession) -> ReceiptRead:
    """What a printed receipt shows: the business's details and the order."""
    settings = get_settings()
    name = settings.receipt_name or settings.business_name
    return ReceiptRead(
        business=ReceiptBusiness(
            name=name,
            logo=settings.receipt_logo or initials(name),
            reg_no=settings.business_reg_no,
            address=settings.business_address,
            phone=settings.business_phones or settings.contact_whatsapp or "",
            email=settings.business_email,
            facebook=settings.business_facebook,
            payment_details=settings.payment_details,
            terms=settings.receipt_terms,
        ),
        order=to_read(orders.get_order(db, order_id)),
        issued_on=orders.today(),
    )


@work_router.get("/items", response_model=list[WorkItemRead])
def work_items(
    db: DbSession, status: Annotated[ItemStatus, Query()] = ItemStatus.RECEIVED
) -> list[WorkItemRead]:
    """The washing list (?status=received) or the packing list (?status=washed)."""
    return [_work_item(item) for item in orders.work_items(db, status)]


@work_router.get("/summary", response_model=WorkSummaryRead)
def work_summary(db: DbSession) -> WorkSummaryRead:
    """The cards at the top: to wash, ready to pack, waiting for pickup, still unpaid."""
    summary = orders.work_summary(db)
    return WorkSummaryRead(**summary.__dict__)


@work_router.get("/untagged", response_model=list[UntaggedRead])
def list_untagged(db: DbSession) -> list[UntaggedRead]:
    """Carpets found without a tag ("XXX"), not yet matched to an order."""
    return [_untagged(u) for u in orders.list_untagged(db)]


@work_router.post("/untagged", response_model=UntaggedRead, status_code=status.HTTP_201_CREATED)
def log_untagged(data: UntaggedIn, db: DbSession, actor: CurrentOwner) -> UntaggedRead:
    return _untagged(orders.log_untagged(db, data.description, actor))


@work_router.post("/untagged/{untagged_id}/match", response_model=UntaggedRead)
def match_untagged(
    untagged_id: int, data: UntaggedMatch, db: DbSession, actor: CurrentOwner
) -> UntaggedRead:
    """It's been recognised: record which tag it is."""
    return _untagged(orders.match_untagged(db, untagged_id, data.tag, actor))


def _untagged(item: UntaggedItem) -> UntaggedRead:
    return UntaggedRead(
        id=item.id,
        description=item.description,
        found_on=item.found_on,
        found_by=item.found_by.name if item.found_by else None,
        matched_tag=item.matched_tag,
    )


@work_router.get("/log", response_model=WorkLogRead)
def work_log(db: DbSession, day: Annotated[date | None, Query()] = None) -> WorkLogRead:
    """What was washed and packed on a day (default today), and by whom: the paper forms."""
    day = day or orders.today()
    washed, packed = orders.work_log(db, day)
    return WorkLogRead(
        day=day, washed=[_work_item(i) for i in washed], packed=[_work_item(i) for i in packed]
    )


def _work_item(item: OrderItem) -> WorkItemRead:
    order = item.order
    return WorkItemRead(
        **_item_read(order, item).model_dump(),
        order_id=order.id,
        order_number=order.number,
        customer_name=order.customer.name,
        received_on=order.received_on,
    )


@customers_router.get("", response_model=list[CustomerSummary])
def list_customers(
    db: DbSession,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CustomerSummary]:
    """All customers, most recent first (the customer table), or those matching a name or
    phone (the order form's lookup)."""
    return [
        _summary(row.customer, row.orders, row.last_order_on, row.total_value, row.unpaid)
        for row in orders.list_customers(db, q, limit=limit, offset=offset)
    ]


@customers_router.get("/{customer_id}", response_model=CustomerDetail)
def get_customer(customer_id: int, db: DbSession) -> CustomerDetail:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise NotFoundError(f"Customer {customer_id} not found")
    history = [to_read(o) for o in orders.list_orders(db, customer_id=customer.id, limit=500)]
    counted = [o for o in history if o.status is not OrderStatus.CANCELLED]
    value = sum((o.total for o in counted), Decimal(0))
    unpaid = sum((max(o.balance, Decimal(0)) for o in counted), Decimal(0))
    last = max((o.received_on for o in history), default=None)
    summary = _summary(customer, len(history), last, value, unpaid)
    return CustomerDetail(**summary.model_dump(), order_history=history)


def _summary(
    customer: Customer, count: int, last: date | None, total_value: Decimal, unpaid: Decimal
) -> CustomerSummary:
    return CustomerSummary(
        id=customer.id,
        name=customer.name,
        phone=customer.phone,
        area=customer.area,
        address=customer.address,
        orders=count,
        last_order_on=last,
        total_value=total_value,
        unpaid=unpaid,
    )


def to_read(order: Order) -> OrderRead:
    totals = orders.totals(order)
    window = orders.ready_window(order)
    washed, ready = orders.progress(order)
    return OrderRead(
        id=order.id,
        number=order.number,
        customer=OrderCustomerRead.model_validate(order.customer),
        received_on=order.received_on,
        status=order.status,
        return_method=order.return_method,
        discount=order.discount,
        notes=order.notes,
        washed_on=order.washed_on,
        ready_on=order.ready_on,
        completed_on=order.completed_on,
        ready_from=window[0] if window else None,
        ready_by=window[1] if window else None,
        items_washed=washed,
        items_ready=ready,
        price_pending=totals.price_pending,
        subtotal=totals.subtotal,
        total=totals.total,
        paid=totals.paid,
        balance=totals.balance,
        payments=[
            PaymentRead(
                id=p.id,
                amount=p.amount,
                method=p.method,
                paid_on=p.paid_on,
                note=p.note,
                received_by=p.received_by.name if p.received_by else None,
                voided=p.voided_at is not None,
                void_reason=p.void_reason,
            )
            for p in order.payments
        ],
        items=[_item_read(order, item) for item in order.items],
        events=[
            OrderEventRead(
                status=event.status,
                item_tag=event.item_tag,
                note=event.note,
                by=event.by.name if event.by else None,
                at=event.created_at,
            )
            for event in order.events
        ],
        created_at=order.created_at,
    )


def _item_read(order: Order, item: OrderItem) -> OrderItemRead:
    window = orders.item_ready_window(item)
    return OrderItemRead(
        id=item.id,
        position=item.position,
        tag=orders.tag(order, item),
        service=OrderServiceRead.model_validate(item.service),
        length_ft=item.length_ft,
        width_ft=item.width_ft,
        quantity=item.quantity,
        unit_price=item.unit_price,
        line_total=orders.line_total(item),
        notes=item.notes,
        status=item.status,
        washed_on=item.washed_on,
        washed_by=item.washed_by.name if item.washed_by else None,
        wash_note=item.wash_note,
        ready_on=item.ready_on,
        packed_by=item.packed_by.name if item.packed_by else None,
        fold=item.fold,
        ready_from=window[0] if window else None,
        ready_by=window[1] if window else None,
    )
