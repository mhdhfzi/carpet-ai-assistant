from fastapi import FastAPI

from app.api import availability, bookings, chat, closed_dates, services
from app.api.errors import register_exception_handlers
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug)

    register_exception_handlers(app)
    app.include_router(services.router)
    app.include_router(bookings.router)
    app.include_router(availability.router)
    app.include_router(closed_dates.router)
    app.include_router(chat.router)

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.environment}

    return app


app = create_app()
