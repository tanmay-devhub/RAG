const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

export interface IngestResponse {
  chunks_created: number;
  entities_created: number;
  relationships_created: number;
  filename: string;
}

export interface Source {
  text: string;
  source: string;
  chunk_index: number;
  score: number;
  type: "vector" | "graph";
}

export interface QueryResponse {
  answer: string;
  sources: Source[];
}

export async function ingestFile(file: File): Promise<IngestResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/ingest`, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Ingest failed with status ${res.status}`);
  }
  return res.json() as Promise<IngestResponse>;
}

export async function queryRAG(question: string, topK: number): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, top_k: topK }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Query failed with status ${res.status}`);
  }
  return res.json() as Promise<QueryResponse>;
}
