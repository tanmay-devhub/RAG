import os
from langchain_ollama import OllamaEmbeddings

_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")

_embeddings_instance: OllamaEmbeddings | None = None


def get_embeddings() -> OllamaEmbeddings:
    """Return a reusable OllamaEmbeddings instance."""
    global _embeddings_instance
    if _embeddings_instance is None:
        _embeddings_instance = OllamaEmbeddings(
            base_url=_OLLAMA_BASE_URL,
            model=_EMBED_MODEL,
        )
    return _embeddings_instance


def embed_text(text: str) -> list[float]:
    """Embed a single string and return the vector."""
    return get_embeddings().embed_query(text)
