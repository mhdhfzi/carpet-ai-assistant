from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.ingest import ingest
from app.ai.llm import Citation, ModelTurn
from app.db.models import Booking, Conversation, Customer
from app.seed import seed_services
from app.seed_demo import DEMO_PHONE_PREFIX, SCENARIOS, seed_demo
from app.services.availability import HOURS
from tests.fakes import FakeChatModel, FakeEmbedder
from tests.test_ingest import write_doc


def test_owner_sees_the_full_transcript_with_sources(
    client: TestClient,
    db: Session,
    fake_llm: FakeChatModel,
    fake_embedder: FakeEmbedder,
    tmp_path: Path,
) -> None:
    write_doc(tmp_path, "hours.md", {"Opening hours": "We are closed on Fridays."})
    ingest(db, fake_embedder, tmp_path)
    fake_llm.script.append(ModelTurn("Closed on Fridays.", citations=[Citation(0, "closed")]))
    session = client.post("/api/chat", json={"message": "Open Friday?"}).json()["session_id"]
    conversation_id = db.scalar(select(Conversation.id).where(Conversation.external_id == session))

    body = client.get(f"/api/conversations/{conversation_id}").json()

    assert body["channel"] == "web"
    assert body["handed_off"] is False
    customer, reply = body["messages"]
    assert (customer["role"], customer["content"], customer["sources"]) == (
        "customer",
        "Open Friday?",
        None,
    )
    assert reply["grounded"] is True
    assert reply["sources"][0]["heading"] == "Opening hours"


def test_missing_conversation_is_404(client: TestClient) -> None:
    assert client.get("/api/conversations/999999").status_code == 404


# --- Demo data -------------------------------------------------------------------------------


def test_demo_data_is_created_and_linked(client: TestClient, db: Session) -> None:
    seed_services(db)

    counts = seed_demo(db)

    assert counts["conversations"] == len(SCENARIOS)
    assert counts["bookings"] == sum(1 for s in SCENARIOS if s.booking)
    bookings = client.get("/api/bookings", params={"limit": 100}).json()
    assert len(bookings) == counts["bookings"]
    assert all(b["conversation_id"] for b in bookings)  # every demo booking came from a chat
    # Never on a Friday (the business is closed), whatever day the seed runs.
    assert all(
        b.scheduled_start.astimezone(HOURS.timezone).weekday() != 4
        for b in db.scalars(select(Booking))
    )
    chat = client.get(f"/api/conversations/{bookings[0]['conversation_id']}").json()
    assert chat["customer"]["phone"].startswith(DEMO_PHONE_PREFIX)
    assert chat["messages"]


def test_demo_seed_replaces_itself_and_keeps_real_data(db: Session) -> None:
    seed_services(db)
    real = Customer(name="Real Customer", phone="+60123456789")
    db.add(real)
    db.flush()

    seed_demo(db)
    seed_demo(db)

    demo = db.scalar(
        select(func.count())
        .select_from(Customer)
        .where(Customer.phone.like(f"{DEMO_PHONE_PREFIX}%"))
    )
    assert demo == len(SCENARIOS)
    assert db.get(Customer, real.id) is not None
