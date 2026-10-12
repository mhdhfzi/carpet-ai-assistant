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
python -m app.seed_demo        # optional: fictional chats and bookings for the dashboard
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

## Production image

One Docker image runs the API and serves the built frontend (demo page, dashboard, `widget.js`) from the same origin:

```bash
docker compose --profile app run --rm app alembic upgrade head   # migrations
docker compose --profile app up --build                          # http://localhost:8080
```

## Deployment (Google Cloud Run + Neon)

Live: https://kilau-918469824880.asia-southeast1.run.app

| Piece | Where |
|---|---|
| App (API + frontend) | Cloud Run service `kilau`, `asia-southeast1`, 0–2 instances (scales to zero) |
| Database | Neon Postgres (Singapore), pooled connection, pgvector |
| Images | Artifact Registry `asia-southeast1-docker.pkg.dev/kilau-assistant/kilau/app:<git sha>` |
| Secrets | Secret Manager: `database-url`, `jwt-secret`, `voyage-api-key`, `anthropic-api-key` |
| Migrations / one-off commands | Cloud Run jobs `migrate` (`alembic upgrade head`) and `manage` (`python -m ...`) |
| Nightly demo reset | Cloud Scheduler `demo-reset-nightly` (03:00 MYT) runs the `demo-reset` job: `python -m app.seed_demo --reset` |

**Public demo.** The dashboard has a read-only demo login (`demo@example.com` / `kilau-demo-2026`, also a one-click button on the login page). Owners have a role, and the auth dependency refuses every non-GET request from the `demo` role with 403, so a write route added later is covered automatically (tested by enumerating all routes). Because that login is public, the nightly reset deletes every customer, chat and booking and re-seeds the fictional demo data, so nothing a visitor types stays visible for more than a day.

**Continuous deployment.** On every push to `main`, CI runs the tests, then builds the image, pushes it, runs the `migrate` job and rolls Cloud Run onto the new image. GitHub authenticates through Workload Identity Federation (no stored key; only this repository is trusted) as `github-deployer`, which can push images and deploy but not read secrets. The app runs as `kilau-run`, which can only read its secrets.

Env vars, secrets and scaling belong to the service and carry over between deploys. To change them, or to run a one-off command against production:

```bash
gcloud run services update kilau --region asia-southeast1 --update-secrets ANTHROPIC_API_KEY=anthropic-api-key:latest
gcloud run jobs execute manage --region asia-southeast1 --args=-m,app.seed_demo --wait
```

Neon runs Postgres 18; CI tests against 16. The app uses nothing that differs between them.
