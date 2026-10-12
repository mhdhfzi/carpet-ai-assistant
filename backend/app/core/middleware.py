"""Per-request context: a request ID, an access log line, security headers, and a safe
response for unexpected errors."""

import json
import logging
import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import request_id_var

logger = logging.getLogger("app.request")

# Accept a caller's ID only if it looks like one: never log arbitrary client text.
_VALID_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",  # browsers must trust our Content-Type
    "X-Frame-Options": "DENY",  # no one can frame our pages (clickjacking)
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


class RequestContextMiddleware:
    """Plain ASGI middleware (not BaseHTTPMiddleware), so it adds no overhead to
    streaming and keeps context variables visible to the endpoint."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        request_id = incoming if _VALID_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status = 500
        response_started = False

        async def send_with_headers(message: Message) -> None:
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                status = message["status"]
                response_started = True
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                for name, value in SECURITY_HEADERS.items():
                    headers.setdefault(name, value)
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        except Exception:
            # Handled here rather than by an app-level handler, which would run after this
            # middleware and lose the request ID. The full error goes to the log; the client
            # gets only an ID to quote, never a stack trace or internal message.
            logger.exception("Unhandled error")
            if response_started:
                raise  # too late to send a clean error response
            body = json.dumps(
                {"detail": "Internal server error", "request_id": request_id}
            ).encode()
            await send_with_headers(
                {
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
        finally:
            path = scope["path"]
            logger.log(
                logging.DEBUG if path == "/health" else logging.INFO,
                "%s %s %s",
                scope["method"],
                path,
                status,
                extra={
                    "http_method": scope["method"],
                    "path": path,
                    "status": status,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    "client_ip": scope["client"][0] if scope.get("client") else None,
                },
            )
            request_id_var.reset(token)
