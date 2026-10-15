import mimetypes
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api import (
    analytics,
    auth,
    availability,
    bookings,
    business,
    chat,
    closed_dates,
    conversations,
    services,
    unanswered,
    whatsapp,
)
from app.api.errors import register_exception_handlers
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.static import FrontendFiles

# Python guesses file types from the OS (on Windows, the registry, where .js can be
# text/plain). Browsers refuse scripts with the wrong type, so pin the ones we serve.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")

ROUTERS = [
    auth.router,
    business.router,
    analytics.router,
    services.router,
    bookings.router,
    availability.router,
    closed_dates.router,
    chat.router,
    conversations.router,
    unanswered.router,
    whatsapp.router,
]


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug)

    register_exception_handlers(app)
    app.add_middleware(RequestContextMiddleware)
    if settings.cors_origin_list:
        # Only the listed sites may call the API from a visitor's browser (the chat widget).
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )
    for router in ROUTERS:
        app.include_router(router)

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.environment}

    if not settings.demo_business:
        # The landing page belongs to the portfolio demo. A real business's deployment
        # serves only widget.js (embedded on its own website) and the owner dashboard.
        @app.get("/", include_in_schema=False)
        @app.get("/index.html", include_in_schema=False)
        def to_dashboard() -> RedirectResponse:
            return RedirectResponse("/admin.html")

    # The built frontend, served from the same origin as the API: one deploy, one URL, and
    # no CORS needed between the demo pages and the API. Mounted last, so /api/* and
    # /health always win over files.
    if settings.static_dir and Path(settings.static_dir).is_dir():
        app.mount("/", FrontendFiles(directory=settings.static_dir, html=True), name="frontend")

    return app


_settings = get_settings()
configure_logging(json_logs=_settings.json_logs, level=_settings.log_level)
app = create_app()
