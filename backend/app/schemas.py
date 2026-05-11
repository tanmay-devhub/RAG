from pydantic import BaseModel


class IngestJobResponse(BaseModel):
    job_id: str
    filename: str
    status: str  # always "pending" on initial response


class JobStatusResponse(BaseModel):
    job_id: str
    filename: str
    status: str  # pending | processing | done | error
    chunks_done: int
    total_chunks: int
    entities_created: int
    relationships_created: int
    error: str | None


class Source(BaseModel):
    text: str
    source: str
    chunk_index: int
    score: float
    type: str


class QueryRequest(BaseModel):
    question: str
    top_k: int = 5


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]
