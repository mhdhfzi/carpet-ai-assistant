"""The back office: orders and customers, for the owner and staff (ORDERS_ENABLED)."""

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentOwner, DbSession, RequireOrdersEnabled, RequireOwner
from app.db.models import Customer, Order, OrderStatus
from app.schemas.order import (
    CustomerDetail,
    CustomerSummary,
    OrderCreate,
    OrderCustomerRead,
    OrderEventRead,
    OrderItemRead,
    OrderRead,
    OrderServiceRead,
    OrderUpdate,
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


@router.get("", response_model=list[OrderRead])
def list_orders(
    db: DbSession,
    status: OrderStatus | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> list[OrderRead]:
    """Newest first; filter by status, or find by order number, tag, phone or name."""
    return [to_read(order) for order in orders.list_orders(db, status=status, q=q)]


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


@customers_router.get("", response_model=list[CustomerSummary])
def search_customers(
    db: DbSession, q: Annotated[str, Query(min_length=1, max_length=100)]
) -> list[CustomerSummary]:
    """For the order form (type a phone number) and the customer page."""
    return [
        _summary(customer, count, last) for customer, count, last in orders.search_customers(db, q)
    ]


@customers_router.get("/{customer_id}", response_model=CustomerDetail)
def get_customer(customer_id: int, db: DbSession) -> CustomerDetail:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise NotFoundError(f"Customer {customer_id} not found")
    history = orders.list_orders(db, customer_id=customer.id, limit=500)
    summary = _summary(customer, len(history), history[0].received_on if history else None)
    return CustomerDetail(**summary.model_dump(), order_history=[to_read(o) for o in history])


def _summary(customer: Customer, count: int, last) -> CustomerSummary:
    return CustomerSummary(
        id=customer.id,
        name=customer.name,
        phone=customer.phone,
        area=customer.area,
        address=customer.address,
        orders=count,
        last_order_on=last,
    )


def to_read(order: Order) -> OrderRead:
    totals = orders.totals(order)
    window = orders.ready_window(order)
    return OrderRead(
        id=order.id,
        number=order.number,
        customer=OrderCustomerRead.model_validate(order.customer),
        received_on=order.received_on,
        status=order.status,
        return_method=order.return_method,
        deposit=order.deposit,
        discount=order.discount,
        notes=order.notes,
        washed_on=order.washed_on,
        ready_on=order.ready_on,
        completed_on=order.completed_on,
        ready_from=window[0] if window else None,
        ready_by=window[1] if window else None,
        price_pending=totals.price_pending,
        subtotal=totals.subtotal,
        total=totals.total,
        balance=totals.balance,
        items=[
            OrderItemRead(
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
            )
            for item in order.items
        ],
        events=[
            OrderEventRead(
                status=event.status,
                note=event.note,
                by=event.by.name if event.by else None,
                at=event.created_at,
            )
            for event in order.events
        ],
        created_at=order.created_at,
    )
