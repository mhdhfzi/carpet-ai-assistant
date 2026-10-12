"""WhatsApp Business Cloud API webhook."""

import hmac
import json
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from app.api.deps import (
    ChatModelDep,
    EmbedderDep,
    SessionFactoryDep,
    WhatsAppClientDep,
    WhatsAppConfigDep,
)
from app.services import whatsapp

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


@router.get("/webhook", response_class=PlainTextResponse)
def verify_webhook(
    config: WhatsAppConfigDep,
    mode: Annotated[str, Query(alias="hub.mode")],
    token: Annotated[str, Query(alias="hub.verify_token")],
    challenge: Annotated[str, Query(alias="hub.challenge")],
) -> str:
    """Meta calls this once when the webhook URL is registered, and expects the challenge
    echoed back only if the verify token matches the one we chose."""
    if (
        config.verify_token
        and mode == "subscribe"
        and hmac.compare_digest(token, config.verify_token)
    ):
        return challenge
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Verification failed")


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    background: BackgroundTasks,
    config: WhatsAppConfigDep,
    embedder: EmbedderDep,
    llm: ChatModelDep,
    client: WhatsAppClientDep,
    session_factory: SessionFactoryDep,
) -> dict[str, str]:
    """Incoming messages. Answers 200 straight away and replies in the background: the AI
    can take several seconds, and Meta retries webhooks that don't respond quickly."""
    if not config.app_secret:
        # Never process messages we can't authenticate.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "WhatsApp is not configured")

    body = await request.body()  # the signature covers the exact raw bytes
    signature = request.headers.get("X-Hub-Signature-256")
    if not whatsapp.verify_signature(config.app_secret, body, signature):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid signature")

    try:
        payload = json.loads(body)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid JSON") from None

    messages = whatsapp.parse_messages(payload)
    if messages:
        background.add_task(
            whatsapp.process_messages, session_factory, embedder, llm, client, messages
        )
    return {"status": "received"}
