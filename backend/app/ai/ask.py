"""Chat with the assistant in the terminal (for manual testing). Uses the real database and
AI providers, exactly like the web chat.

Run with:  python -m app.ai.ask        (type 'quit' to stop)
"""

from app.ai.embeddings import EmbeddingError, get_embedder
from app.ai.llm import LLMError, get_chat_model
from app.db.models import Message
from app.db.session import SessionLocal
from app.services import chat


def main() -> None:
    try:
        embedder, llm = get_embedder(), get_chat_model()
    except (EmbeddingError, LLMError) as exc:
        raise SystemExit(str(exc)) from exc

    session_id = None
    with SessionLocal() as db:
        while (text := input("\nyou> ").strip()).lower() not in {"quit", "exit"}:
            if not text:
                continue
            try:
                result = chat.handle_web_message(db, embedder, llm, session_id, text)
            except (EmbeddingError, LLMError) as exc:
                print(f"[error] {exc}")
                continue
            session_id = result.conversation.external_id
            if result.reply is None:
                print("[handed off: the owner will reply]")
                continue
            print(f"\nassistant> {result.reply}")
            last = (
                db.query(Message)
                .filter_by(conversation=result.conversation)
                .order_by(Message.id.desc())
                .first()
            )
            if last is not None:
                cited = ", ".join(f"{s['source']} > {s['heading']}" for s in last.sources or [])
                print(f"  [grounded: {last.grounded}; cited: {cited or 'none'}]")


if __name__ == "__main__":
    main()
