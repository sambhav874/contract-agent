"use client";

import { Check, Clock, Loader2, X, Layers } from "lucide-react";

interface Subtask {
  step_id: string;
  description: string;
  status: "pending" | "running" | "completed" | "failed";
  result?: string;
  error?: string;
}

interface SubtaskGridProps {
  subtasks: Subtask[];
  goal: string;
}

const STATUS_ICON = {
  pending: <Clock className="w-4 h-4 text-gray-400" />,
  running: <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />,
  completed: <Check className="w-4 h-4 text-green-500" />,
  failed: <X className="w-4 h-4 text-red-500" />,
};

const STATUS_LABEL = {
  pending: "Pending",
  running: "Running",
  completed: "Done",
  failed: "Failed",
};

const STATUS_BADGE = {
  pending: "bg-gray-100 text-gray-600",
  running: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

export function SubtaskGrid({ subtasks, goal }: SubtaskGridProps) {
  if (!subtasks?.length) return null;

  const completed = subtasks.filter((s) => s.status === "completed").length;
  const failed = subtasks.filter((s) => s.status === "failed").length;
  const running = subtasks.filter((s) => s.status === "running").length;

  return (
    <div className="border rounded-lg bg-white overflow-hidden">
      <div className="p-4 bg-gray-50 border-b border-gray-200">
        <div className="flex items-center gap-2 mb-1">
          <Layers className="w-5 h-5 text-blue-600" />
          <h3 className="font-semibold text-gray-900">Multi-Agent Analysis</h3>
        </div>
        <p className="text-sm text-gray-600 mt-1">{goal}</p>
        <div className="flex gap-3 mt-3 text-xs">
          <span className="text-green-700">{completed} done</span>
          <span className="text-blue-700">{running} running</span>
          {failed > 0 && <span className="text-red-700">{failed} failed</span>}
        </div>
      </div>

      <div className="divide-y divide-gray-100">
        {subtasks.map((task) => (
          <div key={task.step_id} className="p-4 hover:bg-gray-50 transition-colors">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 flex-shrink-0">{STATUS_ICON[task.status]}</div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-gray-900">{task.description}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_BADGE[task.status]}`}>
                    {STATUS_LABEL[task.status]}
                  </span>
                </div>

                {task.result && (
                  <div className="mt-2 p-2 bg-gray-50 rounded text-sm text-gray-700">
                    {task.result}
                  </div>
                )}

                {task.error && (
                  <div className="mt-2 p-2 bg-red-50 rounded text-sm text-red-700">
                    {task.error}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
