from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.ai.embeddings import Embedder, get_embedder
from app.ai.llm import ChatModel, get_chat_model
from app.db.session import get_db

DbSession = Annotated[Session, Depends(get_db)]


# Cached so every request reuses one HTTP client (connection pooling). A missing API key
# raises instead of returning, and lru_cache doesn't cache exceptions, so adding the key
# and restarting is enough. Tests replace these via app.dependency_overrides.
@lru_cache
def embedder_dependency() -> Embedder:
    return get_embedder()


@lru_cache
def chat_model_dependency() -> ChatModel:
    return get_chat_model()


EmbedderDep = Annotated[Embedder, Depends(embedder_dependency)]
ChatModelDep = Annotated[ChatModel, Depends(chat_model_dependency)]
