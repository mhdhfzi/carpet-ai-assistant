# carpet-ai-assistant
AI customer assistant for a home-service business: RAG + LLM tool calling, FastAPI, PostgreSQL/pgvector, React, WhatsApp integration, Docker, CI/CD

## Local development

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
python -m app.ai.ask           # chat with the assistant in the terminal (needs ANTHROPIC_API_KEY)
ruff check . && ruff format --check .
pytest                         # needs the database running; uses a separate carpet_test DB
uvicorn app.main:app --reload  # API docs at http://127.0.0.1:8000/docs
```

```bash
# Chat widget and owner dashboard (frontend/)
cd frontend
npm install
npm run dev                    # widget demo at http://localhost:5173, dashboard at /admin.html
                               # (both proxy /api to the backend)
npm run lint && npm run typecheck && npm test
npm run build                  # -> dist/ (demo + dashboard) and dist/widget.js (embeddable)
```

Embed the widget on any site:

```html
<script src="https://<host>/widget.js" data-api="https://<backend>" data-offset-bottom="92" defer></script>
```
