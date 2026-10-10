# carpet-ai-assistant
AI customer assistant for a home-service business: RAG + LLM tool calling, FastAPI, PostgreSQL/pgvector, React, WhatsApp integration, Docker, CI/CD

## Local development

Requires Docker and Python 3.12+.

```bash
# Database (Postgres 16 + pgvector)
cp .env.example .env
docker compose up -d

# Backend
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -e ".[dev]"
alembic upgrade head           # apply database migrations
ruff check . && ruff format --check .
pytest                         # needs the database running; uses a separate carpet_test DB
uvicorn app.main:app --reload  # http://localhost:8000/health
```
