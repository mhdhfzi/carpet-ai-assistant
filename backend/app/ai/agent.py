"""The assistant's agent loop: answer from the knowledge base, or call tools and answer from
their results.

A hand-written loop rather than the SDK's tool runner, because each tool call needs request
context (database session, conversation, the customer message being answered) and the loop
must stay behind the provider-neutral ChatModel interface so it can be tested with fakes.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from app.ai import rag
from app.ai.embeddings import Embedder
from app.ai.llm import ChatModel, ChatTurn, Exchange, ToolOutcome
from app.ai.prompts import fallback_message, system_prompt
from app.ai.rag import Source
from app.ai.retrieval import RetrievedChunk, retrieve_for
from app.ai.tools import ToolContext, available_tools, run_tool, tool_definitions
from app.core import clock
from app.core.config import get_settings
from app.services.availability import HOURS

TOP_K = 5
# Tool rounds allowed per customer message. A booking needs about three (services,
# availability, prepare_booking); the cap stops a confused model looping, and billing, forever.
MAX_TOOL_ROUNDS = 6

# Tools whose results are business data: a reply built on them is grounded even without
# document citations.
DATA_TOOLS = {
    "get_services",
    "estimate_price",
    "check_availability",
    "prepare_booking",
    "create_booking",
}


@dataclass(frozen=True)
class AgentReply:
    text: str
    sources: list[Source]
    retrieved: list[RetrievedChunk]
    tools_used: list[str] = field(default_factory=list)  # successful calls, in order
    gave_up: bool = False  # refusal or too many tool rounds

    @property
    def grounded(self) -> bool:
        """True if the reply rests on the knowledge base or on business data from tools.

        An ungrounded reply ("I'm not sure, the owner will get back to you") means neither
        covered the question: a structured signal for the unanswered-questions log.
        """
        return bool(self.sources) or any(name in DATA_TOOLS for name in self.tools_used)


def run(
    ctx: ToolContext, embedder: Embedder, llm: ChatModel, messages: Sequence[ChatTurn]
) -> AgentReply:
    chunks = retrieve_for(ctx.db, embedder, rag.retrieval_queries(messages), limit=TOP_K)
    ctx.top_score = max((c.score for c in chunks), default=None)
    documents = rag.to_documents(chunks)
    settings = get_settings()
    allowed = available_tools(settings.bookings_enabled)
    tools = tool_definitions(allowed)
    system = system_prompt(settings)
    context = request_context(clock.now())

    exchanges: list[Exchange] = []
    tools_used: list[str] = []
    for _ in range(MAX_TOOL_ROUNDS + 1):
        turn = llm.respond(
            system=system,
            context=context,
            documents=documents,
            messages=messages,
            tools=tools,
            exchanges=exchanges,
        )
        if turn.refused:
            break
        if not turn.tool_calls:
            if not turn.text:
                break
            return AgentReply(
                text=turn.text,
                sources=rag.cited_sources(turn.citations, chunks),
                retrieved=chunks,
                tools_used=tools_used,
            )

        outcomes = []
        for call in turn.tool_calls:
            result = run_tool(ctx, call.name, call.input, allowed=allowed)
            outcomes.append(ToolOutcome(call.id, result.content, result.is_error))
            if not result.is_error:
                tools_used.append(call.name)
        exchanges.append((turn, outcomes))

    return AgentReply(
        text=fallback_message(settings),
        sources=[],
        retrieved=chunks,
        tools_used=tools_used,
        gave_up=True,
    )


def request_context(now: datetime) -> str:
    """Per-request facts the model needs, e.g. to turn "next Monday" into a date."""
    local = now.astimezone(HOURS.timezone)
    return f"[Context: it is now {local:%A, %d %B %Y, %H:%M} in Malaysia.]"
