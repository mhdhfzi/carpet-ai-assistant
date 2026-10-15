"""Chat model behind a small interface, so the provider can be swapped and tests stay offline.

The agent loop (app/ai/agent.py) is provider-neutral: it asks the model for a turn, runs any
tools the model requested, and asks again with the results. Everything Claude-specific
(message format, citations, thinking blocks) stays inside ClaudeChatModel.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import anthropic

from app.core.config import get_settings


class LLMError(Exception):
    pass


class LLMCreditError(LLMError):
    """The AI provider account has run out of credit. Not temporary like an outage: the
    chat pauses itself until someone tops up (see app/services/assistant_status.py)."""


@dataclass(frozen=True)
class Document:
    title: str
    text: str


@dataclass(frozen=True)
class ChatTurn:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class Citation:
    document_index: int  # position in the `documents` passed to `respond`
    cited_text: str


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True)
class ModelTurn:
    text: str
    citations: list[Citation] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    refused: bool = False
    # The provider's own representation of this turn, sent back unchanged on the next
    # request (Claude requires its thinking and tool_use blocks to be returned as-is).
    raw: Any = None


@dataclass(frozen=True)
class ToolOutcome:
    call_id: str
    content: str
    is_error: bool = False


# One round of tool use: what the model asked for and what the tools returned.
Exchange = tuple[ModelTurn, list[ToolOutcome]]


class ChatModel(Protocol):
    def respond(
        self,
        *,
        system: str,
        context: str,
        documents: Sequence[Document],
        messages: Sequence[ChatTurn],
        tools: Sequence[dict[str, Any]],
        exchanges: Sequence[Exchange],
    ) -> ModelTurn: ...


class ClaudeChatModel:
    """Claude via the Anthropic SDK, with built-in citations and client-side tools.

    Retrieved chunks are sent as `document` blocks with citations enabled, so Claude reports
    which document (and which sentence) supports each part of its answer.
    """

    MAX_TOKENS = 16000

    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        self._client = client
        self.model = model

    def respond(
        self,
        *,
        system: str,
        context: str,
        documents: Sequence[Document],
        messages: Sequence[ChatTurn],
        tools: Sequence[dict[str, Any]],
        exchanges: Sequence[Exchange],
    ) -> ModelTurn:
        if not messages or messages[-1].role != "user":
            raise ValueError("The conversation must end with a user message")

        api_messages: list[dict[str, Any]] = [
            {"role": turn.role, "content": turn.content} for turn in messages[:-1]
        ]
        # Latest customer turn: documents first (Claude reads them before the question), then
        # per-request context such as today's date, then the message itself.
        api_messages.append(
            {
                "role": "user",
                "content": [
                    *(_document_block(doc) for doc in documents),
                    {"type": "text", "text": context},
                    {"type": "text", "text": messages[-1].content},
                ],
            }
        )
        # Tool rounds so far, appended (never edited) so the request stays append-only.
        for turn, outcomes in exchanges:
            api_messages.append({"role": "assistant", "content": turn.raw})
            api_messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": outcome.call_id,
                            "content": outcome.content,
                            "is_error": outcome.is_error,
                        }
                        for outcome in outcomes
                    ],
                }
            )

        try:
            response = self._client.beta.messages.create(
                model=self.model,
                max_tokens=self.MAX_TOKENS,
                system=system,
                messages=api_messages,
                tools=list(tools),
                # Customer chat is simple and latency-sensitive, so keep thinking light.
                output_config={"effort": "low"},
                # If a safety classifier declines, the API re-runs the request on a
                # recommended fallback model instead of returning a refusal.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.APIError as exc:
            if _out_of_credit(exc):
                raise LLMCreditError(f"Claude API account is out of credit: {exc}") from exc
            raise LLMError(f"Claude API request failed: {exc}") from exc

        if response.stop_reason == "refusal":
            return ModelTurn(text="", refused=True)

        text, citations, tool_calls = [], [], []
        for block in response.content:
            if block.type == "text":
                text.append(block.text)
                for citation in block.citations or []:
                    if citation.type == "char_location":
                        citations.append(Citation(citation.document_index, citation.cited_text))
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(block.id, block.name, dict(block.input)))
        return ModelTurn(
            text="".join(text).strip(),
            citations=citations,
            tool_calls=tool_calls,
            raw=response.content,
        )


def _out_of_credit(exc: anthropic.APIError) -> bool:
    """The account has no credit left: a `billing_error` (HTTP 402). Older API versions
    reported it as a 400 whose message mentions the credit balance."""
    if not isinstance(exc, anthropic.APIStatusError):
        return False  # a network problem, not billing
    return (
        getattr(exc, "type", None) == "billing_error"
        or exc.status_code == 402
        or "credit balance" in str(exc).lower()
    )


def _document_block(doc: Document) -> dict[str, Any]:
    return {
        "type": "document",
        "source": {"type": "text", "media_type": "text/plain", "data": doc.text},
        "title": doc.title,
        "citations": {"enabled": True},
    }


def get_chat_model() -> ChatModel:
    settings = get_settings()
    if settings.anthropic_api_key is None:
        raise LLMError("ANTHROPIC_API_KEY is not set; add it to backend/.env")
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key.get_secret_value())
    return ClaudeChatModel(client, settings.chat_model)
