# Kilau AI Assistant

[![CI](https://github.com/mhdhfzi/carpet-ai-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/mhdhfzi/carpet-ai-assistant/actions/workflows/ci.yml)

An AI customer assistant for a small carpet-cleaning business in Malaysia. Customers chat on the website or WhatsApp, in English or Bahasa Melayu; the assistant answers from the business's own documents with citations, prices jobs from the real price list, finds free slots and books them once the customer confirms. The owner gets a dashboard with every booking, the chat behind it, and what customers keep asking.

**Live demo: https://kilau-918469824880.asia-southeast1.run.app**

- Chat: open the widget on the landing page (example questions in EN and BM are one click away).
- Owner dashboard: [`/admin.html`](https://kilau-918469824880.asia-southeast1.run.app/admin.html), **Try the demo account** (or `demo@example.com` / `kilau-demo-2026`). It is read-only and the data resets every night.
- Demo video: _to be added_

> Kilau Carpet Care is fictional (inspired by a real family-run business). It's a portfolio project: applied AI (RAG + tool calling), backend engineering, cloud deployment and DevOps.

## The problem

A small cleaning business gets most of its enquiries on WhatsApp, often in the evening and in a mix of Malay and English. Most are the same few questions (how much for my carpet, are you open on Friday, can you come on Saturday), and the owner answers them one by one between jobs. Slow replies lose bookings, and nobody keeps track of what customers ask or which chats turn into work.

An assistant helps only if it can be trusted: it must never invent a price or a policy, must not book a slot that isn't free or that the customer didn't agree to, and must know when to pass the conversation to a person.

## What it does

| | |
|---|---|
| **Answers with sources** | Retrieval-augmented generation over the business's documents (services, pricing, FAQ, policies). Replies cite the passages they used; the owner sees the citations. |
| **Quotes and books** | Claude calls tools (`get_services`, `estimate_price`, `check_availability`, `prepare_booking`, `create_booking`) backed by tested business logic: price ranges, opening hours, Friday closing, 2 days' notice, one team, no double bookings. |
| **Confirms first** | `create_booking` takes no input: it books exactly what `prepare_booking` summarised, and only after a newer customer message (the confirmation). The model can't skip the step or change details on the way. |
| **Hands off** | Upset customers, out-of-scope requests and low-confidence answers go to the owner. Questions it couldn't answer are logged for the dashboard. |
| **Two channels** | An embeddable web widget (one `<script>` tag, shadow DOM) and a WhatsApp Business webhook (signature-verified, deduplicated). |
| **Owner dashboard** | Bookings with status changes, the chat behind each booking, and analytics: chat-to-booking conversion by channel, busy days, common topics, unanswered questions. |

## Screenshots

The conversations below are the seeded demo data that the live demo resets to every night, shown in the real widget and dashboard.

| Chat widget | Booking with its chat and citations |
|---|---|
| ![Chat widget on the landing page](docs/screenshots/chat-widget.png) | ![Booking detail in the owner dashboard](docs/screenshots/booking-detail.png) |

![Analytics dashboard](docs/screenshots/analytics.png)

## Architecture

```mermaid
flowchart LR
    subgraph Clients
        W["Web chat widget<br/>(React, shadow DOM)"]
        WA["WhatsApp"]
        D["Owner dashboard<br/>(React)"]
    end

    subgraph CR["Google Cloud Run: one container"]
        API["FastAPI<br/>rate limits · JWT auth · request IDs"]
        AG["Agent loop"]
        SV["Services<br/>pricing · availability · bookings"]
        ST["Built frontend<br/>(static files)"]
    end

    WA -- "webhook (HMAC-signed)" --> API
    W --> API
    D --> API
    API --> AG
    AG -- "tool calls" --> SV
    AG -- "chat + tool use" --> CL["Claude API"]
    AG -- "embed query" --> VY["Voyage AI"]
    SV --> DB[("Neon Postgres<br/>+ pgvector")]
    AG -- "vector search" --> DB
    API --> ST
    API -- "replies" --> MetaAPI["WhatsApp Cloud API"]
```

One customer message, end to end:

```mermaid
sequenceDiagram
    participant C as Customer
    participant API as FastAPI
    participant A as Agent loop
    participant DB as Postgres + pgvector
    participant L as Claude

    C->>API: "Berapa harga cuci karpet shaggy 6x9?"
    API->>A: conversation so far
    A->>DB: top 5 chunks by cosine similarity
    A->>L: system rules + chunks as citable documents + tools
    L-->>A: tool_use: estimate_price(shaggy, 54 sq ft)
    A->>DB: price list (server-side pricing)
    A->>L: tool_result: RM108
    L-->>A: reply with citations
    A->>DB: store message, sources, grounded flag
    API-->>C: "Karpet Shaggy RM2.00 sekaki persegi, jadi lebih kurang RM108..."
```

### Design decisions

- **Prices come from code, not the model.** The model picks the service and the size; `estimate_price` computes the number from the database. A hallucinated price is impossible by construction, and the pricing rules have their own unit tests.
- **A hand-written agent loop behind a `ChatModel` interface.** Tools need request context (database session, conversation, which customer message is being answered), and the interface keeps the loop provider-neutral and testable with a scripted fake model. Capped at 6 tool rounds so a confused model can't loop (or bill) forever.
- **Booking confirmation enforced by the server, not the prompt.** Prompts are guidance; the rule "book only what the customer confirmed" is enforced in `create_booking` itself.
- **"Grounded" is a structured signal.** A reply counts as grounded if it cited the knowledge base or used a data tool. Ungrounded replies and hand-offs feed the unanswered-questions log, which shows the owner what to add to the documents.
- **pgvector instead of a separate vector database.** Embeddings live next to the business data in Postgres (HNSW cosine index): one database to run, back up and migrate. Re-ingestion reuses embeddings for unchanged chunks.
- **No double bookings at the database level.** A Postgres exclusion constraint rejects overlapping visits even if two requests race past the application check.
- **Deny-by-default authorization.** Every route that isn't on an explicit public list needs a login, and the read-only demo role is refused every non-GET request in one place. Both rules are tested by enumerating every route in the OpenAPI schema, so a new endpoint can't be forgotten.
- **Costs are capped.** Per-IP rate limits on chat and login, a daily cap on AI replies (counted in the database, so it holds across instances), and Cloud Run scales from 0 to at most 2 instances.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| Database | PostgreSQL + pgvector (Neon in production) |
| AI | Claude (tool calling, citations) via the Anthropic SDK; Voyage AI embeddings |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS |
| Messaging | WhatsApp Business Cloud API |
| Auth | Argon2id password hashes, JWT (HS256) |
| Infra | Docker, GitHub Actions, Google Cloud Run, Artifact Registry, Secret Manager, Cloud Scheduler |
| Tests | pytest (300+ tests against a real Postgres), Vitest + Testing Library |

## Testing

- **Backend:** pytest against a real Postgres + pgvector (the same image as production). The tests cover pricing and availability rules, the agent loop with a scripted fake model (tool calls, confirmation step, hand-off, tool-round cap), the WhatsApp signature check and deduplication, auth (forged, expired and `alg: none` tokens, route protection), rate limits, the daily AI cap and a migration round-trip with a model/migration drift check.
- **Frontend:** Vitest and Testing Library for the widget (sending, retrying, restoring history, the hand-off notice, keyboard use) and the dashboard (login, session expiry, filters, status changes, demo mode, charts with table views).
- **CI:** every pull request runs lint, format check, type check, both test suites and a production image build.

## Running locally

Requires Docker, Python 3.12+ and Node.js 22+.

```bash
# Database (Postgres 16 + pgvector)
cp .env.example .env
docker compose up -d

# Backend
cd backend
cp .env.example .env            # then fill in JWT_SECRET and the API keys
python -m venv .venv
.venv/Scripts/activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -e ".[dev]"
alembic upgrade head           # apply database migrations
python -m app.seed             # load the service price list (safe to re-run)
python -m app.ai.ingest        # embed knowledge docs + prices (needs VOYAGE_API_KEY in .env)
python -m app.create_owner owner@example.com "Owner Name"  # dashboard login (prompts for a password)
python -m app.seed_demo        # optional: fictional chats and bookings, plus the read-only demo login
python -m app.ai.ask           # chat with the assistant in the terminal (needs ANTHROPIC_API_KEY)
ruff check . && ruff format --check .
pytest                         # needs the database running; uses a separate carpet_test DB
uvicorn app.main:app --reload  # API docs at http://127.0.0.1:8000/docs
```

```bash
# Chat widget and owner dashboard (frontend/)
cd frontend
npm install
npm run dev                    # landing page at http://localhost:5173, dashboard at /admin.html
                               # (both proxy /api to the backend)
npm run lint && npm run typecheck && npm test
npm run build                  # -> dist/ (landing + dashboard) and dist/widget.js (embeddable)
```

Embed the widget on any site:

```html
<script src="https://<host>/widget.js" data-api="https://<backend>" data-offset-bottom="92" defer></script>
```

A page can also open it from its own button, optionally with a question typed in:

```js
window.dispatchEvent(new CustomEvent('kilau-chat:open', { detail: { message: 'How much for a sofa?' } }))
```

### Production image

One Docker image (multi-stage, non-root) runs the API and serves the built frontend from the same origin:

```bash
docker compose --profile app run --rm app alembic upgrade head   # migrations
docker compose --profile app up --build                          # http://localhost:8080
```

## Deployment (Google Cloud Run + Neon)

| Piece | Where |
|---|---|
| App (API + frontend) | Cloud Run service `kilau`, `asia-southeast1`, 0–2 instances (scales to zero) |
| Database | Neon Postgres (Singapore), pooled connection, pgvector |
| Images | Artifact Registry `asia-southeast1-docker.pkg.dev/kilau-assistant/kilau/app:<git sha>` |
| Secrets | Secret Manager: `database-url`, `jwt-secret`, `voyage-api-key`, `anthropic-api-key` |
| Migrations / one-off commands | Cloud Run jobs `migrate` (`alembic upgrade head`) and `manage` (`python -m ...`) |
| Nightly demo reset | Cloud Scheduler `demo-reset-nightly` (03:00 MYT) runs the `demo-reset` job: `python -m app.seed_demo --reset` |

**Continuous deployment.** On every push to `main`, CI runs the tests, then builds the image, pushes it, runs the `migrate` job and rolls Cloud Run onto the new image. Migrations run before the new code goes live, so they must stay compatible with the code still serving (add first, remove in a later release). GitHub authenticates through Workload Identity Federation (no stored key; only this repository is trusted) as `github-deployer`, which can push images and deploy but not read secrets. The app runs as `kilau-run`, which can only read its secrets.

**Public demo.** Owners have a role, and the auth dependency refuses every non-GET request from the `demo` role with 403. Because that login is public, the nightly reset deletes every customer, chat and booking and re-seeds the fictional demo data, so nothing a visitor types stays visible for more than a day.

Env vars, secrets and scaling belong to the service and carry over between deploys. To change them, or to run a one-off command against production:

```bash
gcloud run services update kilau --region asia-southeast1 --update-secrets ANTHROPIC_API_KEY=anthropic-api-key:latest
gcloud run jobs execute manage --region asia-southeast1 --args=-m,app.seed_demo --wait
```

Neon runs Postgres 18; CI tests against 16. The app uses nothing that differs between them.

## What I'd improve next

- **An evaluation set for the assistant.** The agent is tested with a scripted fake model, which proves the plumbing but not the answers. Next: a fixed set of real-style questions in BM, EN and a mix of both, with expected facts, tool calls and hand-offs, scored automatically on every prompt or model change.
- **Hybrid retrieval.** Add keyword search alongside vectors, so exact service names and Malay spelling variants ("tilam", "tilam queen", "mattress") match reliably.
- **Streaming replies** in the widget (server-sent events), so long answers start appearing at once.
- **Replying from the dashboard** after a hand-off, instead of the owner switching to WhatsApp.
- **WhatsApp templates** for booking confirmations and next-day reminders (messages outside the 24-hour window need approved templates).
- **A shared rate-limit store** (Redis) if the service ever runs more than a couple of instances; limits are per instance today.
- **Infrastructure as code** (Terraform) for the Cloud Run, IAM and scheduler setup, which is currently a documented series of `gcloud` commands, plus a staging environment.
- **Tracing and alerts:** OpenTelemetry traces across the agent loop and alerts on error rate and AI spend.
