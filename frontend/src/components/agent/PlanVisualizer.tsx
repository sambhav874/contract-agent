"use client";

import { Check, Clock, Loader2, X } from "lucide-react";

export interface PlanStep {
  step_id: string;
  description: string;
  status: "pending" | "running" | "done" | "failed";
  tools_needed?: string[];
  depends_on?: string[];
  success_criteria?: string;
}

interface PlanVisualizerProps {
  plan: PlanStep[];
  currentStep?: string;
}

const STATUS_ICON = {
  pending: <Clock className="w-4 h-4 text-gray-400" />,
  running: <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />,
  done: <Check className="w-4 h-4 text-green-500" />,
  failed: <X className="w-4 h-4 text-red-500" />,
};

const STATUS_CLASS = {
  pending: "bg-gray-50 border-gray-200",
  running: "bg-blue-50 border-blue-200",
  done: "bg-green-50 border-green-200",
  failed: "bg-red-50 border-red-200",
};

export function PlanVisualizer({ plan, currentStep }: PlanVisualizerProps) {
  if (!plan?.length) return null;

  const doneCount = plan.filter((s) => s.status === "done").length;
  const progress = Math.round((doneCount / plan.length) * 100);

  return (
    <div className="border rounded-lg p-4 bg-white">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-gray-900">Execution Plan</h3>
        <span className="text-sm text-gray-500">{doneCount}/{plan.length} done</span>
      </div>

      <div className="w-full bg-gray-200 rounded-full h-2 mb-4">
        <div
          className="bg-blue-600 h-2 rounded-full transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="space-y-2">
        {plan.map((step) => (
          <div
            key={step.step_id}
            className={`flex items-start gap-3 p-2 rounded border ${STATUS_CLASS[step.status]} ${
              currentStep === step.step_id ? "ring-2 ring-blue-200" : ""
            }`}
          >
            <div className="mt-0.5 flex-shrink-0">{STATUS_ICON[step.status]}</div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-gray-900 truncate">
                {step.description}
              </div>
              {step.tools_needed && step.tools_needed.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {step.tools_needed.map((tool) => (
                    <span
                      key={tool}
                      className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded"
                    >
                      {tool}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
