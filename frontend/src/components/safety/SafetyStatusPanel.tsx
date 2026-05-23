"use client";

import { Shield, Check, X, AlertTriangle } from "lucide-react";
import { CostTracker } from "./CostTracker";
import { IterationCounter } from "./IterationCounter";

interface SafetyStatus {
  cost_tracker: number;
  max_cost_usd: number;
  max_iterations: number;
  iterations_used: number | null;
}

interface SafetyStatusPanelProps {
  status: SafetyStatus;
  onRefresh?: () => void;
}

export function SafetyStatusPanel({ status, onRefresh }: SafetyStatusPanelProps) {
  const costPercentage = (status.cost_tracker / status.max_cost_usd) * 100;
  const costOk = costPercentage < 95;
  const iterOk = !status.iterations_used || status.iterations_used < status.max_iterations * 0.95;

  return (
    <div className="border rounded-lg bg-white overflow-hidden">
      <div className="flex items-center gap-2 p-4 bg-gray-50 border-b border-gray-200">
        <Shield className="w-5 h-5 text-blue-600" />
        <h3 className="font-semibold text-gray-900">Safety Status</h3>
        {costOk && iterOk ? (
          <span className="ml-auto px-2 py-0.5 text-xs bg-green-100 text-green-700 rounded-full">
            <Check className="w-3 h-3 inline mr-0.5" /> OK
          </span>
        ) : (
          <span className="ml-auto px-2 py-0.5 text-xs bg-red-100 text-red-700 rounded-full">
            <AlertTriangle className="w-3 h-3 inline mr-0.5" /> Warning
          </span>
        )}
      </div>

      <div className="p-4 space-y-4">
        <CostTracker
          currentCost={status.cost_tracker}
          maxCost={status.max_cost_usd}
        />

        <IterationCounter
          current={status.iterations_used ?? 0}
          max={status.max_iterations}
        />

        <div className="grid grid-cols-2 gap-2 mt-2">
          <StatusIndicator
            label="Cost"
            ok={costOk}
            detail={`${((status.cost_tracker / status.max_cost_usd) * 100).toFixed(1)}%`}
          />
          <StatusIndicator
            label="Iterations"
            ok={iterOk}
            detail={status.iterations_used ? `${status.iterations_used}` : "N/A"}
          />
        </div>
      </div>
    </div>
  );
}

function StatusIndicator({ label, ok, detail }: { label: string; ok: boolean; detail: string }) {
  return (
    <div className={`flex items-center justify-between px-3 py-2 rounded-lg ${ok ? "bg-green-50" : "bg-red-50"}`}>
      <div className="flex items-center gap-2">
        {ok ? (
          <Check className="w-4 h-4 text-green-500" />
        ) : (
          <X className="w-4 h-4 text-red-500" />
        )}
        <span className="text-sm font-medium text-gray-700">{label}</span>
      </div>
      <span className={`text-sm font-semibold tabular-nums ${ok ? "text-green-700" : "text-red-700"}`}>
        {detail}
      </span>
    </div>
  );
}
