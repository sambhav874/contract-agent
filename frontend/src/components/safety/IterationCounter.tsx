"use client";

import { Clock, AlertTriangle } from "lucide-react";

interface IterationCounterProps {
  current: number;
  max: number;
  label?: string;
}

export function IterationCounter({
  current,
  max,
  label = "Agent Iterations",
}: IterationCounterProps) {
  const percentage = Math.min((current / max) * 100, 100);
  const warning = percentage > 75;
  const danger = percentage >= 95;

  return (
    <div className={`border rounded-lg p-4 ${danger ? "bg-red-50 border-red-200" : warning ? "bg-amber-50 border-amber-200" : "bg-white border-gray-200"}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Clock className={`w-5 h-5 ${danger ? "text-red-600" : warning ? "text-amber-600" : "text-blue-600"}`} />
          <h3 className="font-semibold text-gray-900">{label}</h3>
        </div>
        {danger && <AlertTriangle className="w-5 h-5 text-red-600" />}
      </div>

      <div className="mb-4">
        <div className="flex justify-between text-sm mb-1">
          <span className="text-gray-600">{current} / {max} turns</span>
          <span className={danger ? "text-red-600 font-semibold" : warning ? "text-amber-600" : "text-gray-500"}>
            {percentage.toFixed(0)}%
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className={`h-2 rounded-full transition-all duration-500 ${
              danger ? "bg-red-500" : warning ? "bg-amber-500" : "bg-blue-500"
            }`}
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>

      <div className="text-sm text-gray-600">
        {danger ? (
          <p className="text-red-700 font-medium">Safety guard may trigger soon. Consider concluding the conversation.</p>
        ) : warning ? (
          <p className="text-amber-700">Approaching iteration limit.</p>
        ) : (
          <p className="text-gray-500">Iterations within safe limits.</p>
        )}
      </div>
    </div>
  );
}
