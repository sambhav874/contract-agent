"use client";

import { useState } from "react";
import { Brain, ChevronDown, ChevronRight } from "lucide-react";

export interface Thought {
  id: string;
  timestamp: number;
  content: string;
}

interface ThinkingPanelProps {
  thoughts: Thought[];
  maxVisible?: number;
}

export function ThinkingPanel({ thoughts, maxVisible = 3 }: ThinkingPanelProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [showAll, setShowAll] = useState(false);

  if (!thoughts?.length) return null;

  const visibleThoughts = showAll ? thoughts : thoughts.slice(-maxVisible);
  const hasMore = thoughts.length > maxVisible;

  return (
    <div className="border rounded-lg overflow-hidden bg-amber-50 border-amber-200">
      <div className="flex items-center gap-2 p-3 bg-amber-100 border-b border-amber-200">
        <Brain className="w-4 h-4 text-amber-600" />
        <h3 className="text-sm font-semibold text-amber-900">Agent Thinking</h3>
        {hasMore && (
          <button
            onClick={() => setShowAll(!showAll)}
            className="ml-auto text-xs text-amber-700 hover:text-amber-900"
          >
            {showAll ? "Show latest" : `Show all (${thoughts.length})`}
          </button>
        )}
      </div>

      <div className="divide-y divide-amber-200">
        {visibleThoughts.map((thought) => {
          const isExpanded = expanded[thought.id];
          const isLong = thought.content.length > 200;
          const displayContent =
            isExpanded || !isLong
              ? thought.content
              : thought.content.slice(0, 200) + "...";

          return (
            <div key={thought.id} className="p-3">
              <div className="flex items-start gap-2">
                <span className="text-xs text-amber-500 mt-0.5 flex-shrink-0">
                  {new Date(thought.timestamp).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })}
                </span>
                <div className="flex-1">
                  <p className="text-sm text-amber-900 leading-relaxed">{displayContent}</p>
                  {isLong && (
                    <button
                      onClick={() =>
                        setExpanded((prev) => ({ ...prev, [thought.id]: !prev[thought.id] }))
                      }
                      className="text-xs text-amber-600 hover:text-amber-800 mt-1 flex items-center gap-0.5"
                    >
                      {isExpanded ? (
                        <ChevronDown className="w-3 h-3" />
                      ) : (
                        <ChevronRight className="w-3 h-3" />
                      )}
                      {isExpanded ? "Show less" : "Show more"}
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
