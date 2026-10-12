"""ClaudeChatModel against a mocked HTTP transport: checks the request we send and how the
response is parsed, without calling the real API."""

import json
from typing import Any

import anthropic
import httpx2
import pytest

from app.ai.llm import (
    ChatTurn,
    Citation,
    ClaudeChatModel,
    Document,
    LLMError,
    ModelTurn,
    ToolCall,
    ToolOutcome,
)

TOOLS = [
    {"name": "get_services", "description": "List services.", "input_schema": {"type": "object"}}
]
DOCS = [Document("Booking and opening hours: Opening hours", "Closed on Fridays.")]
CONTEXT = "[Context: it is now Saturday, 10 October 2026, 10:00 in Malaysia.]"


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
TOOL_USE = message(
    [
        {"type": "thinking", "thinking": "", "signature": "sig-abc"},
        {"type": "tool_use", "id": "toolu_1", "name": "get_services", "input": {}},
    ],
    stop_reason="tool_use",
)


class FakeAnthropicAPI:
    def __init__(self, *responses: dict[str, Any], status_code: int = 200) -> None:
        self.responses = list(responses)
        self.status_code = status_code
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return httpx2.Response(self.status_code, json=self.responses.pop(0))

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


def respond(model: ClaudeChatModel, messages=None, exchanges=(), documents=DOCS) -> ModelTurn:
    return model.respond(
        system="Be helpful.",
        context=CONTEXT,
        documents=documents,
        messages=messages or [ChatTurn("user", "Friday?")],
        tools=TOOLS,
        exchanges=exchanges,
    )


def test_request_sends_documents_context_and_question_in_the_latest_turn() -> None:
    api = FakeAnthropicAPI(CITED_ANSWER)
    history = [ChatTurn("user", "Hi"), ChatTurn("assistant", "Hello!")]

    respond(make_model(api), messages=[*history, ChatTurn("user", "Friday?")])

    body = api.body
    assert body["model"] == "claude-opus-5-5"
    assert body["system"] == "Be helpful."
    assert body["tools"] == TOOLS
    assert body["output_config"] == {"effort": "low"}
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in api.requests[-1].headers["anthropic-beta"]
    assert body["messages"][:2] == [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello!"},
    ]
    document, context, question = body["messages"][2]["content"]
    assert document == {
        "type": "document",
        "source": {"type": "text", "media_type": "text/plain", "data": "Closed on Fridays."},
        "title": "Booking and opening hours: Opening hours",
        "citations": {"enabled": True},
    }
    assert context == {"type": "text", "text": CONTEXT}
    assert question == {"type": "text", "text": "Friday?"}


def test_text_and_citations_are_parsed() -> None:
    turn = respond(make_model(FakeAnthropicAPI(CITED_ANSWER)))

    assert turn.text == "No, we're closed on Fridays."
    assert turn.citations == [Citation(0, "Closed on Fridays.")]
    assert turn.tool_calls == []


def test_tool_calls_are_parsed_and_the_raw_turn_is_kept() -> None:
    turn = respond(make_model(FakeAnthropicAPI(TOOL_USE)))

    assert turn.tool_calls == [ToolCall("toolu_1", "get_services", {})]
    assert [block.type for block in turn.raw] == ["thinking", "tool_use"]


def test_tool_rounds_are_appended_unchanged_with_their_results() -> None:
    api = FakeAnthropicAPI(TOOL_USE, CITED_ANSWER)
    model = make_model(api)
    first = respond(model)

    respond(model, exchanges=[(first, [ToolOutcome("toolu_1", '{"services": []}')])])

    assistant, results = api.body["messages"][-2:]
    assert assistant["role"] == "assistant"
    # Thinking blocks go back exactly as received, signature included.
    assert assistant["content"][0] == {"type": "thinking", "thinking": "", "signature": "sig-abc"}
    assert assistant["content"][1]["type"] == "tool_use"
    assert results == {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_1",
                "content": '{"services": []}',
                "is_error": False,
            }
        ],
    }


def test_refusal_is_reported() -> None:
    turn = respond(make_model(FakeAnthropicAPI(message([], stop_reason="refusal"))))

    assert turn.refused


def test_api_errors_become_llm_errors() -> None:
    api = FakeAnthropicAPI({"type": "error", "error": {"type": "api_error"}}, status_code=500)

    with pytest.raises(LLMError):
        respond(make_model(api))


def test_conversation_must_end_with_the_customer() -> None:
    with pytest.raises(ValueError):
        respond(make_model(FakeAnthropicAPI(CITED_ANSWER)), messages=[ChatTurn("assistant", "Hi")])
