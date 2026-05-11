const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

// ── ingest ────────────────────────────────────────────────────────────────────

export interface IngestJobResponse {
  job_id: string;
  filename: string;
  status: string;
}

export interface JobStatusResponse {
  job_id:                string;
  filename:              string;
  status:                "pending" | "processing" | "done" | "error";
  chunks_done:           number;
  total_chunks:          number;
  entities_created:      number;
  relationships_created: number;
  error:                 string | null;
}

export async function startIngest(file: File): Promise<IngestJobResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/ingest`, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Ingest failed with status ${res.status}`);
  }
  return res.json() as Promise<IngestJobResponse>;
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const res = await fetch(`${API_BASE}/ingest/status/${jobId}`);
  if (!res.ok) throw new Error(`Status check failed: ${res.status}`);
  return res.json() as Promise<JobStatusResponse>;
}

export async function listJobs(): Promise<JobStatusResponse[]> {
  const res = await fetch(`${API_BASE}/ingest/jobs`);
  if (!res.ok) return [];
  const data = await res.json() as { jobs: JobStatusResponse[] };
  return data.jobs;
}

// ── query ─────────────────────────────────────────────────────────────────────

export interface Source {
  text:        string;
  source:      string;
  chunk_index: number;
  score:       number;
  type:        string;
}

export interface QueryResponse {
  answer:  string;
  sources: Source[];
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

// ── graph ─────────────────────────────────────────────────────────────────────

export async function clearGraph(): Promise<{ deleted: number }> {
  const res = await fetch(`${API_BASE}/graph`, { method: "DELETE" });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Clear failed with status ${res.status}`);
  }
  return res.json() as Promise<{ deleted: number }>;
}
