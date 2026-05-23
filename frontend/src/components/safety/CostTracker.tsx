"use client";

import { useEffect } from "react";
import { DollarSign, TrendingUp, AlertTriangle } from "lucide-react";

interface CostTrackerProps {
  currentCost: number;
  maxCost: number;
  currency?: string;
  modelBreakdown?: Record<string, number>;
}

function formatCost(cost: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 4,
    maximumFractionDigits: 6,
  }).format(cost);
}

export function CostTracker({
  currentCost,
  maxCost,
  modelBreakdown = {},
}: CostTrackerProps) {
  const percentage = Math.min((currentCost / maxCost) * 100, 100);
  const warning = percentage > 75;
  const danger = percentage >= 95;

  return (
    <div className={`border rounded-lg p-4 ${danger ? "bg-red-50 border-red-200" : warning ? "bg-amber-50 border-amber-200" : "bg-white border-gray-200"}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <DollarSign className={`w-5 h-5 ${danger ? "text-red-600" : warning ? "text-amber-600" : "text-green-600"}`} />
          <h3 className="font-semibold text-gray-900">Cost Tracking</h3>
        </div>
        {danger && <AlertTriangle className="w-5 h-5 text-red-600" />}
        {warning && !danger && <TrendingUp className="w-5 h-5 text-amber-600" />}
      </div>

      <div className="mb-4">
        <div className="flex justify-between text-sm mb-1">
          <span className="text-gray-600">{formatCost(currentCost)} / {formatCost(maxCost)}</span>
          <span className={danger ? "text-red-600 font-semibold" : warning ? "text-amber-600" : "text-gray-500"}>
            {percentage.toFixed(1)}%
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className={`h-2 rounded-full transition-all duration-500 ${
              danger ? "bg-red-500" : warning ? "bg-amber-500" : "bg-green-500"
            }`}
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>

      {Object.keys(modelBreakdown).length > 0 && (
        <div className="space-y-2">
          <span className="text-xs font-medium text-gray-500 uppercase">By Model</span>
          <div className="space-y-1">
            {Object.entries(modelBreakdown).map(([model, cost]) => (
              <div key={model} className="flex items-center justify-between text-sm">
                <span className="text-gray-700 flex-1 truncate">{model}</span>
                <span className="text-gray-500 tabular-nums">{formatCost(cost)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
