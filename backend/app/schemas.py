from pydantic import BaseModel


class IngestResponse(BaseModel):
    chunks_created: int
    entities_created: int
    relationships_created: int
    filename: str


class Source(BaseModel):
    text: str
    source: str
    chunk_index: int
    score: float
    type: str  # "vector" or "graph"


class QueryRequest(BaseModel):
    question: str
    top_k: int = 5


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]
