"""VoyageEmbedder against a mocked HTTP transport: no network, no API key needed."""

import json

import httpx2
import pytest

from app.ai.embeddings import EmbeddingError, VoyageEmbedder


class FakeVoyageAPI:
    """Mimics Voyage's /v1/embeddings response, returning items in reverse order."""

    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if self.status_code != 200:
            return httpx2.Response(self.status_code, json={"detail": "Invalid API key"})
        texts = json.loads(request.content)["input"]
        data = [{"index": i, "embedding": [float(len(t)), 0.0]} for i, t in enumerate(texts)]
        return httpx2.Response(200, json={"data": data[::-1], "usage": {"total_tokens": 1}})


def make_embedder(api: FakeVoyageAPI) -> VoyageEmbedder:
    client = httpx2.Client(transport=httpx2.MockTransport(api))
    return VoyageEmbedder("secret-key", "voyage-3.5", dimensions=2, client=client)


def test_documents_request_format_and_order() -> None:
    api = FakeVoyageAPI()

    vectors = make_embedder(api).embed_documents(["a", "bbb"])

    assert vectors == [[1.0, 0.0], [3.0, 0.0]]  # re-sorted by index
    request = api.requests[0]
    assert request.headers["Authorization"] == "Bearer secret-key"
    assert json.loads(request.content) == {
        "input": ["a", "bbb"],
        "model": "voyage-3.5",
        "input_type": "document",
        "output_dimension": 2,
    }


def test_query_uses_query_input_type() -> None:
    api = FakeVoyageAPI()

    make_embedder(api).embed_query("berapa harga karpet?")

    assert json.loads(api.requests[0].content)["input_type"] == "query"


def test_large_inputs_are_sent_in_batches() -> None:
    api = FakeVoyageAPI()
    texts = [f"text {i}" for i in range(VoyageEmbedder.BATCH_SIZE + 5)]

    vectors = make_embedder(api).embed_documents(texts)

    assert len(vectors) == len(texts)
    assert [len(json.loads(r.content)["input"]) for r in api.requests] == [128, 5]


def test_api_errors_raise_embedding_error() -> None:
    with pytest.raises(EmbeddingError, match="401"):
        make_embedder(FakeVoyageAPI(status_code=401)).embed_query("hello")
