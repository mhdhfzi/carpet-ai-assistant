"""Fictional demo data for the owner dashboard: customers, chats and bookings around today.

Run with:  python -m app.seed_demo

Re-running replaces the previous demo data and never touches anything else. Demo
customers use the fake phone range +60 3-0000 0xxx, and demo conversations have
"demo-" ids, which is how earlier demo rows are found. Needs the price list
(python -m app.seed) first.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import (
    Booking,
    BookingItem,
    BookingLocation,
    BookingStatus,
    Channel,
    Conversation,
    Customer,
    Message,
    MessageRole,
    Service,
    UnansweredQuestion,
    UnansweredReason,
)
from app.services import availability, pricing

DEMO_PHONE_PREFIX = "+60300000"
DEMO_CONVERSATION_PREFIX = "demo-"

HOME = BookingLocation.CUSTOMER_HOME
SHOP = BookingLocation.SHOP


def src(source: str, title: str, heading: str, cited: str) -> dict:
    return {"source": source, "title": title, "heading": heading, "cited_text": cited}


PRICES = "price list (services database)"
FAQ = ("faq.md", "Frequently asked questions")
HOURS = ("booking-and-hours.md", "Booking and opening hours")
HOW = ("how-it-works.md", "How each service works")


@dataclass
class Scenario:
    name: str
    area: str
    channel: Channel
    days_ago: int  # when the chat happened
    chat: list[tuple[str, str, list[dict] | None]]  # (role, text, sources for assistant)
    booking: dict | None = None  # day (offset from today), hour, items, status, location
    handoff: str | None = None
    unanswered: list[tuple[UnansweredReason, str]] = field(default_factory=list)


C, A = "customer", "assistant"

SCENARIOS = [
    Scenario(
        "Aminah Rahman",
        "Seremban 2",
        Channel.WEB,
        2,
        [
            (C, "Hi, berapa harga cuci karpet shaggy 6x9 kaki?", None),
            (
                A,
                "Karpet Shaggy RM2.00 sekaki persegi, jadi 54 kps lebih kurang RM108. Harga muktamad selepas karpet diukur.",
                [src(PRICES, "Price list", "Karpet Shaggy", "RM2.00 per square foot")],
            ),
            (C, "Ok boleh ambil Isnin pagi?", None),
            (
                A,
                "Boleh, Isnin 10:00 pagi. Saya dah rekod tempahan anda, pemilik akan hubungi untuk sahkan masa.",
                None,
            ),
        ],
        booking={
            "day": 3,
            "hour": 10,
            "items": [("Karpet Shaggy", 54)],
            "status": BookingStatus.CONFIRMED,
        },
    ),
    Scenario(
        "Lim Wei Jie",
        "Rasah",
        Channel.WHATSAPP,
        15,
        [
            (C, "How much to clean a 3 seater sofa at home?", None),
            (
                A,
                "Sofa cleaning is RM60 per seat, so about RM180 for a 3-seater, done at your home in about 2 hours.",
                [
                    src(PRICES, "Price list", "Cucian Sofa", "RM60.00 per item"),
                    src(
                        *HOW,
                        "How long sofa, mattress and car seat cleaning takes",
                        "usually takes about 2 hours",
                    ),
                ],
            ),
            (C, "Great, book me for Tuesday 2pm", None),
            (
                A,
                "Done! Your booking is received and pending; the owner will contact you to confirm.",
                None,
            ),
        ],
        booking={
            "day": -12,
            "hour": 14,
            "items": [("Cucian Sofa", 3)],
            "status": BookingStatus.DONE,
        },
    ),
    Scenario(
        "Nurul Huda",
        "Nilai",
        Channel.WEB,
        1,
        [
            (C, "Nak cuci tilam queen dengan sofa 2 seater, berapa semua?", None),
            (
                A,
                "Tilam Queen RM140 dan sofa 2 tempat duduk RM120, jumlah anggaran RM260.",
                [
                    src(PRICES, "Price list", "Cucian Tilam Queen", "RM140.00 per item"),
                    src(PRICES, "Price list", "Cucian Sofa", "RM60.00 per item"),
                ],
            ),
            (C, "Ok, Rabu depan pukul 2 petang boleh?", None),
            (A, "Boleh. Tempahan anda direkodkan sebagai menunggu pengesahan pemilik.", None),
        ],
        booking={
            "day": 5,
            "hour": 14,
            "items": [("Cucian Tilam Queen", 1), ("Cucian Sofa", 2)],
            "status": BookingStatus.PENDING,
        },
    ),
    Scenario(
        "Rajesh Kumar",
        "Senawang",
        Channel.WHATSAPP,
        3,
        [
            (C, "I have a handmade Persian rug, about 5x8 ft. Price?", None),
            (
                A,
                "Handmade carpets are RM2.50 to RM4.00 per square foot depending on the material, so roughly RM100 to RM160. The owner confirms after inspecting it.",
                [
                    src(
                        PRICES, "Price list", "Karpet Handmade", "RM2.50 to RM4.00 per square foot"
                    ),
                    src(
                        "services.md",
                        "Services we offer",
                        "Handmade carpet (karpet handmade)",
                        "the owner inspects the carpet",
                    ),
                ],
            ),
            (C, "OK please collect it next week", None),
            (A, "Booked for collection; the owner will contact you to confirm the time.", None),
        ],
        booking={
            "day": 6,
            "hour": 11,
            "items": [("Karpet Handmade", 40)],
            "status": BookingStatus.PENDING,
        },
    ),
    Scenario(
        "Siti Aisyah",
        "Seremban",
        Channel.WEB,
        4,
        [
            (C, "Hari Jumaat buka tak?", None),
            (
                A,
                "Maaf, kami tutup setiap hari Jumaat. Kami buka hari lain dari 9 pagi hingga 5.30 petang.",
                [src(*FAQ, "Are you open on Friday?", "We are closed every Friday")],
            ),
        ],
    ),
    Scenario(
        "Ahmad Faiz",
        "Rantau",
        Channel.WHATSAPP,
        2,
        [
            (
                C,
                "Assalamualaikum, nak tanya harga cuci karpet surau, lebih kurang 600 kaki persegi",
                None,
            ),
            (
                A,
                "Waalaikumussalam. Karpet surau tiada harga tetap; pemilik akan lawat tapak dahulu dan beri sebut harga melalui WhatsApp. Saya dah serahkan butiran kepada pemilik.",
                [
                    src(
                        "services.md",
                        "Services we offer",
                        "Mosque, surau and hall carpets (karpet masjid, surau, dewan)",
                        "the owner visits the site first",
                    )
                ],
            ),
        ],
        handoff="Quote request: surau carpet, about 600 sq ft, Rantau",
        unanswered=[
            (UnansweredReason.HANDED_OFF, "Harga cuci karpet surau, lebih kurang 600 kaki persegi")
        ],
    ),
    Scenario(
        "Tan Mei Ling",
        "Seremban 2",
        Channel.WEB,
        6,
        [
            (C, "Do you clean curtains?", None),
            (A, "I'm not sure about curtains; the owner will get back to you on that.", None),
        ],
        unanswered=[(UnansweredReason.NO_ANSWER, "Do you clean curtains?")],
    ),
    Scenario(
        "Hafiz Ismail",
        "Ampangan",
        Channel.WEB,
        24,
        [
            (C, "Karpet biasa 10x10 kaki berapa?", None),
            (
                A,
                "Karpet Biasa RM1.80 sekaki persegi, 100 kps lebih kurang RM180.",
                [src(PRICES, "Price list", "Karpet Biasa", "RM1.80 per square foot")],
            ),
            (C, "Ok tempah", None),
            (A, "Tempahan diterima, pemilik akan hubungi anda.", None),
        ],
        booking={
            "day": -20,
            "hour": 9,
            "items": [("Karpet Biasa", 100)],
            "status": BookingStatus.DONE,
        },
    ),
    Scenario(
        "Kavitha Raman",
        "Port Dickson",
        Channel.WHATSAPP,
        9,
        [
            (C, "King size mattress cleaning price?", None),
            (
                A,
                "King mattress cleaning is RM160, usually done at your home in about 2 hours.",
                [src(PRICES, "Price list", "Cucian Tilam King", "RM160.00 per item")],
            ),
            (C, "Book Saturday morning", None),
            (A, "Booked; the owner will confirm the time with you.", None),
        ],
        booking={
            "day": -5,
            "hour": 10,
            "items": [("Cucian Tilam King", 1)],
            "status": BookingStatus.CANCELLED,
        },
    ),
    Scenario(
        "Zulkifli Hassan",
        "Seremban",
        Channel.WEB,
        1,
        [
            (C, "Berapa harga cuci seat kereta Honda City?", None),
            (
                A,
                "Harga cuci seat kereta bergantung pada saiz kereta dan disahkan oleh pemilik. Saya dah serahkan kepada pemilik untuk sebut harga.",
                [
                    src(
                        "services.md",
                        "Services we offer",
                        "Car seat cleaning (cuci seat kereta)",
                        "The price depends on the size of the car",
                    )
                ],
            ),
        ],
        handoff="Quote request: car seats, Honda City (sedan)",
        unanswered=[(UnansweredReason.HANDED_OFF, "Berapa harga cuci seat kereta Honda City?")],
    ),
    Scenario(
        "Farah Nadia",
        "Senawang",
        Channel.WEB,
        5,
        [
            (C, "Can I pay by DuitNow QR?", None),
            (
                A,
                "I'm not sure which payment methods are accepted; the owner will get back to you.",
                None,
            ),
        ],
        unanswered=[
            (UnansweredReason.NO_ANSWER, "What payment methods are accepted (e.g. DuitNow QR)?")
        ],
    ),
    Scenario(
        "Daniel Wong",
        "Seremban",
        Channel.WHATSAPP,
        1,
        [
            (C, "Velvet carpet about 80 sq ft, I can drop it at your shop", None),
            (
                A,
                "Karpet Velvet is RM0.90 per square foot, about RM72 for 80 sq ft. You're welcome to drop it off at the shop.",
                [src(PRICES, "Price list", "Karpet Velvet", "RM0.90 per square foot")],
            ),
            (C, "I'll come Monday 11am", None),
            (A, "Noted for Monday 11:00 at the shop; the owner will confirm.", None),
        ],
        booking={
            "day": 2,
            "hour": 11,
            "items": [("Karpet Velvet", 80)],
            "status": BookingStatus.CONFIRMED,
            "location": SHOP,
        },
    ),
    Scenario(
        "Noraini Yusof",
        "Nilai",
        Channel.WEB,
        7,
        [
            (C, "Berapa lama nak siap cuci karpet?", None),
            (
                A,
                "Karpet siap dalam 5 hingga 7 hari selepas diambil.",
                [src(*HOW, "How long carpet cleaning takes", "Carpets are returned 5 to 7 days")],
            ),
        ],
    ),
    Scenario(
        "Arif Daniel",
        "Seremban 2",
        Channel.WHATSAPP,
        6,
        [
            (C, "Tatami 20 sqft and normal carpet 60 sqft, how much?", None),
            (
                A,
                "Karpet Tatami RM18 and Karpet Biasa RM108, about RM126 in total.",
                [
                    src(PRICES, "Price list", "Karpet Tatami", "RM0.90 per square foot"),
                    src(PRICES, "Price list", "Karpet Biasa", "RM1.80 per square foot"),
                ],
            ),
            (C, "Please collect Thursday", None),
            (A, "Booked for collection on Thursday; pending the owner's confirmation.", None),
        ],
        booking={
            "day": -3,
            "hour": 15,
            "items": [("Karpet Tatami", 20), ("Karpet Biasa", 60)],
            "status": BookingStatus.DONE,
        },
    ),
    Scenario(
        "Mei Chen",
        "Rahang",
        Channel.WEB,
        2,
        [
            (C, "The stain on my carpet is still there after your cleaning!", None),
            (
                A,
                "I'm sorry about that. I've passed this to the owner, who will reply to you here soon.",
                None,
            ),
        ],
        handoff="Customer unhappy: stain still visible after carpet cleaning",
        unanswered=[
            (
                UnansweredReason.HANDED_OFF,
                "The stain on my carpet is still there after your cleaning!",
            )
        ],
    ),
]


def seed_demo(db: Session) -> dict[str, int]:
    clear_demo(db)
    services = {s.name: s for s in db.scalars(select(Service))}
    tz = availability.HOURS.timezone
    today = clock.now().astimezone(tz).date()
    counts = {"conversations": 0, "bookings": 0, "unanswered": 0}

    for index, scenario in enumerate(SCENARIOS, start=1):
        customer = Customer(
            name=scenario.name,
            phone=f"{DEMO_PHONE_PREFIX}{index:03d}",
            area=scenario.area,
            address=f"{index}, Jalan Contoh {index}, {scenario.area}" if scenario.booking else None,
        )
        chat_start = datetime.combine(
            today - timedelta(days=scenario.days_ago), time(9, 30), tz
        ) + timedelta(minutes=37 * index)
        conversation = Conversation(
            channel=scenario.channel,
            external_id=f"{DEMO_CONVERSATION_PREFIX}{index}",
            customer=customer,
            handed_off=scenario.handoff is not None,
            handoff_reason=scenario.handoff,
            created_at=chat_start,
        )
        db.add(conversation)
        first_customer_message = None
        for offset, (role, text, sources) in enumerate(scenario.chat):
            message = Message(
                conversation=conversation,
                role=MessageRole(role),
                content=text,
                sources=sources if role == A else None,
                # Replies in a chat that led to a booking came from the booking tools, which counts
                # as grounded in the real agent (see app/ai/agent.py, DATA_TOOLS).
                grounded=(bool(sources) or scenario.booking is not None) if role == A else None,
                created_at=chat_start + timedelta(minutes=offset),
            )
            db.add(message)
            first_customer_message = first_customer_message or (message if role == C else None)
        db.flush()

        for reason, question in scenario.unanswered:
            db.add(
                UnansweredQuestion(
                    conversation=conversation,
                    message_id=first_customer_message.id,
                    reason=reason,
                    question=question,
                    detail=scenario.handoff,
                    top_score=0.41 if reason is UnansweredReason.NO_ANSWER else 0.58,
                    created_at=chat_start,
                )
            )
            counts["unanswered"] += 1

        if scenario.booking:
            db.add(
                _booking(scenario.booking, customer, conversation, services, today, tz, chat_start)
            )
            counts["bookings"] += 1
        counts["conversations"] += 1

    db.commit()
    return counts


def clear_demo(db: Session) -> None:
    demo_customers = select(Customer.id).where(Customer.phone.like(f"{DEMO_PHONE_PREFIX}%"))
    demo_conversations = select(Conversation.id).where(
        Conversation.external_id.like(f"{DEMO_CONVERSATION_PREFIX}%")
    )
    db.execute(
        delete(UnansweredQuestion).where(UnansweredQuestion.conversation_id.in_(demo_conversations))
    )
    db.execute(delete(Booking).where(Booking.customer_id.in_(demo_customers)))  # items cascade
    db.execute(
        delete(Conversation).where(Conversation.id.in_(demo_conversations))
    )  # messages cascade
    db.execute(delete(Customer).where(Customer.id.in_(demo_customers)))
    db.flush()


def _booking(spec, customer, conversation, services, today: date, tz, created_at) -> Booking:
    day = today + timedelta(days=spec["day"])
    if day.weekday() in availability.HOURS.closed_weekdays:  # never on a Friday
        day += timedelta(days=1)
    chosen = [(services[name], Decimal(qty)) for name, qty in spec["items"]]
    start = datetime.combine(day, time(spec["hour"]), tz)
    lines = [(service, qty, pricing.estimate_line(service, qty)) for service, qty in chosen]
    total = pricing.estimate_total(line for _, _, line in lines)
    return Booking(
        customer=customer,
        conversation=conversation,
        scheduled_start=start,
        scheduled_end=start + availability.visit_duration(s for s, _ in chosen),
        location=spec.get("location", HOME),
        status=spec["status"],
        estimated_price=total.low,
        estimated_price_max=total.high,
        created_at=created_at,
        items=[
            BookingItem(
                service=service,
                quantity=qty,
                unit_price=pricing.unit_price_range(service).low,
                unit_price_max=pricing.unit_price_range(service).high,
                line_total=line.low,
                line_total_max=line.high,
            )
            for service, qty, line in lines
        ],
    )


def main() -> None:
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        if not db.scalar(select(Service.id).limit(1)):
            raise SystemExit("No services yet: run python -m app.seed first.")
        counts = seed_demo(db)
    print(
        f"Demo data created: {counts['conversations']} conversations, "
        f"{counts['bookings']} bookings, {counts['unanswered']} unanswered questions."
    )


if __name__ == "__main__":
    main()
