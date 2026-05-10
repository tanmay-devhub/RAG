import os
import logging
from neo4j import GraphDatabase, Driver

logger = logging.getLogger(__name__)

_NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
_NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
_NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "graphrag123")

_STOPWORDS = {"a", "the", "is", "in", "of", "to", "and", "or", "for", "with", "that", "this", "it", "as", "be", "was", "are"}

_driver: Driver | None = None


def _get_driver() -> Driver:
    """Return the Neo4j driver, initializing it on first call."""
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(_NEO4J_URI, auth=(_NEO4J_USER, _NEO4J_PASSWORD))
        _driver.verify_connectivity()
    return _driver


# Initialize driver on module load
try:
    _get_driver()
except Exception as exc:
    logger.warning("Neo4j not reachable on startup: %s", exc)


def create_indexes() -> None:
    """Create indexes on :Entity(name) and :Document(filename) if they do not exist."""
    driver = _get_driver()
    with driver.session() as session:
        session.run(
            "CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)"
        )
        session.run(
            "CREATE INDEX document_filename IF NOT EXISTS FOR (d:Document) ON (d.filename)"
        )


def store_entities(
    entities: list[str],
    relationships: list[tuple[str, str, str]],
    filename: str,
    chunk_index: int,
) -> tuple[int, int]:
    """Store entities and relationships in Neo4j; return (entities_created, relationships_created)."""
    driver = _get_driver()
    entities_created = 0
    relationships_created = 0

    with driver.session() as session:
        for entity in entities:
            result = session.run(
                """
                MERGE (e:Entity {name: $name})
                ON CREATE SET e.filename = $filename, e.chunk_index = $chunk_index
                RETURN e
                """,
                name=entity,
                filename=filename,
                chunk_index=chunk_index,
            )
            summary = result.consume()
            entities_created += summary.counters.nodes_created

        for entity_a, relation_type, entity_b in relationships:
            safe_rel = relation_type.upper().replace(" ", "_").replace("-", "_")
            result = session.run(
                f"""
                MERGE (a:Entity {{name: $entity_a}})
                MERGE (b:Entity {{name: $entity_b}})
                MERGE (a)-[r:RELATION {{type: $relation_type}}]->(b)
                RETURN r
                """,
                entity_a=entity_a,
                entity_b=entity_b,
                relation_type=safe_rel,
            )
            summary = result.consume()
            relationships_created += summary.counters.relationships_created

    return entities_created, relationships_created


def query_related(question: str, top_k: int) -> list[dict]:
    """Search graph for entities matching question keywords and return formatted results."""
    keywords = [
        word.strip(".,!?;:\"'")
        for word in question.split()
        if word.lower().strip(".,!?;:\"'") not in _STOPWORDS and len(word) > 2
    ]

    driver = _get_driver()
    seen_chunks: set[int] = set()
    results: list[dict] = []

    with driver.session() as session:
        for keyword in keywords:
            records = session.run(
                """
                MATCH (e:Entity)
                WHERE toLower(e.name) CONTAINS toLower($kw)
                MATCH (e)-[r]-(related)
                RETURN e.name AS entity_a, type(r) AS rel_type, related.name AS entity_b,
                       e.filename AS filename, e.chunk_index AS chunk_index
                LIMIT 10
                """,
                kw=keyword,
            )
            for record in records:
                chunk_index = record["chunk_index"]
                if chunk_index in seen_chunks:
                    continue
                seen_chunks.add(chunk_index)
                results.append({
                    "text": f"{record['entity_a']} -[{record['rel_type']}]-> {record['entity_b']}",
                    "source": record["filename"],
                    "chunk_index": chunk_index,
                    "score": 0.7,
                    "type": "graph",
                })
                if len(results) >= top_k:
                    return results

    return results
