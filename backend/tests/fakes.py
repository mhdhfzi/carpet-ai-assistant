"""Test doubles for external AI services."""

import hashlib
import math
import re
from collections.abc import Sequence

from app.db.models import EMBEDDING_DIMENSIONS


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
