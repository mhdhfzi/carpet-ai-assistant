"""ORM models for the core domain: services, customers, bookings and conversations."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, str_enum

# Money is always NUMERIC (exact decimal), never float.
Money = Numeric(10, 2)

# Size of the embedding vectors (voyage-3.5's default). Changing it needs a migration.
EMBEDDING_DIMENSIONS = 1024


class PricingUnit(StrEnum):
    PER_SQFT = "per_sqft"  # e.g. wall-to-wall carpet, rugs
    PER_ITEM = "per_item"  # e.g. per sofa seat, per mattress
    FLAT = "flat"  # fixed price per job


class BookingStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DONE = "done"
    CANCELLED = "cancelled"


class BookingLocation(StrEnum):
    CUSTOMER_HOME = "customer_home"  # the team visits (collects carpets or cleans on site)
    SHOP = "shop"  # the customer drops the item off; doesn't occupy the team


class Channel(StrEnum):
    WEB = "web"
    WHATSAPP = "whatsapp"


class OwnerRole(StrEnum):
    OWNER = "owner"  # full access
    DEMO = "demo"  # the public demo login: can see everything, change nothing


class MessageRole(StrEnum):
    CUSTOMER = "customer"
    ASSISTANT = "assistant"
    STAFF = "staff"  # a human who took over after a handoff


class UnansweredReason(StrEnum):
    NO_ANSWER = "no_answer"  # the assistant flagged it couldn't answer
    HANDED_OFF = "handed_off"  # the conversation was handed to the owner
    GAVE_UP = "gave_up"  # refusal, or too many tool rounds


class Service(TimestampMixin, Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="unit_price_non_negative"),
        CheckConstraint("minimum_charge >= 0", name="minimum_charge_non_negative"),
        CheckConstraint(
            "unit_price_max IS NULL OR unit_price_max >= unit_price", name="unit_price_range"
        ),
        CheckConstraint("visit_minutes > 0", name="visit_minutes_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    pricing_unit: Mapped[PricingUnit] = mapped_column(str_enum(PricingUnit, "pricing_unit"))
    unit_price: Mapped[Decimal] = mapped_column(Money)
    # Set only when the price varies (e.g. handmade carpet, decided by the owner on
    # inspection); unit_price is then the lower bound. NULL means a fixed price.
    unit_price_max: Mapped[Decimal | None] = mapped_column(Money)
    minimum_charge: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    # How long the team spends at the customer's home: e.g. 30 min to collect a carpet
    # (cleaned at the shop, returned in 5-7 days), 2 hours to clean a sofa on site.
    visit_minutes: Mapped[int] = mapped_column(Integer, default=120, server_default="120")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    # E.164 format (e.g. +60123456789); doubles as the WhatsApp ID, so it must be unique.
    phone: Mapped[str] = mapped_column(String(20), unique=True)
    area: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(Text)

    bookings: Mapped[list["Booking"]] = relationship(back_populates="customer")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="customer")


class Booking(TimestampMixin, Base):
    # The migration also adds ex_bookings_no_overlap, an exclusion constraint that stops two
    # active home visits overlapping (there is one team). SQLAlchemy can't express it here.
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("scheduled_end > scheduled_start", name="end_after_start"),
        CheckConstraint("estimated_price >= 0", name="estimated_price_non_negative"),
        CheckConstraint("estimated_price_max >= estimated_price", name="estimated_price_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    # The chat that produced this booking (if any); used for chat-to-booking analytics.
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), index=True
    )
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    location: Mapped[BookingLocation] = mapped_column(
        str_enum(BookingLocation, "booking_location"),
        default=BookingLocation.CUSTOMER_HOME,
        server_default=BookingLocation.CUSTOMER_HOME.value,
    )
    status: Mapped[BookingStatus] = mapped_column(
        str_enum(BookingStatus, "booking_status"),
        default=BookingStatus.PENDING,
        server_default=BookingStatus.PENDING.value,
    )
    # Estimate range; equal when every item has a fixed price. The final price is set on site.
    estimated_price: Mapped[Decimal] = mapped_column(Money)
    estimated_price_max: Mapped[Decimal] = mapped_column(Money)
    notes: Mapped[str | None] = mapped_column(Text)

    customer: Mapped[Customer] = relationship(back_populates="bookings")
    conversation: Mapped["Conversation | None"] = relationship(back_populates="bookings")
    items: Mapped[list["BookingItem"]] = relationship(
        back_populates="booking", cascade="all, delete-orphan", passive_deletes=True
    )


class BookingItem(Base):
    """One service line on a booking.

    Prices are copied from the Service at booking time, so later price changes don't
    rewrite the history of what the customer was quoted.
    """

    __tablename__ = "booking_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0", name="unit_price_non_negative"),
        CheckConstraint("line_total >= 0", name="line_total_non_negative"),
        CheckConstraint("unit_price_max >= unit_price", name="unit_price_range"),
        CheckConstraint("line_total_max >= line_total", name="line_total_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), index=True
    )
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # sqft or item count
    # Snapshots are always a (min, max) pair, equal for fixed-price services.
    unit_price: Mapped[Decimal] = mapped_column(Money)
    unit_price_max: Mapped[Decimal] = mapped_column(Money)
    line_total: Mapped[Decimal] = mapped_column(Money)
    line_total_max: Mapped[Decimal] = mapped_column(Money)

    booking: Mapped[Booking] = relationship(back_populates="items")
    service: Mapped[Service] = relationship()


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_channel_external_id", "channel", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    channel: Mapped[Channel] = mapped_column(str_enum(Channel, "channel"))
    # WhatsApp number or web session ID: how we find the conversation for an incoming message.
    external_id: Mapped[str] = mapped_column(String(100))
    # Nullable: web visitors are anonymous until they give their details.
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), index=True
    )
    handed_off: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    handoff_reason: Mapped[str | None] = mapped_column(Text)  # why the AI handed over
    # A booking the assistant has summarised to the customer but not yet created, and the
    # customer message it was prepared in reply to. create_booking only runs once a newer
    # customer message exists, i.e. the customer has seen the summary and answered.
    booking_draft: Mapped[dict | None] = mapped_column(JSONB)
    booking_draft_after_message_id: Mapped[int | None] = mapped_column(Integer)

    customer: Mapped[Customer | None] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.id",  # insertion order; timestamps can tie within a transaction
    )
    bookings: Mapped[list[Booking]] = relationship(back_populates="conversation")


class Message(Base):
    """A single chat message. Messages are immutable, so there is no updated_at."""

    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_id_created_at", "conversation_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    role: Mapped[MessageRole] = mapped_column(str_enum(MessageRole, "message_role"))
    content: Mapped[str] = mapped_column(Text)
    # The channel's own message id (e.g. WhatsApp's "wamid..."). Unique, so a webhook
    # delivered twice can't be processed twice.
    external_id: Mapped[str | None] = mapped_column(String(200), unique=True)
    # Assistant replies only: the knowledge chunks the reply cited (shown in the admin view),
    # and whether it cited any. An ungrounded reply means the knowledge base had no answer.
    sources: Mapped[list[dict] | None] = mapped_column(JSONB)
    grounded: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Owner(TimestampMixin, Base):
    """A business owner who can log in to the dashboard. Created with python -m app.create_owner."""

    __tablename__ = "owners"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)  # stored lower-case
    name: Mapped[str] = mapped_column(String(100))
    # Argon2 hash (includes its own salt and parameters); the password itself is never stored.
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[OwnerRole] = mapped_column(
        str_enum(OwnerRole, "owner_role"),
        default=OwnerRole.OWNER,
        server_default=OwnerRole.OWNER.value,
    )


class ClosedDate(Base):
    """A day the business is closed besides Fridays, e.g. a public holiday."""

    __tablename__ = "closed_dates"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    reason: Mapped[str] = mapped_column(String(100), default="")


class KnowledgeChunk(Base):
    """One retrievable piece of the knowledge base (a document section or a price-list entry).

    Rebuilt by `python -m app.ai.ingest`; never edited by hand.
    """

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        # HNSW: approximate nearest-neighbour index, fast even as the knowledge base grows.
        # vector_cosine_ops matches the cosine distance (<=>) used when searching.
        Index(
            "ix_knowledge_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(200))  # e.g. "faq.md", cited in the admin view
    title: Mapped[str] = mapped_column(String(200))
    heading: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    # sha256 of the embedding model + embedded text: lets re-ingestion reuse embeddings for
    # unchanged chunks instead of paying to embed them again.
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UnansweredQuestion(Base):
    """A customer question the assistant couldn't handle: the owner's to-do list for
    improving the knowledge base, shown on the dashboard until marked resolved."""

    __tablename__ = "unanswered_questions"
    __table_args__ = (
        Index("ix_unanswered_questions_resolved_created_at", "resolved", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    # The customer message that asked it (the original wording, in their language).
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    reason: Mapped[UnansweredReason] = mapped_column(
        str_enum(UnansweredReason, "unanswered_reason")
    )
    question: Mapped[str] = mapped_column(Text)  # what was asked, as summarised for the owner
    detail: Mapped[str | None] = mapped_column(Text)  # e.g. the handoff reason
    # Similarity of the best knowledge chunk found: helps tune a confidence threshold later.
    top_score: Mapped[float | None] = mapped_column(Float)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[Conversation] = relationship()


class AssistantPause(Base):
    """When the AI is paused because the provider account ran out of credit (one row, id 1).

    In the database, not in memory: Cloud Run restarts instances often (it scales to zero)
    and may run two at once, and all of them must agree whether the chat is shown.
    """

    __tablename__ = "assistant_pause"

    id: Mapped[int] = mapped_column(primary_key=True)
    paused_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Pauses in a row without a successful reply in between: each one lasts longer.
    consecutive: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reason: Mapped[str | None] = mapped_column(Text)
