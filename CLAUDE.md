# AI Service Assistant (working name)

A personal portfolio project: an AI customer assistant for a small home-service business (carpet cleaning, based in Negeri Sembilan, Malaysia). Customers chat with it on the web or WhatsApp to ask about services and pricing, get estimates, and book jobs. The owner gets an admin dashboard with insights.

This is **not** my university final-year project. It is a separate portfolio piece meant to show employers skills in **applied AI (RAG + tool calling), backend engineering, cloud deployment and DevOps**.

## Goals

- A working, deployed product that recruiters can open and try via a live link
- Clean, well-tested, well-documented code that I can explain in an interview
- Production practices: Docker, CI/CD, auth, logging, rate limiting, tests

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic (migrations), Pydantic v2 |
| Database | PostgreSQL 16 + pgvector (for embeddings) |
| AI | Claude (Anthropic API) for chat + tool calling; Voyage AI embeddings for RAG. Both behind interfaces so providers can be swapped |
| Frontend | React + TypeScript (Vite), Tailwind CSS: web chat widget + admin dashboard |
| Messaging | WhatsApp Business Cloud API (webhook) |
| Infra | Docker + docker-compose for local dev; GitHub Actions for CI/CD; deploy to AWS (or GCP/Azure) |
| Testing | pytest (backend), Vitest (frontend) |

## Folder structure (target)

```
.
├── CLAUDE.md
├── README.md
├── docker-compose.yml
├── .github/workflows/        # CI/CD pipelines
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/              # FastAPI routers (chat, bookings, admin, whatsapp webhook)
│   │   ├── core/             # config, security, logging
│   │   ├── db/               # models, session, migrations
│   │   ├── services/         # business logic (pricing, availability, bookings)
│   │   ├── ai/               # LLM client, RAG retrieval, tool definitions, agent loop
│   │   └── schemas/          # Pydantic models
│   ├── knowledge/            # business documents for RAG (services, pricing, FAQ, policies)
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
└── frontend/
    ├── src/
    │   ├── chat/             # customer chat widget
    │   └── admin/            # owner dashboard
    ├── Dockerfile
    └── package.json
```

## Core domain

- **Service**: name, description, pricing rule (e.g. per square foot, by carpet type, minimum charge)
- **Customer**: name, phone (WhatsApp number), area/address
- **Booking**: customer, service(s), date/time slot, estimated price, status (pending / confirmed / done / cancelled)
- **Conversation / Message**: channel (web or whatsapp), messages, whether the AI handed off to a human
- **Unanswered question log**: questions the AI could not answer confidently (feeds the dashboard)

## AI behaviour rules

- Answer only from the knowledge base and tool results; never invent prices, services or policies
- Cite which document an answer came from (shown in the admin view)
- **Always confirm details with the customer before creating a booking**
- Hand off to a human when confidence is low, the customer is upset, or the request is out of scope
- Support English and Bahasa Melayu (customers may mix both)
- Never expose other customers' data

## Build plan

Work through these phases in order. Tick items off as they are done.

### Phase 1: Backend and data
- [x] Project scaffold, pyproject, linting (ruff), formatting
- [x] docker-compose with Postgres + pgvector
- [x] Models + Alembic migrations for Service, Customer, Booking, Conversation, Message
- [x] CRUD endpoints for services and bookings
- [x] Pricing service (estimate from carpet size/type) with unit tests
- [x] Availability service (free slots) with unit tests

### Phase 2: RAG chatbot
- [x] Write knowledge documents in `backend/knowledge/`
- [x] Ingestion script: chunk → embed → store in pgvector
- [x] Retrieval + answer generation with sources
- [x] `/chat` endpoint; tests with a mocked LLM

### Phase 3: Tool calling (agent)
- [x] Tools: `get_services`, `estimate_price`, `check_availability`, `create_booking` (with `prepare_booking`), `handoff_to_human`
- [x] Agent loop with confirmation step before `create_booking`
- [x] Log low-confidence / unanswered questions
- [x] Tests for the tool-calling flow

### Phase 4: Channels
- [x] React web chat widget (embeddable `widget.js`)
- [x] WhatsApp webhook (verify signature, handle incoming/outgoing messages)

### Phase 5: Admin dashboard
- [x] Owner login (JWT auth)
- [x] Bookings list and status updates
- [ ] Analytics: common questions, chat-to-booking conversion, busy days, unanswered questions

### Phase 6: Production-grade
- [ ] GitHub Actions: lint + test on every PR; build and deploy on main
- [ ] Cloud deployment with environment-based config and secrets
- [ ] Rate limiting, structured logging, error handling
- [ ] README: problem, architecture diagram, screenshots, live link, demo video, "what I'd improve next"

## How to work with me (instructions for Claude)

- I'm a final-year computer science student building this to learn and to show in interviews. **Briefly explain important design decisions** so I can defend them in an interview.
- Work in small, reviewable steps. Finish one checklist item, run the tests, then move on.
- Ask me before making big architectural changes or adding a major new dependency.
- Keep tests passing; add tests for new business logic.
- Never commit secrets. Use `.env` (gitignored) and provide `.env.example`.
- Use clear commit messages (e.g. `feat: add pricing service`).
- Update the checklist in this file as items are completed.
