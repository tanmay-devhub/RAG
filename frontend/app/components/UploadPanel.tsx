"use client";
import { useState, useCallback, DragEvent, ChangeEvent } from "react";
import { ingestFile, IngestResponse } from "@/lib/api";

export default function UploadPanel() {
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState<IngestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFile = useCallback(async (file: File) => {
    setSuccess(null);
    setError(null);
    setLoading(true);
    try {
      const res = await ingestFile(file);
      setSuccess(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }, []);

  const onDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const onInputChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
      e.target.value = "";
    },
    [handleFile]
  );

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-base font-semibold text-gray-700">Upload Document</h2>
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`relative flex flex-col items-center justify-center border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors
          ${dragging ? "border-blue-400 bg-blue-50" : "border-gray-300 bg-gray-50 hover:border-blue-300"}`}
      >
        <input
          type="file"
          accept=".pdf,.txt"
          className="absolute inset-0 opacity-0 cursor-pointer"
          onChange={onInputChange}
        />
        <svg className="w-10 h-10 text-gray-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
        <p className="text-sm text-gray-600 font-medium">Drag &amp; drop or click to upload</p>
        <p className="text-xs text-gray-400 mt-1">PDF or TXT files</p>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-sm text-blue-600">
          <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
          </svg>
          Indexing…
        </div>
      )}

      {success && (
        <div className="rounded-lg bg-green-50 border border-green-200 p-3 text-sm text-green-800">
          Indexed <strong>{success.chunks_created}</strong> chunks,{" "}
          <strong>{success.entities_created}</strong> entities,{" "}
          <strong>{success.relationships_created}</strong> relationships from{" "}
          <em>{success.filename}</em>
        </div>
      )}

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-800 break-words">
          {error}
        </div>
      )}
    </div>
  );
}
