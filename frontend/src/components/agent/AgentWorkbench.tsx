"use client";

import { useState, useEffect } from "react";
import { Brain, ChevronRight, ChevronDown, X, Terminal } from "lucide-react";
import { PlanVisualizer, type PlanStep } from "./PlanVisualizer";
import { ThinkingPanel, type Thought } from "./ThinkingPanel";
import { ToolCallLog, type ToolCall } from "./ToolCallLog";

interface AgentWorkbenchProps {
  plan: PlanStep[];
  thoughts: Thought[];
  toolCalls: ToolCall[];
  onClose: () => void;
}

export function AgentWorkbench({ plan, thoughts, toolCalls, onClose }: AgentWorkbenchProps) {
  const [activeTab, setActiveTab] = useState<"plan" | "thoughts" | "tools">("plan");

  const hasContent = plan.length > 0 || thoughts.length > 0 || toolCalls.length > 0;

  if (!hasContent) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-400">
        <Brain className="w-12 h-12 mb-3 opacity-50" />
        <p className="text-sm">No agent activity yet</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-white border-l shadow-lg">
      <div className="flex items-center justify-between p-4 border-b">
        <div className="flex items-center gap-2">
          <Brain className="w-5 h-5 text-purple-600" />
          <h3 className="font-semibold text-gray-900">Agent Workbench</h3>
          <span className="text-xs text-gray-500">
            {plan.filter((s) => s.status === "done").length}/{plan.length} steps
          </span>
        </div>
        <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="flex border-b">
        {[
          { id: "plan" as const, label: "Plan", count: plan.filter(s => s.status !== "pending").length },
          { id: "thoughts" as const, label: "Thinking", count: thoughts.length },
          { id: "tools" as const, label: "Tools", count: toolCalls.length },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 py-3 text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? "text-purple-700 border-b-2 border-purple-600 bg-purple-50"
                : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"
            }`}
          >
            {tab.label} {tab.count > 0 && <span className="ml-1 text-xs text-gray-400">({tab.count})</span>}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === "plan" && <PlanVisualizer plan={plan} />}
        {activeTab === "thoughts" && <ThinkingPanel thoughts={thoughts} />}
        {activeTab === "tools" && <ToolCallLog toolCalls={toolCalls} />}
      </div>
    </div>
  );
}
