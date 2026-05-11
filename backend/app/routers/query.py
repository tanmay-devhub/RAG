import logging
from fastapi import APIRouter
from app.schemas import QueryRequest, QueryResponse, Source
from app.services import graph_store, llm, reranker

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    """
    Query pipeline:
      1. Retrieve candidate chunks from Neo4j (full-text + entity traversal)
      2. Re-rank with HuggingFace cross-encoder
      3. Feed top-k into hybrid LLM prompt (RAG if relevant, general otherwise)
    """
    # Fetch more candidates than needed so the reranker has room to work
    candidates = graph_store.query_chunks(request.question, top_k=request.top_k * 4)
    ranked = reranker.rerank(request.question, candidates, top_k=request.top_k)

    sources = [
        Source(
            text=r["text"],
            source=r["source"],
            chunk_index=r["chunk_index"],
            score=r["score"],
            type="graph",
        )
        for r in ranked
    ]

    if sources:
        answer = llm.generate_answer(request.question, [s.text for s in sources])
    else:
        answer = llm.generate_general_answer(request.question)

    return QueryResponse(answer=answer, sources=sources)
