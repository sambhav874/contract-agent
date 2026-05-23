"use client";

import { ChevronDown, ChevronRight, Terminal } from "lucide-react";
import { useState } from "react";

interface ToolCall {
  name: string;
  args: Record<string, any>;
  status: "running" | "done";
}

interface ToolCallLogProps {
  toolCalls: ToolCall[];
}

export function ToolCallLog({ toolCalls }: ToolCallLogProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  if (!toolCalls?.length) return null;

  return (
    <div className="mt-2 space-y-1">
      {toolCalls.map((tc, idx) => {
        const key = `${tc.name}-${idx}`;
        return (
          <div key={key} className="text-xs bg-gray-100 rounded p-2">
            <button
              onClick={() => setExpanded((prev) => ({ ...prev, [key]: !prev[key] }))}
              className="flex items-center gap-1 text-gray-600 hover:text-gray-900"
            >
              {expanded[key] ? (
                <ChevronDown className="w-3 h-3" />
              ) : (
                <ChevronRight className="w-3 h-3" />
              )}
              <Terminal className="w-3 h-3" />
              <span className="font-medium">{tc.name}</span>
              <span
                className={`px-1.5 py-0.5 rounded-full text-[10px] ${
                  tc.status === "done"
                    ? "bg-green-100 text-green-700"
                    : "bg-amber-100 text-amber-700"
                }`}
              >
                {tc.status}
              </span>
            </button>
            {expanded[key] && (
              <pre className="mt-1 p-2 bg-gray-800 text-green-400 rounded text-[10px] overflow-x-auto">
                {JSON.stringify(tc.args, null, 2)}
              </pre>
            )}
          </div>
        );
      })}
    </div>
  );
}
