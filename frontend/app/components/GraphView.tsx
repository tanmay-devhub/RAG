"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import * as d3 from "d3";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

interface GraphNode extends d3.SimulationNodeDatum {
  id: string;
  label: string;
  filename: string;
  nodeType: "chunk" | "entity";
  type?: string;
}

interface RawLink { source: string; target: string; type: string; }
interface SimLink extends d3.SimulationLinkDatum<GraphNode> { type: string; }
interface GraphData { nodes: GraphNode[]; links: RawLink[]; }

function nodeOf(v: string | GraphNode): GraphNode | null {
  return typeof v === "object" ? v : null;
}
function linkColor(type: string) {
  if (type === "NEXT_CHUNK") return "#3b82f6";
  if (type === "MENTIONS")   return "#94a3b8";
  return "#f59e0b";
}
function linkWidth(type: string) {
  if (type === "NEXT_CHUNK") return 2.5;
  if (type === "MENTIONS")   return 1;
  return 1.5;
}

export default function GraphView() {
  const svgRef                                  = useRef<SVGSVGElement>(null);
  const [status, setStatus]                     = useState<"loading"|"empty"|"ready"|"error">("loading");
  const [counts, setCounts]                     = useState({ nodes: 0, links: 0 });
  const [files, setFiles]                       = useState<{ filename: string; chunks: number }[]>([]);
  const [selectedFile, setSelectedFile]         = useState<string | null>(null); // null = All

  // ── fetch available files on mount ────────────────────────────────────────
  useEffect(() => {
    fetch(`${API_BASE}/graph/files`)
      .then(r => r.json())
      .then((d: { files: { filename: string; chunks: number }[] }) => setFiles(d.files))
      .catch(() => {});
  }, []);

  // ── fetch & render graph whenever selected document changes ───────────────
  const renderGraph = useCallback((data: GraphData) => {
    if (!svgRef.current) return;
    const el     = svgRef.current;
    const width  = el.clientWidth  || 900;
    const height = el.clientHeight || 600;

    d3.select(el).selectAll("*").remove();

    const svg = d3.select(el);
    const g   = svg.append("g");

    svg.call(
      d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.08, 4])
        .on("zoom", ({ transform }) => g.attr("transform", transform.toString()))
    );

    const filesInGraph = [...new Set(data.nodes.map(n => n.filename))];
    const fileColor    = d3.scaleOrdinal<string>().domain(filesInGraph).range(d3.schemeTableau10);

    const nodes: GraphNode[] = data.nodes.map(n => ({ ...n }));
    const links: SimLink[]   = data.links.map(l => ({ ...l } as SimLink));

    const simulation = d3.forceSimulation<GraphNode>(nodes)
      .force("link", d3.forceLink<GraphNode, SimLink>(links)
        .id(d => d.id)
        .distance(d => {
          const t = (d as SimLink).type;
          return t === "NEXT_CHUNK" ? 160 : t === "MENTIONS" ? 90 : 120;
        }))
      .force("charge", d3.forceManyBody<GraphNode>()
        .strength(d => (d as GraphNode).nodeType === "chunk" ? -400 : -180))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide<GraphNode>(
        d => (d as GraphNode).nodeType === "chunk" ? 30 : 20));

    // Arrow markers
    const defs = svg.append("defs");
    [
      { id: "arr-bb", color: "#3b82f6" },
      { id: "arr-mn", color: "#94a3b8" },
      { id: "arr-sm", color: "#f59e0b" },
    ].forEach(({ id, color }) => {
      defs.append("marker")
        .attr("id", id).attr("viewBox", "0 -5 10 10")
        .attr("refX", 24).attr("refY", 0)
        .attr("markerWidth", 5).attr("markerHeight", 5)
        .attr("orient", "auto")
        .append("path").attr("d", "M0,-5L10,0L0,5").attr("fill", color);
    });

    const arrowId = (t: string) =>
      t === "NEXT_CHUNK" ? "url(#arr-bb)" : t === "MENTIONS" ? "url(#arr-mn)" : "url(#arr-sm)";

    const linkEls = g.append("g")
      .selectAll<SVGLineElement, SimLink>("line")
      .data(links).enter().append("line")
      .attr("stroke",           d => linkColor(d.type))
      .attr("stroke-width",     d => linkWidth(d.type))
      .attr("stroke-dasharray", d => d.type === "MENTIONS" ? "4,3" : null)
      .attr("stroke-opacity",   d => d.type === "MENTIONS" ? 0.5 : 0.85)
      .attr("marker-end",       d => arrowId(d.type));

    const linkLabels = g.append("g")
      .selectAll<SVGTextElement, SimLink>("text")
      .data(links.filter(l => l.type !== "NEXT_CHUNK" && l.type !== "MENTIONS"))
      .enter().append("text")
      .text(d => d.type)
      .attr("font-size", "7px").attr("fill", "#f59e0b")
      .attr("text-anchor", "middle").attr("pointer-events", "none");

    const nodeEls = g.append("g")
      .selectAll<SVGCircleElement, GraphNode>("circle")
      .data(nodes).enter().append("circle")
      .attr("r",            d => d.nodeType === "chunk" ? 16 : 10)
      .attr("fill",         d => d.nodeType === "chunk" ? "#1e40af" : fileColor(d.filename))
      .attr("stroke",       d => d.nodeType === "chunk" ? "#93c5fd" : "#fff")
      .attr("stroke-width", d => d.nodeType === "chunk" ? 3 : 1.5)
      .attr("fill-opacity", d => d.nodeType === "chunk" ? 0.9 : 1)
      .style("cursor", "grab")
      .call(
        d3.drag<SVGCircleElement, GraphNode>()
          .on("start", (ev, d) => { if (!ev.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
          .on("drag",  (ev, d) => { d.fx = ev.x; d.fy = ev.y; })
          .on("end",   (ev, d) => { if (!ev.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; })
      );

    nodeEls.append("title").text(d =>
      `${d.label}\n${d.nodeType === "chunk" ? "Chunk" : d.type || "Entity"}\n${d.filename}`
    );

    const nodeLabels = g.append("g")
      .selectAll<SVGTextElement, GraphNode>("text")
      .data(nodes).enter().append("text")
      .text(d => { const l = d.label || d.id; return l.length > 14 ? l.slice(0, 13) + "…" : l; })
      .attr("font-size",   "9px")
      .attr("font-weight", d => d.nodeType === "chunk" ? "700" : "400")
      .attr("fill",        d => d.nodeType === "chunk" ? "#dbeafe" : "#1e293b")
      .attr("text-anchor", "middle")
      .attr("dy",          d => d.nodeType === "chunk" ? 32 : 24)
      .attr("pointer-events", "none");

    simulation.on("tick", () => {
      linkEls
        .attr("x1", d => nodeOf(d.source)?.x ?? 0).attr("y1", d => nodeOf(d.source)?.y ?? 0)
        .attr("x2", d => nodeOf(d.target)?.x ?? 0).attr("y2", d => nodeOf(d.target)?.y ?? 0);
      linkLabels
        .attr("x", d => ((nodeOf(d.source)?.x ?? 0) + (nodeOf(d.target)?.x ?? 0)) / 2)
        .attr("y", d => ((nodeOf(d.source)?.y ?? 0) + (nodeOf(d.target)?.y ?? 0)) / 2);
      nodeEls.attr("cx", d => d.x ?? 0).attr("cy", d => d.y ?? 0);
      nodeLabels.attr("x", d => d.x ?? 0).attr("y", d => d.y ?? 0);
    });
  }, []);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");

    const url = selectedFile
      ? `${API_BASE}/graph?filename=${encodeURIComponent(selectedFile)}`
      : `${API_BASE}/graph`;

    fetch(url)
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then((data: GraphData) => {
        if (cancelled) return;
        setCounts({ nodes: data.nodes.length, links: data.links.length });
        if (data.nodes.length === 0) { setStatus("empty"); return; }
        renderGraph(data);
        setStatus("ready");
      })
      .catch(() => { if (!cancelled) setStatus("error"); });

    return () => { cancelled = true; };
  }, [selectedFile, renderGraph]);

  const shortName = (f: string) => f.length > 22 ? f.slice(0, 20) + "…" : f;

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-200 bg-white shrink-0 flex-wrap">
        {/* Document tabs */}
        <div className="flex items-center gap-1 flex-wrap flex-1">
          <button
            onClick={() => setSelectedFile(null)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              selectedFile === null
                ? "bg-gray-800 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            All
          </button>
          {files.map(f => (
            <button
              key={f.filename}
              onClick={() => setSelectedFile(f.filename)}
              title={`${f.filename} (${f.chunks} chunks)`}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors max-w-[160px] truncate ${
                selectedFile === f.filename
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {shortName(f.filename)}
            </button>
          ))}
        </div>

        {/* Counts + legend */}
        {status === "ready" && (
          <div className="flex items-center gap-3 text-xs text-gray-500 shrink-0">
            <span><strong className="text-gray-700">{counts.nodes}</strong> nodes</span>
            <span><strong className="text-gray-700">{counts.links}</strong> edges</span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-3 rounded-full bg-blue-800 border border-blue-300" />
              Chunk
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-3 rounded-full bg-amber-400" />
              Entity
            </span>
          </div>
        )}
      </div>

      {/* Canvas */}
      <div className="flex-1 relative overflow-hidden bg-gray-50">
        {status === "loading" && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="flex flex-col items-center gap-3 text-gray-400">
              <svg className="animate-spin w-8 h-8" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
              </svg>
              <span className="text-sm">Loading graph…</span>
            </div>
          </div>
        )}
        {status === "empty" && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center text-gray-400">
              <p className="text-lg font-medium mb-1">No graph data yet</p>
              <p className="text-sm">Upload a document to build the knowledge graph.</p>
            </div>
          </div>
        )}
        {status === "error" && (
          <div className="absolute inset-0 flex items-center justify-center">
            <p className="text-sm text-red-500">Failed to load graph. Is the backend running?</p>
          </div>
        )}
        <svg ref={svgRef} className="w-full h-full" />
      </div>
    </div>
  );
}
