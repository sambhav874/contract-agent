"use client";

import { Database, Trash2, Clock } from "lucide-react";

interface Fact {
  key: string;
  value: string;
  source: string;
  confidence: number;
  last_used: string;
}

interface LearnedFactsProps {
  facts: Fact[];
  onRemove?: (key: string) => void;
}

function confidenceColor(score: number): string {
  if (score >= 0.95) return "bg-green-100 text-green-700";
  if (score >= 0.8) return "bg-blue-100 text-blue-700";
  if (score >= 0.6) return "bg-amber-100 text-amber-700";
  return "bg-red-100 text-red-700";
}

export function LearnedFacts({ facts, onRemove }: LearnedFactsProps) {
  return (
    <div className="border rounded-lg bg-white overflow-hidden">
      <div className="p-4 bg-gray-50 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <Database className="w-5 h-5 text-purple-600" />
          <h3 className="font-semibold text-gray-900">Learned Facts</h3>
          <span className="text-sm text-gray-500">({facts.length})</span>
        </div>
      </div>

      <div className="divide-y divide-gray-100 max-h-96 overflow-y-auto">
        {facts.length === 0 && (
          <div className="p-4 text-center text-sm text-gray-400">No facts stored</div>
        )}
        <div className="grid grid-cols-1 gap-0">
          {facts.map((fact) => (
            <div
              key={fact.key}
              className="p-3 hover:bg-gray-50 transition-colors flex items-start gap-3"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-medium text-gray-900">{fact.key}</span>
                  <span
                    className={`text-xs px-1.5 py-0.5 rounded-full ${confidenceColor(
                      fact.confidence
                    )}`}
                  >
                    {(fact.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                <p className="text-sm text-gray-600">{fact.value}</p>
                <div className="flex items-center gap-2 mt-1 text-xs text-gray-400">
                  <span className="text-gray-500">{fact.source}</span>
                  <span className="flex items-center gap-0.5">
                    <Clock className="w-3 h-3" />
                    {new Date(fact.last_used).toLocaleDateString()}
                  </span>
                </div>
              </div>

              {onRemove && (
                <button
                  onClick={() => onRemove(fact.key)}
                  className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                  title="Remove fact"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
