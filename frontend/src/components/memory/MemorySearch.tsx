"use client";

import { useState } from "react";
import { Search, Clock, ArrowRight } from "lucide-react";

interface MemoryItem {
  id: string;
  type: "episodic" | "semantic";
  title: string;
  snippet: string;
  timestamp: string;
  relevance?: number;
}

interface MemorySearchProps {
  onSearch?: (query: string) => void;
  items?: MemoryItem[];
}

export function MemorySearch({ onSearch, items = [] }: MemorySearchProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<MemoryItem[]>(items);

  const handleSearch = () => {
    if (!query.trim()) return;
    if (onSearch) {
      onSearch(query);
    } else {
      const filtered = items.filter(
        (item) =>
          item.title.toLowerCase().includes(query.toLowerCase()) ||
          item.snippet.toLowerCase().includes(query.toLowerCase())
      );
      setResults(filtered);
    }
  };

  return (
    <div className="border rounded-lg bg-white overflow-hidden">
      <div className="p-4 bg-gray-50 border-b border-gray-200">
        <h3 className="font-semibold text-gray-900 mb-2">Search Memory</h3>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="Search past conversations, facts..."
              className="w-full pl-9 pr-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />
          </div>
          <button
            onClick={handleSearch}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
          >
            Search
          </button>
        </div>
      </div>

      <div className="max-h-96 overflow-y-auto">
        {results.length === 0 && query && (
          <div className="p-4 text-center text-sm text-gray-400">No results found</div>
        )}
        <div className="divide-y divide-gray-100">
          {results.map((item) => (
            <div
              key={item.id}
              className="p-3 hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-start gap-3">
                <div
                  className={`mt-0.5 text-xs px-1.5 py-0.5 rounded-full ${
                    item.type === "episodic"
                      ? "bg-purple-100 text-purple-700"
                      : "bg-green-100 text-green-700"
                  }`}
                >
                  {item.type}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900">{item.title}</p>
                  <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{item.snippet}</p>
                  <div className="flex items-center gap-3 mt-1 text-xs text-gray-400">
                    <span className="flex items-center gap-0.5">
                      <Clock className="w-3 h-3" />
                      {new Date(item.timestamp).toLocaleDateString()}
                    </span>
                    {item.relevance && (
                      <span className="text-blue-600">
                        {(item.relevance * 100).toFixed(0)}% match
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
