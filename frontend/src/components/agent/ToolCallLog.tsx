"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Terminal, Check, X } from "lucide-react";

export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, any>;
  status: "running" | "done" | "failed";
  result?: string;
  duration?: number;
  error?: string;
}

interface ToolCallLogProps {
  toolCalls: ToolCall[];
  maxVisible?: number;
}

const STATUS_ICON = {
  running: <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />,
  done: <Check className="w-4 h-4 text-green-500" />,
  failed: <X className="w-4 h-4 text-red-500" />,
};

export function ToolCallLog({ toolCalls, maxVisible = 5 }: ToolCallLogProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [showAll, setShowAll] = useState(false);

  if (!toolCalls?.length) return null;

  const visibleCalls = showAll ? toolCalls : toolCalls.slice(0, maxVisible);
  const hasMore = toolCalls.length > maxVisible;

  const toggleExpanded = (id: string) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="border rounded-lg overflow-hidden bg-gray-50 border-gray-200">
      <div className="flex items-center gap-2 p-3 bg-gray-100 border-b border-gray-200">
        <Terminal className="w-4 h-4 text-gray-600" />
        <h3 className="text-sm font-semibold text-gray-900">Tool Calls</h3>
        <span className="text-xs text-gray-500">({toolCalls.length})</span>
        {hasMore && (
          <button
            onClick={() => setShowAll(!showAll)}
            className="ml-auto text-xs text-gray-500 hover:text-gray-700"
          >
            {showAll ? "Show first 5" : "Show all"}
          </button>
        )}
      </div>

      <div className="divide-y divide-gray-200">
        {visibleCalls.map((call) => {
          const isExpanded = expanded[call.id];

          return (
            <div key={call.id} className="p-3">
              <button
                onClick={() => toggleExpanded(call.id)}
                className="w-full flex items-start gap-3 text-left"
              >
                <div className="mt-0.5 flex-shrink-0">{STATUS_ICON[call.status]}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-900">{call.name}</span>
                    {call.duration && (
                      <span className="text-xs text-gray-500">{call.duration}ms</span>
                    )}
                  </div>
                </div>
                {isExpanded ? (
                  <ChevronDown className="w-4 h-4 text-gray-400 flex-shrink-0" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-gray-400 flex-shrink-0" />
                )}
              </button>

              {isExpanded && (
                <div className="mt-2 space-y-2">
                  <div>
                    <span className="text-xs font-medium text-gray-500 uppercase" >
                      Arguments
                    </span>
                    <pre className="mt-1 p-2 bg-gray-800 text-green-400 rounded text-xs overflow-x-auto">
                      {JSON.stringify(call.args, null, 2)}
                    </pre>
                  </div>

                  {call.result && (
                    <div>
                      <span className="text-xs font-medium text-gray-500 uppercase">
                        Result
                      </span>
                      <pre className="mt-1 p-2 bg-gray-800 text-blue-400 rounded text-xs overflow-x-auto max-h-40 overflow-y-auto">
                        {call.result.length > 500
                          ? call.result.slice(0, 500) + "..."
                          : call.result}
                      </pre>
                    </div>
                  )}

                  {call.error && (
                    <div>
                      <span className="text-xs font-medium text-red-500 uppercase" >
                        Error
                      </span>
                      <p className="mt-1 p-2 bg-red-50 text-red-700 rounded text-xs">{call.error}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
