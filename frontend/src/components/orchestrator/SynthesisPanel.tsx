"use client";

import { useState } from "react";
import { FileText, ChevronDown, ChevronRight } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";

interface SynthesisPanelProps {
  synthesis: string;
  subtaskCount: number;
  onExport?: () => void;
}

export function SynthesisPanel({ synthesis, subtaskCount, onExport }: SynthesisPanelProps) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="border rounded-lg bg-white overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 bg-blue-50 border-b border-blue-200 hover:bg-blue-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-blue-600" />
          <h3 className="font-semibold text-gray-900">Synthesized Result</h3>
          <span className="text-xs text-gray-500">
            ({subtaskCount} agent{subtaskCount !== 1 ? "s" : ""})
          </span>
        </div>
        <div className="flex items-center gap-2">
          {expanded ? (
            <ChevronDown className="w-4 h-4 text-gray-500" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-500" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="p-4">
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
              {synthesis}
            </ReactMarkdown>
          </div>

          {onExport && (
            <div className="mt-4 flex justify-end">
              <button
                onClick={onExport}
                className="text-sm text-blue-600 hover:text-blue-800 font-medium"
              >
                Export Full Report
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
