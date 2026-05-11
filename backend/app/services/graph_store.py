import os
import logging
from collections import defaultdict
from typing import Callable
from neo4j import GraphDatabase, Driver

logger = logging.getLogger(__name__)

_NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
_NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
_NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

_STOPWORDS = {
    "a", "an", "the", "is", "in", "of", "to", "and", "or", "for",
    "with", "that", "this", "it", "as", "be", "was", "are", "what",
    "how", "why", "who", "when", "where", "which", "do", "does",
}

_driver: Driver | None = None


def _get_driver() -> Driver:
    global _driver
    if _driver is None:
        driver = GraphDatabase.driver(
            _NEO4J_URI,
            auth=(_NEO4J_USER, _NEO4J_PASSWORD),
            max_connection_pool_size=50,   # tune for concurrency
            connection_timeout=30.0,
            connection_acquisition_timeout=60.0,
        )
        driver.verify_connectivity()
        _driver = driver
    return _driver


try:
    _get_driver()
except Exception as exc:
    logger.warning("Neo4j not reachable on startup: %s", exc)


def create_indexes() -> None:
    driver = _get_driver()
    with driver.session() as session:
        session.run("CREATE INDEX entity_name  IF NOT EXISTS FOR (e:Entity)   ON (e.name)")
        session.run("CREATE INDEX chunk_id     IF NOT EXISTS FOR (c:Chunk)    ON (c.id)")
        session.run("CREATE INDEX doc_filename IF NOT EXISTS FOR (d:Document) ON (d.filename)")
        session.run(
            "CREATE FULLTEXT INDEX chunk_text_index IF NOT EXISTS FOR (c:Chunk) ON EACH [c.text]"
        )


# ── ingest ────────────────────────────────────────────────────────────────────

def store_graph_documents_batch(
    graph_docs,
    chunks: list[str],
    filename: str,
    progress_cb: Callable[[int], None] | None = None,
) -> tuple[int, int]:
    """
    Write a full document's graph data to Neo4j using UNWIND batch queries.

    Instead of N individual queries (one per entity/relationship), this issues
    a small constant number of queries regardless of document size:
      - 1 query  → Document node
      - 1 query  → all Chunk nodes
      - 1 query  → all NEXT_CHUNK edges
      - 1 query  → all Entity nodes (deduplicated)
      - 1 query  → all MENTIONS edges
      - K queries → entity-entity relationships, grouped by relationship type

    This reduces Neo4j round-trips from O(entities + relationships) to O(1)
    per document — critical at 10K+ document scale.
    """
    driver = _get_driver()

    # ── collect all data up-front ────────────────────────────────────────────
    chunk_rows: list[dict]          = []
    entity_map: dict[str, dict]     = {}   # deduplicate by name
    mentions_rows: list[dict]       = []
    rel_by_type: dict[str, list]    = defaultdict(list)

    for idx, (graph_doc, chunk_text) in enumerate(zip(graph_docs, chunks)):
        chunk_id = f"{filename}_{idx}"
        chunk_rows.append({
            "id": chunk_id, "text": chunk_text,
            "filename": filename, "chunk_index": idx,
        })

        # Explicit entity nodes
        for node in graph_doc.nodes:
            name = node.id
            if name not in entity_map:
                entity_map[name] = {
                    "name": name, "type": node.type or "Entity",
                    "filename": filename, "chunk_index": idx,
                }
            mentions_rows.append({"chunk_id": chunk_id, "entity_name": name})

        # Relationship endpoints — also get MENTIONS edges
        for rel in graph_doc.relationships:
            for name, node_obj in [(rel.source.id, rel.source), (rel.target.id, rel.target)]:
                if name not in entity_map:
                    entity_map[name] = {
                        "name": name, "type": node_obj.type or "Entity",
                        "filename": filename, "chunk_index": idx,
                    }
                mentions_rows.append({"chunk_id": chunk_id, "entity_name": name})

            safe_type = rel.type.upper().replace(" ", "_").replace("-", "_")
            rel_by_type[safe_type].append({
                "source": rel.source.id, "target": rel.target.id,
                "filename": filename, "chunk_index": idx,
            })

        if progress_cb:
            progress_cb(idx + 1)

    entity_rows = list(entity_map.values())
    entities_created    = 0
    relationships_created = 0

    with driver.session() as session:
        # 1. Document registry node
        session.run(
            """
            MERGE (d:Document {filename: $filename})
            SET d.chunk_count = $chunk_count, d.ingested_at = datetime()
            """,
            filename=filename, chunk_count=len(chunks),
        )

        # 2. All Chunk nodes in one UNWIND
        session.run(
            """
            UNWIND $chunks AS c
            MERGE (ch:Chunk {id: c.id})
            SET ch.text = c.text, ch.filename = c.filename, ch.chunk_index = c.chunk_index
            """,
            chunks=chunk_rows,
        )

        # 3. NEXT_CHUNK chain — link consecutive chunks
        if len(chunk_rows) > 1:
            pairs = [
                {"a": chunk_rows[i]["id"], "b": chunk_rows[i + 1]["id"]}
                for i in range(len(chunk_rows) - 1)
            ]
            session.run(
                """
                UNWIND $pairs AS p
                MATCH (a:Chunk {id: p.a})
                MATCH (b:Chunk {id: p.b})
                MERGE (a)-[:NEXT_CHUNK]->(b)
                """,
                pairs=pairs,
            )

        # 4. All Entity nodes (deduplicated) in one UNWIND
        if entity_rows:
            result = session.run(
                """
                UNWIND $entities AS e
                MERGE (ent:Entity {name: e.name})
                ON CREATE SET ent.type = e.type, ent.filename = e.filename,
                              ent.chunk_index = e.chunk_index
                RETURN count(ent) AS n
                """,
                entities=entity_rows,
            )
            summary = result.consume()
            entities_created = summary.counters.nodes_created

        # 5. All MENTIONS edges in one UNWIND
        if mentions_rows:
            # Deduplicate (chunk_id, entity_name) pairs before sending
            unique_mentions = list({(r["chunk_id"], r["entity_name"]): r for r in mentions_rows}.values())
            session.run(
                """
                UNWIND $pairs AS p
                MATCH (c:Chunk  {id:   p.chunk_id})
                MATCH (e:Entity {name: p.entity_name})
                MERGE (c)-[:MENTIONS]->(e)
                """,
                pairs=unique_mentions,
            )

        # 6. Entity-entity relationships — one UNWIND per relationship type
        for rel_type, rels in rel_by_type.items():
            result = session.run(
                f"""
                UNWIND $rels AS r
                MERGE (a:Entity {{name: r.source}})
                MERGE (b:Entity {{name: r.target}})
                MERGE (a)-[rel:{rel_type}]->(b)
                ON CREATE SET rel.filename = r.filename, rel.chunk_index = r.chunk_index
                """,
                rels=rels,
            )
            summary = result.consume()
            relationships_created += summary.counters.relationships_created

    return entities_created, relationships_created


# ── retrieval ─────────────────────────────────────────────────────────────────

def query_chunks(question: str, top_k: int) -> list[dict]:
    """
    Three-strategy retrieval for a given question:

      1. Full-text Lucene search on Chunk.text          — broad keyword match
      2. Entity keyword match → direct MENTIONS → Chunk  — entity-driven
      3. Multi-hop: entity → related entities → Chunk    — graph traversal

    Strategies 2+3 also include adjacent NEXT_CHUNK neighbours for
    sentence-boundary context continuity.
    Results are deduplicated by chunk id before returning.
    """
    keywords = [
        w.strip(".,!?;:\"'()")
        for w in question.split()
        if w.lower().strip(".,!?;:\"'()") not in _STOPWORDS and len(w) > 2
    ]
    if not keywords:
        return []

    driver = _get_driver()
    seen:    set[str]   = set()
    results: list[dict] = []

    def _add(record: dict, score: float) -> None:
        cid = record["chunk_id"]
        if cid not in seen:
            seen.add(cid)
            results.append({
                "text":        record["text"],
                "source":      record["filename"],
                "chunk_index": int(record["chunk_index"]),
                "score":       score,
                "type":        "graph",
            })

    with driver.session() as session:

        # ── 1. Full-text index search ────────────────────────────────────────
        try:
            records = session.run(
                """
                CALL db.index.fulltext.queryNodes("chunk_text_index", $query)
                YIELD node, score
                RETURN node.text        AS text,
                       node.filename    AS filename,
                       node.chunk_index AS chunk_index,
                       node.id          AS chunk_id,
                       score
                LIMIT $limit
                """,
                query=" ".join(keywords),
                limit=top_k * 3,
            )
            for r in records:
                _add(dict(r), float(r["score"]))
        except Exception as exc:
            logger.warning("Full-text search failed: %s", exc)

        # ── 2+3. Entity search + multi-hop traversal ─────────────────────────
        for keyword in keywords:
            records = session.run(
                """
                MATCH (e:Entity)
                WHERE toLower(e.name) CONTAINS toLower($kw)

                // Hop 0: chunks that directly mention this entity
                MATCH (c0:Chunk)-[:MENTIONS]->(e)

                // Hop 1: related entities (1 relationship away) and their chunks
                OPTIONAL MATCH (e)--(rel_e:Entity)
                OPTIONAL MATCH (c1:Chunk)-[:MENTIONS]->(rel_e)

                // Context continuity: prev and next chunks along the backbone
                OPTIONAL MATCH (c0)-[:NEXT_CHUNK]->(next0:Chunk)
                OPTIONAL MATCH (prev0:Chunk)-[:NEXT_CHUNK]->(c0)

                WITH collect(DISTINCT c0)   +
                     collect(DISTINCT c1)   +
                     collect(DISTINCT next0) +
                     collect(DISTINCT prev0) AS all_chunks
                UNWIND all_chunks AS chunk
                WHERE chunk IS NOT NULL
                RETURN DISTINCT
                       chunk.text        AS text,
                       chunk.filename    AS filename,
                       chunk.chunk_index AS chunk_index,
                       chunk.id          AS chunk_id
                LIMIT 25
                """,
                kw=keyword,
            )
            for r in records:
                _add(dict(r), 0.5)

    return results


# ── graph visualisation ───────────────────────────────────────────────────────

def get_ingested_files() -> dict:
    """Return all ingested documents from the Document registry."""
    driver = _get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (d:Document)
            RETURN d.filename AS filename, d.chunk_count AS chunks
            ORDER BY d.filename
            """
        )
        files = [{"filename": r["filename"], "chunks": r["chunks"]} for r in result]
    return {"files": files}


def get_all_graph_data(filename: str | None = None) -> dict:
    """
    Return graph data for D3 visualisation.
    When filename is given, only nodes/edges belonging to that document are returned.
    """
    driver = _get_driver()
    nodes: dict[str, dict] = {}
    links: list[dict]      = []

    with driver.session() as session:
        if filename:
            # ── per-document view ────────────────────────────────────────────
            for r in session.run(
                "MATCH (c:Chunk {filename:$fn}) RETURN c.id AS id, c.filename AS filename, c.chunk_index AS chunk_index ORDER BY c.chunk_index",
                fn=filename,
            ):
                nodes[r["id"]] = {"id": r["id"], "label": f"Chunk {r['chunk_index']}", "filename": r["filename"] or "", "nodeType": "chunk"}

            for r in session.run(
                "MATCH (c:Chunk {filename:$fn})-[:MENTIONS]->(e:Entity) RETURN DISTINCT e.name AS name, e.type AS type LIMIT 500",
                fn=filename,
            ):
                nodes[r["name"]] = {"id": r["name"], "label": r["name"], "filename": filename, "nodeType": "entity", "type": r["type"] or "Entity"}

            for r in session.run(
                "MATCH (a:Chunk {filename:$fn})-[:NEXT_CHUNK]->(b:Chunk {filename:$fn}) RETURN a.id AS source, b.id AS target",
                fn=filename,
            ):
                links.append({"source": r["source"], "target": r["target"], "type": "NEXT_CHUNK"})

            for r in session.run(
                "MATCH (c:Chunk {filename:$fn})-[:MENTIONS]->(e:Entity) RETURN c.id AS source, e.name AS target LIMIT 2000",
                fn=filename,
            ):
                links.append({"source": r["source"], "target": r["target"], "type": "MENTIONS"})

            for r in session.run(
                """
                MATCH (c1:Chunk {filename:$fn})-[:MENTIONS]->(a:Entity)-[r]->(b:Entity)<-[:MENTIONS]-(c2:Chunk {filename:$fn})
                RETURN DISTINCT a.name AS source, b.name AS target, type(r) AS type LIMIT 1000
                """,
                fn=filename,
            ):
                links.append({"source": r["source"], "target": r["target"], "type": r["type"]})

        else:
            # ── all documents ────────────────────────────────────────────────
            for r in session.run("MATCH (c:Chunk) RETURN c.id AS id, c.filename AS filename, c.chunk_index AS chunk_index LIMIT 500"):
                nodes[r["id"]] = {"id": r["id"], "label": f"Chunk {r['chunk_index']}", "filename": r["filename"] or "", "nodeType": "chunk"}

            for r in session.run("MATCH (e:Entity) RETURN e.name AS name, e.filename AS filename, e.type AS type LIMIT 1000"):
                nodes[r["name"]] = {"id": r["name"], "label": r["name"], "filename": r["filename"] or "", "nodeType": "entity", "type": r["type"] or "Entity"}

            for r in session.run("MATCH (a:Chunk)-[:NEXT_CHUNK]->(b:Chunk) RETURN a.id AS source, b.id AS target LIMIT 500"):
                links.append({"source": r["source"], "target": r["target"], "type": "NEXT_CHUNK"})

            for r in session.run("MATCH (c:Chunk)-[:MENTIONS]->(e:Entity) RETURN c.id AS source, e.name AS target LIMIT 3000"):
                links.append({"source": r["source"], "target": r["target"], "type": "MENTIONS"})

            for r in session.run("MATCH (a:Entity)-[r]->(b:Entity) RETURN a.name AS source, b.name AS target, type(r) AS type LIMIT 2000"):
                links.append({"source": r["source"], "target": r["target"], "type": r["type"] or "RELATES_TO"})

    return {"nodes": list(nodes.values()), "links": links}


def clear_graph() -> dict:
    driver = _get_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (n) WHERE n:Chunk OR n:Entity OR n:Document DETACH DELETE n RETURN count(n) AS deleted"
        )
        deleted = result.single()["deleted"]
    return {"deleted": deleted}
