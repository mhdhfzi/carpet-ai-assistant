"""ClaudeChatModel against a mocked HTTP transport: checks the request we send and how the
response is parsed, without calling the real API."""

import json
from typing import Any

import anthropic
import httpx2
import pytest

from app.ai.llm import ChatTurn, Citation, ClaudeChatModel, Document, LLMError


def message(content: list[dict], stop_reason: str = "end_turn") -> dict[str, Any]:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


class FakeAnthropicAPI:
    def __init__(self, response: dict[str, Any], status_code: int = 200) -> None:
        self.response = response
        self.status_code = status_code
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return httpx2.Response(self.status_code, json=self.response)

    @property
    def body(self) -> dict[str, Any]:
        return json.loads(self.requests[-1].content)


def make_model(api: FakeAnthropicAPI) -> ClaudeChatModel:
    client = anthropic.Anthropic(
        api_key="test-key",
        max_retries=0,
        http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(api)),
    )
    return ClaudeChatModel(client, "claude-opus-5-5")


DOCS = [Document("Booking and opening hours: Opening hours", "Closed on Fridays.")]
CITED_ANSWER = message(
    [
        {"type": "text", "text": "No, ", "citations": None},
        {
            "type": "text",
            "text": "we're closed on Fridays.",
            "citations": [
                {
                    "type": "char_location",
                    "cited_text": "Closed on Fridays.",
                    "document_index": 0,
                    "document_title": "Booking and opening hours: Opening hours",
                    "start_char_index": 0,
                    "end_char_index": 18,
                }
            ],
        },
    ]
)


def test_request_sends_documents_with_citations_before_the_question() -> None:
    api = FakeAnthropicAPI(CITED_ANSWER)
    history = [ChatTurn("user", "Hi"), ChatTurn("assistant", "Hello!")]

    make_model(api).answer(
        system="Be helpful.", documents=DOCS, messages=[*history, ChatTurn("user", "Friday?")]
    )

    body = api.body
    assert body["model"] == "claude-opus-5-5"
    assert body["system"] == "Be helpful."
    assert body["output_config"] == {"effort": "low"}
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in api.requests[-1].headers["anthropic-beta"]
    assert body["messages"][:2] == [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello!"},
    ]
    document, question = body["messages"][2]["content"]
    assert document == {
        "type": "document",
        "source": {"type": "text", "media_type": "text/plain", "data": "Closed on Fridays."},
        "title": "Booking and opening hours: Opening hours",
        "citations": {"enabled": True},
    }
    assert question == {"type": "text", "text": "Friday?"}


def test_response_text_and_citations_are_parsed() -> None:
    result = make_model(FakeAnthropicAPI(CITED_ANSWER)).answer(
        system="", documents=DOCS, messages=[ChatTurn("user", "Friday?")]
    )

    assert result.text == "No, we're closed on Fridays."
    assert result.citations == [Citation(0, "Closed on Fridays.")]
    assert not result.refused


def test_refusal_is_reported() -> None:
    api = FakeAnthropicAPI(message([], stop_reason="refusal"))

    result = make_model(api).answer(system="", documents=[], messages=[ChatTurn("user", "x")])

    assert result.refused


def test_api_errors_become_llm_errors() -> None:
    api = FakeAnthropicAPI({"type": "error", "error": {"type": "api_error"}}, status_code=500)

    with pytest.raises(LLMError):
        make_model(api).answer(system="", documents=[], messages=[ChatTurn("user", "x")])


def test_conversation_must_end_with_the_customer() -> None:
    with pytest.raises(ValueError):
        make_model(FakeAnthropicAPI(CITED_ANSWER)).answer(
            system="", documents=[], messages=[ChatTurn("assistant", "Hello")]
        )
