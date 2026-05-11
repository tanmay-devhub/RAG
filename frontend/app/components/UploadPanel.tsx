"use client";
import { useState, useCallback, useEffect, useRef, DragEvent, ChangeEvent } from "react";
import { startIngest, getJobStatus, clearGraph, JobStatusResponse } from "@/lib/api";

type LocalStatus = "queued" | "submitted" | "pending" | "processing" | "done" | "error";

interface FileEntry {
  id:      string;
  file:    File;
  jobId:   string | null;
  status:  LocalStatus;
  job:     JobStatusResponse | null;
  error:   string | null;
}

let _ctr = 0;
const uid = () => String(++_ctr);

export default function UploadPanel() {
  const [dragging, setDragging]         = useState(false);
  const [queue, setQueue]               = useState<FileEntry[]>([]);
  const [confirmClear, setConfirmClear] = useState(false);
  const [clearing, setClearing]         = useState(false);
  const [clearMsg, setClearMsg]         = useState<string | null>(null);

  // keep a ref so the polling interval always reads the latest queue
  const queueRef = useRef<FileEntry[]>(queue);
  queueRef.current = queue;

  const update = useCallback((id: string, patch: Partial<FileEntry>) => {
    setQueue(q => q.map(e => e.id === id ? { ...e, ...patch } : e));
  }, []);

  // ── submit files to backend (all in parallel, non-blocking) ───────────────
  const submitFiles = useCallback(async (entries: FileEntry[]) => {
    await Promise.all(entries.map(async entry => {
      update(entry.id, { status: "submitted" });
      try {
        const res = await startIngest(entry.file);
        update(entry.id, { jobId: res.job_id, status: "pending" });
      } catch (err) {
        update(entry.id, {
          status: "error",
          error: err instanceof Error ? err.message : "Submission failed",
        });
      }
    }));
  }, [update]);

  // ── add files ─────────────────────────────────────────────────────────────
  const addFiles = useCallback((files: File[]) => {
    const supported = files.filter(f =>
      f.name.toLowerCase().endsWith(".pdf") || f.name.toLowerCase().endsWith(".txt")
    );
    if (!supported.length) return;

    const entries: FileEntry[] = supported.map(f => ({
      id: uid(), file: f, jobId: null,
      status: "queued", job: null, error: null,
    }));

    setQueue(q => {
      const next = [...q, ...entries];
      setTimeout(() => submitFiles(entries), 0);
      return next;
    });
  }, [submitFiles]);

  // ── poll active jobs every 2 s ────────────────────────────────────────────
  useEffect(() => {
    const timer = setInterval(async () => {
      const active = queueRef.current.filter(
        e => e.jobId && (e.status === "pending" || e.status === "processing")
      );
      if (active.length === 0) return;

      await Promise.all(active.map(async entry => {
        if (!entry.jobId) return;
        try {
          const job = await getJobStatus(entry.jobId);
          update(entry.id, { status: job.status as LocalStatus, job });
        } catch {
          // network blip — keep polling
        }
      }));
    }, 2000);

    return () => clearInterval(timer);
  }, [update]); // runs once; uses queueRef for latest queue state

  // ── drag-and-drop ─────────────────────────────────────────────────────────
  const onDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    addFiles(Array.from(e.dataTransfer.files));
  }, [addFiles]);

  const onInputChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) addFiles(Array.from(e.target.files));
    e.target.value = "";
  }, [addFiles]);

  // ── clear graph ───────────────────────────────────────────────────────────
  const handleClearGraph = useCallback(async () => {
    setClearing(true);
    setClearMsg(null);
    setConfirmClear(false);
    try {
      const res = await clearGraph();
      setClearMsg(`Deleted ${res.deleted} nodes.`);
      setQueue([]);
    } catch (err) {
      setClearMsg(err instanceof Error ? err.message : "Clear failed");
    } finally {
      setClearing(false);
    }
  }, []);

  // ── derived ───────────────────────────────────────────────────────────────
  const total      = queue.length;
  const doneCount  = queue.filter(e => e.status === "done").length;
  const activeCount = queue.filter(e => e.status === "pending" || e.status === "processing").length;

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-base font-semibold text-gray-700">Upload Documents</h2>

      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`relative flex flex-col items-center justify-center border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors
          ${dragging ? "border-blue-400 bg-blue-50" : "border-gray-300 bg-gray-50 hover:border-blue-300"}`}
      >
        <input type="file" accept=".pdf,.txt" multiple
          className="absolute inset-0 opacity-0 cursor-pointer"
          onChange={onInputChange} />
        <svg className="w-10 h-10 text-gray-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
        <p className="text-sm text-gray-600 font-medium">Drag &amp; drop or click to upload</p>
        <p className="text-xs text-gray-400 mt-1">PDF or TXT · multiple files</p>
      </div>

      {/* Summary bar */}
      {total > 0 && (
        <div className="flex items-center justify-between text-xs text-gray-500 px-1">
          <span>
            {doneCount}/{total} indexed
            {activeCount > 0 && <span className="ml-1 text-blue-500">· {activeCount} processing…</span>}
          </span>
          {activeCount === 0 && (
            <button onClick={() => setQueue([])} className="text-gray-400 hover:text-gray-600 underline">
              Clear list
            </button>
          )}
        </div>
      )}

      {/* Per-file cards */}
      {queue.length > 0 && (
        <ul className="flex flex-col gap-2 max-h-72 overflow-y-auto pr-1">
          {queue.map(entry => (
            <FileCard key={entry.id} entry={entry} />
          ))}
        </ul>
      )}

      {/* Graph management */}
      <div className="border-t border-gray-200 pt-4 mt-2">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Graph Management</h3>

        {!confirmClear ? (
          <button
            onClick={() => { setConfirmClear(true); setClearMsg(null); }}
            disabled={clearing}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-red-300 text-red-600 text-sm font-medium hover:bg-red-50 transition-colors disabled:opacity-50"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            Clear Graph
          </button>
        ) : (
          <div className="rounded-lg border border-red-300 bg-red-50 p-3 flex flex-col gap-2">
            <p className="text-xs text-red-700 font-medium">Delete all nodes and relationships?</p>
            <div className="flex gap-2">
              <button onClick={handleClearGraph}
                className="flex-1 py-1.5 rounded-md bg-red-600 text-white text-xs font-semibold hover:bg-red-700 transition-colors">
                Yes, delete
              </button>
              <button onClick={() => setConfirmClear(false)}
                className="flex-1 py-1.5 rounded-md bg-white border border-gray-300 text-gray-600 text-xs font-semibold hover:bg-gray-50 transition-colors">
                Cancel
              </button>
            </div>
          </div>
        )}

        {clearing && (
          <div className="flex items-center gap-2 text-sm text-red-500 mt-2">
            <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
            Clearing…
          </div>
        )}
        {clearMsg && (
          <div className={`rounded-lg p-3 text-xs mt-2 ${clearMsg.startsWith("Deleted")
            ? "bg-green-50 border border-green-200 text-green-800"
            : "bg-red-50 border border-red-200 text-red-800"}`}>
            {clearMsg}
          </div>
        )}
      </div>
    </div>
  );
}

// ── file card ─────────────────────────────────────────────────────────────────

function FileCard({ entry }: { entry: FileEntry }) {
  const { file, status, job, error } = entry;
  const pct = job && job.total_chunks > 0
    ? Math.round((job.chunks_done / job.total_chunks) * 100)
    : null;

  return (
    <li className="rounded-lg border border-gray-200 bg-white p-3">
      <div className="flex items-center gap-2">
        <StatusIcon status={status} />
        <span className="text-xs font-medium text-gray-700 truncate flex-1" title={file.name}>
          {file.name}
        </span>
        <span className="text-xs text-gray-400 shrink-0">
          {(file.size / 1024).toFixed(0)} KB
        </span>
      </div>

      {/* Progress bar */}
      {(status === "pending" || status === "processing") && job && job.total_chunks > 0 && (
        <div className="mt-2">
          <div className="flex justify-between text-xs text-gray-400 mb-1">
            <span>{status === "processing" ? "Extracting graph…" : "Queued"}</span>
            <span>{job.chunks_done}/{job.total_chunks} chunks</span>
          </div>
          <div className="w-full bg-gray-100 rounded-full h-1.5">
            <div
              className="bg-blue-500 h-1.5 rounded-full transition-all duration-500"
              style={{ width: `${pct ?? 0}%` }}
            />
          </div>
        </div>
      )}

      {/* Result */}
      {status === "done" && job && (
        <p className="mt-1.5 text-xs text-green-700">
          {job.chunks_done} chunks · {job.entities_created} entities · {job.relationships_created} relationships
        </p>
      )}
      {status === "error" && (
        <p className="mt-1.5 text-xs text-red-600 break-words">{error}</p>
      )}
    </li>
  );
}

function StatusIcon({ status }: { status: LocalStatus }) {
  if (status === "queued" || status === "submitted") return (
    <svg className="w-4 h-4 text-gray-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <circle cx="12" cy="12" r="10" strokeWidth="2" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6v6l4 2" />
    </svg>
  );
  if (status === "pending" || status === "processing") return (
    <svg className="animate-spin w-4 h-4 text-blue-500 shrink-0" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
    </svg>
  );
  if (status === "done") return (
    <svg className="w-4 h-4 text-green-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
    </svg>
  );
  return (
    <svg className="w-4 h-4 text-red-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}
