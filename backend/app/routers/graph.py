import logging
from typing import Optional
from fastapi import APIRouter, Query
from app.services import graph_store

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/graph/files")
async def get_graph_files() -> dict:
    """Return the list of ingested document filenames."""
    try:
        return graph_store.get_ingested_files()
    except Exception as exc:
        logger.error("Failed to fetch file list: %s", exc)
        return {"files": []}


@router.get("/graph")
async def get_graph(filename: Optional[str] = Query(default=None)) -> dict:
    """Return graph data, optionally filtered to a single document."""
    try:
        return graph_store.get_all_graph_data(filename=filename)
    except Exception as exc:
        logger.error("Failed to fetch graph data: %s", exc)
        return {"nodes": [], "links": []}


@router.delete("/graph")
async def delete_graph() -> dict:
    """Delete all Chunk and Entity nodes from Neo4j."""
    try:
        return graph_store.clear_graph()
    except Exception as exc:
        logger.error("Failed to clear graph: %s", exc)
        return {"deleted": 0, "error": str(exc)}
