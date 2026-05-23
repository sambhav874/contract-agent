"use client";

import React, { useEffect } from "react";
import { Activity, BarChart3, Download, X, Sparkles } from "lucide-react";

interface Artifact {
  type: "svg" | "html";
  content: string;
}

interface ArtifactOverlayProps {
  activeArtifact: Artifact | null;
  onClose: () => void;
}

export default function ArtifactOverlay({ activeArtifact, onClose }: ArtifactOverlayProps) {
  useEffect(() => {
    if (!activeArtifact) return;

    const handler = (event: MessageEvent) => {
      if (event.data?.type === "artifact-resize" && event.data.height) {
        const iframe = document.getElementById("artifact-iframe") as HTMLIFrameElement | null;
        if (iframe) {
          iframe.style.height = Math.min(event.data.height + 40, 1200) + "px";
        }
      }
    };

    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, [activeArtifact]);

  if (!activeArtifact) return null;

  const handleDownload = () => {
    const blob = new Blob([activeArtifact.content], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `artifact.${activeArtifact.type === "svg" ? "svg" : "html"}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 md:p-8 animate-in">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-md" onClick={onClose} />
      <div className="relative w-full max-w-6xl bg-white rounded-2xl shadow-[0_32px_64px_-16px_rgba(0,0,0,0.2)] border border-gray-200/80 overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="px-5 py-3.5 border-b border-gray-100 flex items-center justify-between bg-gradient-to-r from-indigo-50/60 via-white to-white">
          <div className="flex items-center gap-3">
            <div
              className={`h-9 w-9 rounded-xl flex items-center justify-center text-white shadow-md ${
                activeArtifact.type === "svg"
                  ? "bg-gradient-to-br from-violet-500 to-indigo-600 shadow-indigo-200"
                  : "bg-gradient-to-br from-blue-500 to-indigo-600 shadow-blue-200"
              }`}
            >
              {activeArtifact.type === "svg" ? <Activity className="h-5 w-5" /> : <BarChart3 className="h-5 w-5" />}
            </div>
            <div>
              <h2 className="text-sm font-bold text-gray-800">
                {activeArtifact.type === "svg" ? "Compliance Diagram" : "Data Visualization"}
              </h2>
              <p className="text-[10px] text-indigo-500 font-semibold uppercase tracking-widest">
                Generated from real contract data
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              onClick={handleDownload}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors text-gray-400 hover:text-gray-600"
              title="Download"
            >
              <Download className="h-4 w-4" />
            </button>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors text-gray-400 hover:text-gray-600"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Content — Premium Iframe Sandbox */}
        <div className="flex-1 overflow-auto bg-[#fafbfc] relative">
          <div
            className="absolute inset-0 opacity-[0.03] pointer-events-none"
            style={{
              backgroundImage: "radial-gradient(#64748b 0.5px, transparent 0.5px)",
              backgroundSize: "20px 20px",
            }}
          />
          <div className="relative h-full">
            <iframe
              id="artifact-iframe"
              srcDoc={
                '<!DOCTYPE html><html><head><meta charset="utf-8">' +
                '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">' +
                "<style>" +
                ":root {" +
                "  --bg-primary: #ffffff;" +
                "  --bg-secondary: #f8fafc;" +
                "  --bg-tertiary: #f1f5f9;" +
                "  --bg-card: rgba(255,255,255,0.85);" +
                "  --text-primary: #0f172a;" +
                "  --text-secondary: #475569;" +
                "  --text-tertiary: #94a3b8;" +
                "  --border-light: #f1f5f9;" +
                "  --border-default: #e2e8f0;" +
                "  --indigo-50: #eef2ff; --indigo-100: #e0e7ff; --indigo-400: #818cf8; --indigo-500: #6366f1; --indigo-600: #4f46e5;" +
                "  --emerald-50: #ecfdf5; --emerald-400: #34d399; --emerald-500: #10b981; --emerald-600: #059669;" +
                "  --amber-50: #fffbeb; --amber-400: #fbbf24; --amber-500: #f59e0b; --amber-600: #d97706;" +
                "  --rose-50: #fff1f2; --rose-400: #fb7185; --rose-500: #f43f5e; --rose-600: #e11d48;" +
                "  --sky-50: #f0f9ff; --sky-400: #38bdf8; --sky-500: #0ea5e9;" +
                "  --radius-sm: 6px; --radius-md: 10px; --radius-lg: 14px; --radius-xl: 20px;" +
                "  --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);" +
                "  --shadow-md: 0 4px 12px rgba(0,0,0,0.06);" +
                "  --font-sans: Inter, system-ui, -apple-system, sans-serif;" +
                "  --font-mono: SF Mono, Fira Code, ui-monospace, monospace;" +
                "  --color-background-primary: #ffffff;" +
                "  --color-background-secondary: #f8fafc;" +
                "  --color-background-tertiary: #f1f5f9;" +
                "  --color-text-primary: #0f172a;" +
                "  --color-text-secondary: #475569;" +
                "  --color-text-tertiary: #94a3b8;" +
                "  --color-border-primary: #e2e8f0;" +
                "  --color-border-secondary: #cbd5e1;" +
                "  --color-border-tertiary: #f1f5f9;" +
                "  --border-radius-md: 10px;" +
                "  --border-radius-lg: 14px;" +
                "}" +
                "@keyframes fadeInUp { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }" +
                "@keyframes countUp { from { opacity:0; transform:scale(0.8); } to { opacity:1; transform:scale(1); } }" +
                ".animate-in { animation: fadeInUp 0.4s ease-out both; }" +
                ".stat-value { animation: countUp 0.5s cubic-bezier(0.16,1,0.3,1) both; }" +
                ".card { background:var(--bg-card); backdrop-filter:blur(12px); border:0.5px solid var(--border-default); border-radius:var(--radius-lg); box-shadow:var(--shadow-sm); padding:20px; transition:box-shadow 0.2s,transform 0.2s; }" +
                ".card:hover { box-shadow:var(--shadow-md); transform:translateY(-1px); }" +
                "body { margin:0; padding:2rem; font-family:var(--font-sans); display:flex; justify-content:center; align-items:flex-start; min-height:100vh; background:transparent; color:var(--text-primary); }" +
                "* { box-sizing:border-box; }" +
                "svg { max-width:100%; height:auto; }" +
                "</style></head><body>" +
                activeArtifact.content +
                "<script>" +
                'window.addEventListener("load", () => {' +
                "  if (window.init) window.init();" +
                '  if (typeof initFn === "function") initFn();' +
                "  // Auto-resize iframe to content height" +
                "  setTimeout(() => {" +
                "    const h = document.body.scrollHeight;" +
                '    window.parent.postMessage({ type:"artifact-resize", height: h }, "*");' +
                "  }, 500);" +
                "});" +
                "</script></body></html>"
              }
              className="w-full border-none bg-transparent"
              style={{ minHeight: "650px" }}
              title="Generative UI Artifact"
              sandbox="allow-scripts allow-same-origin"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-gray-100 bg-white/80 backdrop-blur-sm flex items-center justify-between">
          <div className="flex items-center gap-2 text-[10px] text-gray-400">
            <Sparkles className="h-3 w-3" />
            <span className="font-medium">Data sourced from MongoDB · Contract KPI Registry</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-gray-50 hover:bg-gray-100 text-gray-600 rounded-lg text-xs font-semibold transition-all active:scale-95 border border-gray-200"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
