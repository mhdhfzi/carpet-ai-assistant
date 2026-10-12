"""Chat model behind a small interface, so the provider can be swapped and tests stay offline."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol

import anthropic

from app.core.config import get_settings


class LLMError(Exception):
    pass


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
    document_index: int  # position in the `documents` passed to `answer`
    cited_text: str


@dataclass(frozen=True)
class LLMAnswer:
    text: str
    citations: list[Citation] = field(default_factory=list)
    refused: bool = False


class ChatModel(Protocol):
    def answer(
        self, *, system: str, documents: Sequence[Document], messages: Sequence[ChatTurn]
    ) -> LLMAnswer: ...


class ClaudeChatModel:
    """Claude via the Anthropic SDK, using the API's built-in citations.

    Retrieved chunks are sent as `document` blocks with citations enabled, so Claude reports
    which document (and which sentence) supports each part of its answer. This is more
    reliable than asking the model to write source names into its reply.
    """

    MAX_TOKENS = 16000

    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        self._client = client
        self.model = model

    def answer(
        self, *, system: str, documents: Sequence[Document], messages: Sequence[ChatTurn]
    ) -> LLMAnswer:
        if not messages or messages[-1].role != "user":
            raise ValueError("The conversation must end with a user message")

        # Documents go in the latest user turn, before the question (Claude reads them first).
        latest = [
            *(
                {
                    "type": "document",
                    "source": {"type": "text", "media_type": "text/plain", "data": doc.text},
                    "title": doc.title,
                    "citations": {"enabled": True},
                }
                for doc in documents
            ),
            {"type": "text", "text": messages[-1].content},
        ]
        history = [{"role": turn.role, "content": turn.content} for turn in messages[:-1]]

        try:
            response = self._client.beta.messages.create(
                model=self.model,
                max_tokens=self.MAX_TOKENS,
                system=system,
                messages=[*history, {"role": "user", "content": latest}],
                # Customer chat is simple and latency-sensitive, so keep thinking light.
                output_config={"effort": "low"},
                # If a safety classifier declines, the API re-runs the request on a
                # recommended fallback model instead of returning a refusal.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.APIError as exc:
            raise LLMError(f"Claude API request failed: {exc}") from exc

        if response.stop_reason == "refusal":
            return LLMAnswer(text="", refused=True)

        text, citations = [], []
        for block in response.content:
            if block.type != "text":
                continue  # e.g. thinking or fallback marker blocks
            text.append(block.text)
            for citation in block.citations or []:
                if citation.type == "char_location":
                    citations.append(Citation(citation.document_index, citation.cited_text))
        return LLMAnswer(text="".join(text).strip(), citations=citations)


def get_chat_model() -> ChatModel:
    settings = get_settings()
    if settings.anthropic_api_key is None:
        raise LLMError("ANTHROPIC_API_KEY is not set; add it to backend/.env")
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key.get_secret_value())
    return ClaudeChatModel(client, settings.chat_model)
