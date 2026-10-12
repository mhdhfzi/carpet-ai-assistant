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
cp .env.example .env            # then fill in the API keys
python -m venv .venv
.venv/Scripts/activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -e ".[dev]"
alembic upgrade head           # apply database migrations
python -m app.seed             # load the service price list (safe to re-run)
python -m app.ai.ingest        # embed knowledge docs + prices (needs VOYAGE_API_KEY in .env)
python -m app.ai.ask           # chat with the assistant in the terminal (needs ANTHROPIC_API_KEY)
ruff check . && ruff format --check .
pytest                         # needs the database running; uses a separate carpet_test DB
uvicorn app.main:app --reload  # API docs at http://127.0.0.1:8000/docs
```

```bash
# Chat widget (frontend/)
cd frontend
npm install
npm run dev                    # demo page at http://localhost:5173 (proxies /api to the backend)
npm run lint && npm run typecheck && npm test
npm run build                  # -> dist/widget.js, one self-contained embeddable script
```

Embed the widget on any site:

```html
<script src="https://<host>/widget.js" data-api="https://<backend>" data-offset-bottom="92" defer></script>
```
