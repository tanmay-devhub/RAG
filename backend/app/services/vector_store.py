import os
import logging
import chromadb
from chromadb import Collection
from app.services.embedder import embed_text

logger = logging.getLogger(__name__)

_CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
_CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
_COLLECTION_NAME = "rag_documents"

_client: chromadb.HttpClient | None = None
_collection: Collection | None = None


def get_collection() -> Collection:
    """Return the persistent Chroma collection, creating it if necessary."""
    global _client, _collection
    if _client is None:
        _client = chromadb.HttpClient(host=_CHROMA_HOST, port=_CHROMA_PORT)
    if _collection is None:
        _collection = _client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def add_chunks(chunks: list[str], metadatas: list[dict], ids: list[str]) -> None:
    """Embed chunks and store them in ChromaDB."""
    collection = get_collection()
    embeddings = [embed_text(chunk) for chunk in chunks]
    collection.add(documents=chunks, embeddings=embeddings, metadatas=metadatas, ids=ids)


def query_chunks(question: str, top_k: int) -> list[dict]:
    """Query ChromaDB with cosine similarity and return results normalized to 0–1 score."""
    collection = get_collection()
    query_embedding = embed_text(question)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    output: list[dict] = []
    documents = results.get("documents") or [[]]
    metadatas = results.get("metadatas") or [[]]
    distances = results.get("distances") or [[]]

    for doc, meta, dist in zip(documents[0], metadatas[0], distances[0]):
        # ChromaDB cosine distance is 0 (identical) to 2 (opposite); normalize to 0–1 similarity
        score = max(0.0, min(1.0, 1.0 - dist / 2.0))
        output.append({
            "text": doc,
            "metadata": meta,
            "score": score,
        })
    return output
