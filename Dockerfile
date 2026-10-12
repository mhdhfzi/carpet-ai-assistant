# syntax=docker/dockerfile:1
# One production image: the FastAPI backend serving the built frontend.
#   docker build -t carpet-ai-assistant .
#   docker run -p 8000:8000 --env-file backend/.env carpet-ai-assistant

# --- 1. Build the frontend (demo page, owner dashboard, widget.js) --------------------------
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- 2. Install Python dependencies into a virtualenv ----------------------------------------
FROM python:3.12-slim AS python-deps
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY backend/pyproject.toml ./
# Dependencies only (read from pyproject.toml), so this layer stays cached until they
# change, not every time the code does.
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > requirements.txt \
 && python -m venv /venv \
 && /venv/bin/pip install -r requirements.txt

# --- 3. Runtime: slim, no build tools, non-root ---------------------------------------------
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH" \
    PORT=8000 \
    STATIC_DIR=/app/static \
    ENVIRONMENT=production
RUN useradd --create-home --uid 10001 app
COPY --from=python-deps /venv /venv
WORKDIR /app
COPY backend/ ./
COPY --from=frontend /frontend/dist ./static
USER app
EXPOSE 8000
# Cloud Run sets PORT. --proxy-headers so client IPs (used by rate limiting) come from the
# load balancer's X-Forwarded-For header.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
