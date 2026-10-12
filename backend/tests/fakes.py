"""Test doubles for external AI services."""

import hashlib
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.ai.llm import ChatTurn, Document, Exchange, ModelTurn, ToolCall
from app.db.models import EMBEDDING_DIMENSIONS


@dataclass
class ChatCall:
    system: str
    context: str
    documents: list[Document]
    messages: list[ChatTurn]
    tools: list[dict[str, Any]]
    exchanges: list[Exchange]


class FakeChatModel:
    """Returns scripted turns in order (then a default reply) and records every request."""

    def __init__(self, *script: ModelTurn, default: str = "Hello from the fake model.") -> None:
        self.script = list(script)
        self.default = ModelTurn(default)
        self.calls: list[ChatCall] = []

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
        self.calls.append(
            ChatCall(system, context, list(documents), list(messages), list(tools), list(exchanges))
        )
        return self.script.pop(0) if self.script else self.default


def tool_turn(name: str, call_id: str = "call_1", **tool_input: Any) -> ModelTurn:
    """A scripted model turn that calls one tool."""
    return ModelTurn(text="", tool_calls=[ToolCall(call_id, name, tool_input)])


class FakeEmbedder:
    """Deterministic, offline embeddings: a hashed bag of words, normalised to length 1.

    Texts that share words get similar vectors, so retrieval tests behave sensibly
    without calling a real API. Records every text it was asked to embed.
    """

    def __init__(self, model: str = "fake-embedding-model") -> None:
        self.model = model
        self.dimensions = EMBEDDING_DIMENSIONS
        self.embedded: list[str] = []

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        self.embedded += texts
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for word in re.findall(r"\w+", text.lower()):
            bucket = int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dimensions
            vector[bucket] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]
