# GraphRAG

> **Pure Graph-Based Retrieval-Augmented Generation** knowledge graphs, not vector stores.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14-000000?style=flat&logo=next.js&logoColor=white)](https://nextjs.org)
[![Neo4j](https://img.shields.io/badge/Neo4j-5-008CC1?style=flat&logo=neo4j&logoColor=white)](https://neo4j.com)
[![LangChain](https://img.shields.io/badge/LangChain-Experimental-1C3C3C?style=flat)](https://python.langchain.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Overview

GraphRAG is a **fully local, privacy-first** document intelligence system that replaces the traditional vector similarity approach with a **property knowledge graph**. Documents are ingested as entity graphs every concept, person, technology, and relationship is stored as a native Neo4j node and edge. At query time, **multi-hop graph traversal** + **HuggingFace cross-encoder reranking** retrieves precise, grounded answers.

No external APIs. No embeddings database. No cloud dependency.

---

## Features

| Capability | Detail |
|---|---|
| **Graph extraction** | LangChain `LLMGraphTransformer` entities, relationships, and typed nodes |
| **Pure graph retrieval** | Full-text index + entity keyword match + 1-hop neighbour traversal |
| **Cross-encoder reranking** | `cross-encoder/ms-marco-MiniLM-L-6-v2` from HuggingFace |
| **Hybrid LLM answering** | Uses document context when relevant; falls back to general knowledge |
| **Async ingest pipeline** | `POST /ingest` returns immediately; background thread processes the file |
| **Batch Neo4j writes** | UNWIND-based bulk writes O(1) queries per document, not O(entities) |
| **Multi-document support** | Per-document graph views; shared entities bridge cross-doc queries |
| **Interactive graph** | D3.js force-directed graph chunk backbone + semantic edges + per-doc filter |
| **Fully local** | Ollama LLM · Neo4j Community · zero cloud required |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      INGESTION                          │
│                                                         │
│  PDF / TXT  →  Chunker  →  LLMGraphTransformer          │
│                                ↓                        │
│              (:Chunk)-[:NEXT_CHUNK]->(:Chunk)           │
│              (:Chunk)-[:MENTIONS]->(:Entity)            │
│              (:Entity)-[:REL_TYPE]->(:Entity)           │
│                                ↓                        │
│                 Neo4j 5  (UNWIND batch writes)          │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                       RETRIEVAL                         │
│                                                         │
│  Question                                               │
│     │                                                   │
│     ├─① Full-text index search on Chunk.text            │
│     ├─② Entity keyword → MENTIONS → Chunk               │
│     └─③ Entity → 1-hop related entities → their Chunks  │
│                  + NEXT_CHUNK context neighbours        │
│                                ↓                        │
│          HuggingFace Cross-Encoder Reranker             │
│                                ↓                        │
│          Hybrid LLM Prompt (RAG + general knowledge)    │
│                                ↓                        │
│                       Answer + Sources                  │
└─────────────────────────────────────────────────────────┘
```

**Neo4j schema:**

```
(:Document {filename, chunk_count, ingested_at})
(:Chunk    {id, text, filename, chunk_index})
(:Entity   {name, type, filename, chunk_index})

(:Chunk)-[:NEXT_CHUNK]->(:Chunk)             — document backbone
(:Chunk)-[:MENTIONS]->(:Entity)              — chunk ↔ entity provenance
(:Entity)-[:<SEMANTIC_TYPE>]->(:Entity)      — LLM-extracted relationships
```

---

## Tech Stack

### Backend
| Component | Technology |
|---|---|
| API framework | [FastAPI](https://fastapi.tiangolo.com) + Uvicorn |
| Graph extraction | [LangChain Experimental LLMGraphTransformer](https://python.langchain.com) |
| LLM inference | [Ollama](https://ollama.com) via `langchain-ollama` |
| Graph database | [Neo4j 5 Community](https://neo4j.com) |
| Reranker | [cross-encoder/ms-marco-MiniLM-L-6-v2](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L-6-v2) |
| PDF parsing | PyMuPDF |
| Text splitting | LangChain `RecursiveCharacterTextSplitter` |

### Frontend
| Component | Technology |
|---|---|
| Framework | [Next.js 14](https://nextjs.org) (App Router) |
| Language | TypeScript 5 |
| Styling | Tailwind CSS 3 |
| Graph visualisation | [D3.js v7](https://d3js.org) force-directed |

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | |
| Node.js | 20+ | |
| Neo4j | 5 Community+ | Running on `bolt://localhost:7687` |
| Ollama | Latest | Running on `http://localhost:11434` |

---

## Quick Start

### 1 — Clone

```bash
git clone https://github.com/your-username/graphrag.git
cd graphrag
```

### 2 — Pull the model

```bash
ollama pull gpt-oss:20b-cloud
```

### 3 — Configure

```bash
cp backend/.env.example backend/.env
# Edit backend/.env — set NEO4J_PASSWORD and model names
```

### 4 — Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows

pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

### 5 — Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **[http://localhost:3000](http://localhost:3000)**.

---

## Docker

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8080 |
| Neo4j Browser | http://localhost:7474 |
| Ollama | http://localhost:11434 |

> **First run:** pull the model inside the Ollama container:
> ```bash
> docker exec -it graphrag-ollama-1 ollama pull gpt-oss:20b-cloud
> ```

---

## Configuration

All backend configuration lives in `backend/.env`:

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `LLM_MODEL` | `gpt-oss:20b-cloud` | Model for chat / answer generation |
| `GRAPH_MODEL` | `gpt-oss:20b-cloud` | Model for `LLMGraphTransformer` entity extraction |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt connection URI |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | *(required)* | Neo4j password |

---

## API Reference

### Ingest

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/ingest` | Upload PDF or TXT returns `job_id` instantly (HTTP 202) |
| `GET` | `/ingest/status/{job_id}` | Poll ingest progress |
| `GET` | `/ingest/jobs` | List all jobs (page-refresh recovery) |

**POST /ingest response**
```json
{ "job_id": "550e8400-...", "filename": "paper.pdf", "status": "pending" }
```

**GET /ingest/status/{job_id} response**
```json
{
  "job_id": "550e8400-...",
  "filename": "paper.pdf",
  "status": "done",
  "chunks_done": 24,
  "total_chunks": 24,
  "entities_created": 87,
  "relationships_created": 43,
  "error": null
}
```

### Query

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/query` | Ask a question; returns answer + ranked sources |

**Request body**
```json
{ "question": "What deep learning techniques were used?", "top_k": 5 }
```

**Response**
```json
{
  "answer": "The paper uses 3D CNN on PPMI MRI scans with HPC multi-GPU training...",
  "sources": [
    {
      "text": "...",
      "source": "paper.pdf",
      "chunk_index": 3,
      "score": 0.9421,
      "type": "graph"
    }
  ]
}
```

### Graph

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/graph` | All nodes and edges (D3 format) |
| `GET` | `/graph?filename=doc.pdf` | Nodes and edges scoped to one document |
| `GET` | `/graph/files` | Ingested document list with chunk counts |
| `DELETE` | `/graph` | Wipe all Chunk, Entity, and Document nodes |

### Health

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Neo4j + Ollama connectivity status |

---

## Project Structure

```
graphrag/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app, CORS, lifespan indexes
│   │   ├── schemas.py              # Pydantic request / response models
│   │   ├── routers/
│   │   │   ├── ingest.py           # Async ingest + job status endpoints
│   │   │   ├── query.py            # Retrieval + reranking + LLM endpoint
│   │   │   └── graph.py            # Graph data, file list, delete
│   │   └── services/
│   │       ├── chunker.py          # Text splitting
│   │       ├── graph_store.py      # Neo4j batch UNWIND writes, multi-hop query
│   │       ├── job_store.py        # Thread-safe in-memory job registry
│   │       ├── llm.py              # Ollama RAG prompt + general prompt
│   │       └── reranker.py         # HuggingFace cross-encoder
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── page.tsx                # Root page Chat / Graph tabs
│   │   ├── layout.tsx
│   │   └── components/
│   │       ├── ChatWindow.tsx      # Query interface + message history
│   │       ├── UploadPanel.tsx     # Multi-file upload + job progress polling
│   │       ├── GraphView.tsx       # D3 force-graph with per-document filter
│   │       └── SourceDebug.tsx     # Source cards (score, snippet, type)
│   ├── lib/
│   │   └── api.ts                  # Typed fetch client
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

## How Retrieval Works

When a question arrives, three strategies execute against Neo4j and are merged before reranking:

1. **Full-text search**: Lucene index on `Chunk.text` matches question keywords directly in document text.
2. **Entity traversal**: Question keywords matched against `Entity.name`; `MENTIONS` edges walk back to the source `Chunk` nodes, and `NEXT_CHUNK` neighbours are included for sentence-boundary continuity.
3. **Multi-hop traversal**: From each matched entity, one semantic relationship hop reaches related entities, then their chunks. This surfaces context that shares no keywords with the question but is conceptually linked.

All candidates are deduplicated, then scored by a **cross-encoder** that evaluates the full `(question, chunk)` pair, significantly more accurate than cosine similarity. Top-k results feed a **hybrid LLM prompt** that cites document evidence when relevant and answers from general knowledge otherwise.

---

## Scaling to 10 000+ Documents

| Bottleneck | Solution implemented |
|---|---|
| Blocking ingest | Background thread via FastAPI `BackgroundTasks`; HTTP 202 returned instantly |
| N+1 Neo4j writes | `UNWIND` bulk queries **5–7 round-trips per document** regardless of entity count |
| Connection contention | Neo4j driver pool set to 50 connections with tuned acquisition timeout |
| Document listing | `(:Document)` registry nodes O(1) metadata lookup without scanning chunks |
| Cross-encoder cost | Candidates capped at `top_k × 4` before inference; reranker loaded once and cached |
| Large graph render | Per-document view isolates subgraphs; hard node/edge limits prevent browser freeze |

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes following [Conventional Commits](https://www.conventionalcommits.org/):
   ```
   feat: add streaming response support
   fix: handle empty entity list from LLM
   docs: update API reference
   ```
4. Push and open a Pull Request

---

## License

MIT © 2025 — see [LICENSE](LICENSE) for details.
