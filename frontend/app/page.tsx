"use client";
import { useEffect, useState } from "react";
import UploadPanel from "./components/UploadPanel";
import ChatWindow from "./components/ChatWindow";
import GraphView from "./components/GraphView";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

type Tab = "chat" | "graph";

export default function Home() {
  const [connected, setConnected] = useState<boolean | null>(null);
  const [tab, setTab] = useState<Tab>("chat");

  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch(`${API_BASE}/health`);
        setConnected(res.ok);
      } catch {
        setConnected(false);
      }
    };
    check();
  }, []);

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 bg-white border-b border-gray-200 shrink-0">
        <span className="text-xl font-bold text-gray-900 tracking-tight">GraphRAG</span>

        {/* Tabs */}
        <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
          <button
            onClick={() => setTab("chat")}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              tab === "chat"
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            Chat
          </button>
          <button
            onClick={() => setTab("graph")}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              tab === "graph"
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            Graph
          </button>
        </div>

        {/* Connection status */}
        <div className="flex items-center gap-2 text-sm">
          {connected === null ? (
            <span className="text-gray-400">Checking…</span>
          ) : connected ? (
            <>
              <span className="w-2.5 h-2.5 rounded-full bg-green-500 inline-block" />
              <span className="text-green-700 font-medium">Connected</span>
            </>
          ) : (
            <>
              <span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block" />
              <span className="text-red-600 font-medium">Disconnected</span>
            </>
          )}
        </div>
      </header>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar — always visible */}
        <aside className="w-[30%] border-r border-gray-200 bg-white p-5 overflow-y-auto shrink-0">
          <UploadPanel />
        </aside>

        {/* Main panel — switches between Chat and Graph */}
        <main className="flex-1 overflow-hidden">
          {tab === "chat" ? <ChatWindow /> : <GraphView />}
        </main>
      </div>
    </div>
  );
}
