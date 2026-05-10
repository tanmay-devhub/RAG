import os
import logging
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import ingest, query
from app.services import graph_store, vector_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create Neo4j indexes on startup."""
    try:
        graph_store.create_indexes()
        logger.info("Neo4j indexes created")
    except Exception as exc:
        logger.warning("Could not create Neo4j indexes on startup: %s", exc)
    yield


app = FastAPI(title="GraphRAG API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router)
app.include_router(query.router)


@app.get("/health")
async def health() -> dict:
    """Check liveness of ChromaDB, Neo4j, and Ollama."""
    chroma_ok = False
    neo4j_ok = False
    ollama_ok = False

    try:
        collection = vector_store.get_collection()
        collection.count()
        chroma_ok = True
    except Exception as exc:
        logger.warning("ChromaDB health check failed: %s", exc)

    try:
        graph_store._get_driver().verify_connectivity()
        neo4j_ok = True
    except Exception as exc:
        logger.warning("Neo4j health check failed: %s", exc)

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(_OLLAMA_BASE_URL)
            ollama_ok = resp.status_code < 500
    except Exception as exc:
        logger.warning("Ollama health check failed: %s", exc)

    return {
        "status": "ok",
        "chromadb": chroma_ok,
        "neo4j": neo4j_ok,
        "ollama": ollama_ok,
    }
