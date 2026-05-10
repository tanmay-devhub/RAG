import logging
from fastapi import APIRouter
from app.schemas import QueryRequest, QueryResponse, Source
from app.services import vector_store, graph_store, llm

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    """Hybrid query: merge vector and graph results, then generate an answer with the LLM."""
    vector_results = vector_store.query_chunks(request.question, request.top_k)
    graph_results = graph_store.query_related(request.question, request.top_k)

    # Build merged list: vector results first, then graph-only (deduplicated by chunk_index)
    seen_chunks: set[int] = set()
    merged_sources: list[Source] = []

    for r in vector_results:
        meta = r["metadata"]
        chunk_index = int(meta.get("chunk_index", -1))
        seen_chunks.add(chunk_index)
        merged_sources.append(Source(
            text=r["text"],
            source=meta.get("source", "unknown"),
            chunk_index=chunk_index,
            score=r["score"],
            type="vector",
        ))

    for r in graph_results:
        chunk_index = int(r.get("chunk_index", -1))
        if chunk_index in seen_chunks:
            continue
        seen_chunks.add(chunk_index)
        merged_sources.append(Source(
            text=r["text"],
            source=r.get("source", "unknown"),
            chunk_index=chunk_index,
            score=r["score"],
            type="graph",
        ))

    context_chunks = [s.text for s in merged_sources]
    answer = llm.generate_answer(request.question, context_chunks)

    return QueryResponse(answer=answer, sources=merged_sources)
