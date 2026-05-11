import os
import logging
from collections import defaultdict
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import fitz  # PyMuPDF
from langchain_core.documents import Document
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_ollama import ChatOllama

from app.schemas import IngestJobResponse, JobStatusResponse
from app.services import chunker, graph_store, job_store

logger = logging.getLogger(__name__)
router = APIRouter()

_transformer: LLMGraphTransformer | None = None


def _get_transformer() -> LLMGraphTransformer:
    global _transformer
    if _transformer is None:
        chat_llm = ChatOllama(
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=os.getenv("GRAPH_MODEL", "gpt-oss:20b-cloud"),
        )
        _transformer = LLMGraphTransformer(llm=chat_llm, ignore_tool_usage=True)
    return _transformer


def _extract_text(filename: str, data: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        doc = fitz.open(stream=data, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    return data.decode("utf-8")


# ── background worker ─────────────────────────────────────────────────────────

def _run_ingest(job_id: str, filename: str, data: bytes) -> None:
    """
    Synchronous ingestion worker — runs in FastAPI's thread-pool via BackgroundTasks.

    Steps:
      1. Extract text from file
      2. Chunk the text
      3. Run LLMGraphTransformer across all chunks in one batch call
      4. Batch-write everything to Neo4j (UNWIND — O(1) queries per document)
      5. Update job status as progress is made
    """
    job_store.update_job(job_id, status="processing")
    try:
        text = _extract_text(filename, data)
        if not text.strip():
            raise ValueError("File contains no extractable text")

        chunks = chunker.chunk_text(text)
        job_store.update_job(job_id, total_chunks=len(chunks))

        docs = [Document(page_content=chunk) for chunk in chunks]

        # LLMGraphTransformer.convert_to_graph_documents is synchronous;
        # running here in the thread-pool avoids blocking the event loop.
        transformer = _get_transformer()
        graph_docs = transformer.convert_to_graph_documents(docs)

        entities_created, relationships_created = graph_store.store_graph_documents_batch(
            graph_docs, chunks, filename,
            progress_cb=lambda done: job_store.update_job(job_id, chunks_done=done),
        )

        job_store.update_job(
            job_id,
            status="done",
            chunks_done=len(chunks),
            entities_created=entities_created,
            relationships_created=relationships_created,
        )
        logger.info("Job %s done: %s — %d chunks, %d entities, %d rels",
                    job_id, filename, len(chunks), entities_created, relationships_created)

    except Exception as exc:
        logger.error("Job %s failed: %s", job_id, exc)
        job_store.update_job(job_id, status="error", error=str(exc))


# ── routes ────────────────────────────────────────────────────────────────────

@router.post("/ingest", response_model=IngestJobResponse, status_code=202)
async def ingest(background_tasks: BackgroundTasks, file: UploadFile = File(...)) -> IngestJobResponse:
    """
    Accept a file upload and return immediately with a job_id.
    The actual graph extraction and storage happens in the background.
    Poll GET /ingest/status/{job_id} to track progress.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    filename = file.filename
    if not (filename.lower().endswith(".pdf") or filename.lower().endswith(".txt")):
        raise HTTPException(status_code=400, detail="Only .pdf and .txt files are supported")

    data = await file.read()
    job_id = job_store.create_job(filename)

    # BackgroundTasks runs sync functions in Starlette's thread pool
    background_tasks.add_task(_run_ingest, job_id, filename, data)

    return IngestJobResponse(job_id=job_id, filename=filename, status="pending")


@router.get("/ingest/status/{job_id}", response_model=JobStatusResponse)
async def ingest_status(job_id: str) -> JobStatusResponse:
    """Return the current status of an ingest job."""
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(**job)


@router.get("/ingest/jobs")
async def list_ingest_jobs() -> dict:
    """Return all known ingest jobs (useful for UI recovery after page refresh)."""
    return {"jobs": job_store.list_jobs()}
