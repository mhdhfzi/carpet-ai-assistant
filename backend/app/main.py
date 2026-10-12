from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    analytics,
    auth,
    availability,
    bookings,
    chat,
    closed_dates,
    conversations,
    services,
    unanswered,
    whatsapp,
)
from app.api.errors import register_exception_handlers
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug)

    register_exception_handlers(app)
    app.include_router(auth.router)
    app.include_router(analytics.router)
    if settings.cors_origin_list:
        # Only the listed sites may call the API from a visitor's browser (the chat widget).
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )
    app.include_router(services.router)
    app.include_router(bookings.router)
    app.include_router(availability.router)
    app.include_router(closed_dates.router)
    app.include_router(chat.router)
    app.include_router(conversations.router)
    app.include_router(unanswered.router)
    app.include_router(whatsapp.router)

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.environment}

    return app


app = create_app()
