"""Translate service-layer domain errors into HTTP responses, in one place."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.ai.embeddings import EmbeddingError
from app.ai.llm import LLMError
from app.services.errors import BusinessRuleError, ConflictError, DomainError, NotFoundError

logger = logging.getLogger(__name__)

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
    for exc_class in (EmbeddingError, LLMError):
        app.add_exception_handler(exc_class, _ai_unavailable)


def _handler(status_code: int):
    async def handle(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handle


async def _ai_unavailable(_: Request, exc: Exception) -> JSONResponse:
    # The real cause (missing key, provider outage) goes to the server log; the customer
    # gets a generic message, never provider error details.
    logger.error("AI provider error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "The assistant is temporarily unavailable. Please try again later."},
    )
