"""Text embeddings, behind a small interface so the provider can be swapped.

The rest of the app depends only on `Embedder`. Tests use a fake implementation, and
replacing Voyage AI with another provider means writing one new class.
"""

from collections.abc import Sequence
from typing import Literal, Protocol

import httpx2

from app.core.config import get_settings
from app.db.models import EMBEDDING_DIMENSIONS


class EmbeddingError(Exception):
    pass


class Embedder(Protocol):
    model: str
    dimensions: int

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class VoyageEmbedder:
    """Voyage AI embeddings via their REST API (https://docs.voyageai.com/reference).

    Calls the API directly with httpx2 rather than using the voyageai SDK, which would add
    numpy, pillow and a tokenizer library to the image for what is one POST request.
    """

    URL = "https://api.voyageai.com/v1/embeddings"
    BATCH_SIZE = 128  # well under Voyage's per-request limits

    def __init__(
        self,
        api_key: str,
        model: str,
        dimensions: int = EMBEDDING_DIMENSIONS,
        client: httpx2.Client | None = None,
    ) -> None:
        self.model = model
        self.dimensions = dimensions
        self._client = client or httpx2.Client(
            timeout=30.0, transport=httpx2.HTTPTransport(retries=2)
        )
        self._headers = {"Authorization": f"Bearer {api_key}"}

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.BATCH_SIZE):
            vectors += self._embed(texts[start : start + self.BATCH_SIZE], "document")
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "query")[0]

    def _embed(
        self, texts: Sequence[str], input_type: Literal["document", "query"]
    ) -> list[list[float]]:
        # input_type matters: Voyage prepends a different prompt for queries vs documents,
        # which measurably improves retrieval of short questions against longer passages.
        response = self._client.post(
            self.URL,
            headers=self._headers,
            json={
                "input": list(texts),
                "model": self.model,
                "input_type": input_type,
                "output_dimension": self.dimensions,
            },
        )
        if response.is_error:
            raise EmbeddingError(f"Voyage AI returned {response.status_code}: {response.text}")
        data = sorted(response.json()["data"], key=lambda item: item["index"])
        return [item["embedding"] for item in data]


def get_embedder() -> Embedder:
    settings = get_settings()
    if settings.voyage_api_key is None:
        raise EmbeddingError("VOYAGE_API_KEY is not set; add it to backend/.env")
    return VoyageEmbedder(settings.voyage_api_key.get_secret_value(), settings.embedding_model)
