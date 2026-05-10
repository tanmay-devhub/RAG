# GraphRAG

A local hybrid Retrieval-Augmented Generation system combining vector similarity search (ChromaDB) with knowledge graph traversal (Neo4j), powered by local LLMs via Ollama.

## Prerequisites

- Docker Desktop (latest)
- 8 GB RAM minimum
- ~10 GB free disk space (for model weights)

## Setup

```bash
# 1. Start all services
docker-compose up -d

# 2. Pull the embedding model
docker exec graphrag-ollama-1 ollama pull nomic-embed-text

# 3. Pull the LLM
docker exec graphrag-ollama-1 ollama pull llama3.2

# 4. Open the UI
open http://localhost:3000
```

Neo4j browser is available at http://localhost:7474 (user: `neo4j`, password: `graphrag123`).

## Architecture

Documents ingested through the UI are split into 500-character overlapping chunks. Each chunk is embedded with `nomic-embed-text` via Ollama and stored in ChromaDB for dense vector retrieval. Simultaneously, the LLM extracts named entities and relationships from each chunk and stores them as a property graph in Neo4j. At query time both retrieval paths run in parallel: ChromaDB returns the top-k most similar chunks by cosine similarity, while Neo4j matches entity names from the query against the graph and returns related triples. The two result sets are merged (vector results first, then graph-only results deduped by chunk index), and the combined context is sent to `llama3.2` via a strict RAG prompt that forbids hallucination. The frontend displays the answer and lets users inspect every source card with its origin tag (vector or graph) and similarity score.

## API Endpoints

| Method | Path      | Description                                              |
|--------|-----------|----------------------------------------------------------|
| POST   | /ingest   | Upload a PDF or .txt file; returns chunk/entity counts  |
| POST   | /query    | Ask a question; returns answer + ranked source list     |
| GET    | /health   | Returns liveness status of ChromaDB, Neo4j, and Ollama  |
