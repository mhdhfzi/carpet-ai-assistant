"""Translate service-layer domain errors into HTTP responses, in one place."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.services.errors import BusinessRuleError, ConflictError, DomainError, NotFoundError

# Starlette picks the handler for the most specific class in the exception's MRO,
# so e.g. InvalidStatusTransitionError (a ConflictError) becomes a 409.
_STATUS_CODES: dict[type[DomainError], int] = {
    DomainError: status.HTTP_400_BAD_REQUEST,
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    BusinessRuleError: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


def register_exception_handlers(app: FastAPI) -> None:
    for exc_class, status_code in _STATUS_CODES.items():
        app.add_exception_handler(exc_class, _handler(status_code))


def _handler(status_code: int):
    async def handle(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handle
