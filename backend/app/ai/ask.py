"""Ask the assistant a one-off question from the terminal (for manual testing).

Run with:  python -m app.ai.ask "Berapa harga cuci sofa?"
"""

import sys

from app.ai import rag
from app.ai.embeddings import EmbeddingError, get_embedder
from app.ai.llm import ChatTurn, LLMError, get_chat_model
from app.db.session import SessionLocal


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python -m app.ai.ask "your question"')
    try:
        with SessionLocal() as db:
            result = rag.answer(
                db, get_embedder(), get_chat_model(), [ChatTurn("user", sys.argv[1])]
            )
    except (EmbeddingError, LLMError) as exc:
        raise SystemExit(str(exc)) from exc

    print(result.text, end="\n\n")
    print("Grounded in the knowledge base:", "yes" if result.grounded else "NO")
    for source in result.sources:
        print(f'  - {source.source} > {source.heading}: "{source.cited_text}"')
    print("Retrieved:", ", ".join(f"{c.heading} ({c.score:.2f})" for c in result.retrieved))


if __name__ == "__main__":
    main()
