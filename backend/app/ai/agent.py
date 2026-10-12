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
from app.ai.prompts import AGENT_SYSTEM_PROMPT, HANDOFF_MESSAGE
from app.ai.rag import Source
from app.ai.retrieval import RetrievedChunk, retrieve
from app.ai.tools import ToolContext, run_tool, tool_definitions
from app.core import clock
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
    chunks = retrieve(ctx.db, embedder, rag.retrieval_query(messages), limit=TOP_K)
    documents = rag.to_documents(chunks)
    tools = tool_definitions()
    context = request_context(clock.now())

    exchanges: list[Exchange] = []
    tools_used: list[str] = []
    for _ in range(MAX_TOOL_ROUNDS + 1):
        turn = llm.respond(
            system=AGENT_SYSTEM_PROMPT,
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
            result = run_tool(ctx, call.name, call.input)
            outcomes.append(ToolOutcome(call.id, result.content, result.is_error))
            if not result.is_error:
                tools_used.append(call.name)
        exchanges.append((turn, outcomes))

    return AgentReply(
        text=HANDOFF_MESSAGE, sources=[], retrieved=chunks, tools_used=tools_used, gave_up=True
    )


def request_context(now: datetime) -> str:
    """Per-request facts the model needs, e.g. to turn "next Monday" into a date."""
    local = now.astimezone(HOURS.timezone)
    return f"[Context: it is now {local:%A, %d %B %Y, %H:%M} in Malaysia.]"
