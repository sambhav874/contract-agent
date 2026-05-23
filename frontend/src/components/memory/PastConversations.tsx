"use client";

import { useState } from "react";
import { Clock, Search, ChevronRight } from "lucide-react";

interface Conversation {
  id: string;
  goal: string;
  result: string;
  outcome: string;
  timestamp: string;
  trace: any[];
}

interface PastConversationsProps {
  conversations: Conversation[];
  onSelect?: (id: string) => void;
}

export function PastConversations({ conversations, onSelect }: PastConversationsProps) {
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const filtered = conversations.filter(
    (c) =>
      c.goal.toLowerCase().includes(search.toLowerCase()) ||
      c.result.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="border rounded-lg bg-white overflow-hidden">
      <div className="p-4 bg-gray-50 border-b border-gray-200">
        <h3 className="font-semibold text-gray-900">Past Sessions</h3>
        <div className="relative mt-2">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search past sessions..."
            className="w-full pl-9 pr-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
          />
        </div>
      </div>

      <div className="divide-y divide-gray-100 max-h-96 overflow-y-auto">
        {filtered.length === 0 && (
          <div className="p-4 text-center text-sm text-gray-400">No sessions found</div>
        )}
        {filtered.map((c) => (
          <div key={c.id} className="p-3 hover:bg-gray-50 transition-colors">
            <button onClick={() => onSelect?.(c.id)} className="w-full text-left">
              <div className="flex items-start gap-2">
                <Clock className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{c.goal}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{new Date(c.timestamp).toLocaleString()}</p>
                  <span
                    className={`inline-block mt-1 text-xs px-2 py-0.5 rounded-full ${
                      c.outcome === "success"
                        ? "bg-green-100 text-green-700"
                        : "bg-red-100 text-red-700"
                    }`}
                  >
                    {c.outcome}
                  </span>
                </div>
                <ChevronRight className="w-4 h-4 text-gray-300" />
              </div>
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
