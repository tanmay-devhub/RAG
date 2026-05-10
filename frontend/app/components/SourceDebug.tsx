"use client";
import { Source } from "@/lib/api";

interface Props {
  sources: Source[];
}

export default function SourceDebug({ sources }: Props) {
  return (
    <div className="grid grid-cols-2 gap-2 mt-2">
      {sources.map((src, i) => (
        <div key={i} className="border border-gray-200 rounded-lg p-2 bg-white text-xs">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="font-medium text-gray-700 truncate max-w-[120px]" title={src.source}>
              {src.source.length > 30 ? src.source.slice(0, 30) + "…" : src.source}
            </span>
            {src.type === "vector" ? (
              <span className="bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded text-[10px] font-semibold">
                vector
              </span>
            ) : (
              <span className="bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded text-[10px] font-semibold">
                graph
              </span>
            )}
            <span className="ml-auto text-gray-500">{Math.round(src.score * 100)}%</span>
          </div>
          <p className="text-gray-600 leading-snug">
            {src.text.length > 200 ? src.text.slice(0, 200) + "…" : src.text}
          </p>
        </div>
      ))}
    </div>
  );
}
