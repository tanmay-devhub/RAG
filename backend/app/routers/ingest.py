import json
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
import fitz  # PyMuPDF
from app.schemas import IngestResponse
from app.services import chunker, vector_store, graph_store, llm

logger = logging.getLogger(__name__)
router = APIRouter()

_ENTITY_PROMPT_TEMPLATE = (
    "Extract named entities (people, organizations, technologies, concepts, locations) from this text.\n"
    "Return ONLY a JSON object in this format with no other text:\n"
    '{"entities": ["entity1", "entity2"], "relationships": [["entity1", "RELATES_TO", "entity2"]]}\n'
    "Text: {chunk}"
)


def _extract_text_from_pdf(data: bytes) -> str:
    """Extract and concatenate text from all pages of a PDF."""
    doc = fitz.open(stream=data, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)


def _extract_entities(chunk: str) -> dict:
    """Use the LLM to extract entities and relationships from a chunk; returns safe dict on failure."""
    prompt = _ENTITY_PROMPT_TEMPLATE.format(chunk=chunk)
    try:
        raw = llm.get_llm().invoke(prompt)
        # Find JSON object boundaries to handle any surrounding text
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON object found in LLM response")
        return json.loads(raw[start:end])
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Entity extraction failed: %s", exc)
        return {"entities": [], "relationships": []}


@router.post("/ingest", response_model=IngestResponse)
async def ingest(file: UploadFile = File(...)) -> IngestResponse:
    """Ingest a PDF or .txt file: chunk, embed, and store in ChromaDB and Neo4j."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    filename = file.filename
    data = await file.read()

    if filename.lower().endswith(".pdf"):
        text = _extract_text_from_pdf(data)
    elif filename.lower().endswith(".txt"):
        text = data.decode("utf-8")
    else:
        raise HTTPException(status_code=400, detail="Only .pdf and .txt files are supported")

    if not text.strip():
        raise HTTPException(status_code=400, detail="File contains no extractable text")

    chunks = chunker.chunk_text(text)
    total_entities = 0
    total_relationships = 0

    chunk_texts: list[str] = []
    chunk_metadatas: list[dict] = []
    chunk_ids: list[str] = []

    for idx, chunk in enumerate(chunks):
        chunk_texts.append(chunk)
        chunk_metadatas.append({"source": filename, "chunk_index": idx})
        chunk_ids.append(f"{filename}_{idx}")

        extracted = _extract_entities(chunk)
        entities: list[str] = extracted.get("entities", [])
        raw_rels = extracted.get("relationships", [])
        relationships: list[tuple[str, str, str]] = [
            (r[0], r[1], r[2]) for r in raw_rels if isinstance(r, list) and len(r) == 3
        ]

        ent_count, rel_count = graph_store.store_entities(entities, relationships, filename, idx)
        total_entities += ent_count
        total_relationships += rel_count

    vector_store.add_chunks(chunk_texts, chunk_metadatas, chunk_ids)

    return IngestResponse(
        chunks_created=len(chunks),
        entities_created=total_entities,
        relationships_created=total_relationships,
        filename=filename,
    )
