"use client";

import React, { useState } from "react";
import {
  Activity,
  ChevronUp,
  ChevronDown,
  Terminal,
  Shield,
  Brain,
  Cpu,
  Clock,
  CircleDot,
  CheckCircle2,
  DollarSign
} from "lucide-react";

interface AgentInspectorProps {
  planSteps: any[];
  thoughts: any[];
  toolCalls: any[];
  facts: any[];
  safetyStatus: {
    cost_tracker: number;
    max_cost_usd: number;
    max_iterations: number;
    iterations_used: number;
  };
}

export default function AgentInspector({
  planSteps,
  thoughts,
  toolCalls,
  facts,
  safetyStatus,
}: AgentInspectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [activeSubTab, setActiveSubTab] = useState<"trace" | "tools" | "memory" | "safety">("trace");

  return (
    <div
      id="agent-inspector-container"
      className={`fixed bg-white/90 backdrop-blur-xl shadow-[0_-8px_30px_rgba(0,0,0,0.08)] z-40 transition-all duration-500 ease-in-out ${
        isOpen
          ? "bottom-0 left-0 h-[360px] w-full border-t border-gray-200/80"
          : "bottom-4 left-4 h-10 w-auto rounded-lg border border-gray-200/80"
      }`}
    >
      {/* Header Bar / Toggle */}
      <div
        id="agent-inspector-header"
        onClick={() => setIsOpen(!isOpen)}
        className={`flex cursor-pointer items-center justify-between gap-6 transition-colors hover:bg-gray-50/50 ${
          isOpen ? "h-12 border-b border-gray-100 px-6" : "h-10 rounded-lg px-3"
        }`}
      >
        <div className="flex items-center gap-3">
          <div className="h-6 w-6 rounded-md bg-purple-600/10 flex items-center justify-center text-purple-600 animate-pulse">
            <Cpu className="h-3.5 w-3.5" />
          </div>
          <span className="text-xs font-bold text-gray-800 tracking-wide uppercase">
            {isOpen ? "Agent Inspector & Telemetry" : "Agent Log"}
          </span>
          <span className="text-[10px] bg-purple-50 text-purple-700 px-2 py-0.5 rounded-full font-bold border border-purple-100">
            {toolCalls.length} Operations
          </span>
        </div>

        <div className="flex items-center gap-4">
          <div className={`${isOpen ? "flex" : "hidden"} items-center gap-2 text-[10px] font-semibold text-gray-400`}>
            <span className="flex items-center gap-1">
              <DollarSign className="h-3 w-3" /> Cost: ${safetyStatus.cost_tracker.toFixed(4)}
            </span>
            <span className="h-3 w-px bg-gray-200" />
            <span>
              Step: {safetyStatus.iterations_used}/{safetyStatus.max_iterations}
            </span>
          </div>
          {isOpen ? (
            <ChevronDown className="h-4 w-4 text-gray-400 transition-transform" />
          ) : (
            <ChevronUp className="h-4 w-4 text-gray-400 transition-transform" />
          )}
        </div>
      </div>

      {/* Drawer Content */}
      {isOpen && (
        <div id="agent-inspector-body" className="flex h-[312px]">
          {/* Sidebar Nav */}
          <div className="w-48 border-r border-gray-100 bg-gray-50/40 p-2 space-y-1 flex flex-col justify-between">
            <div className="space-y-1">
              <button
                id="tab-trace"
                onClick={() => setActiveSubTab("trace")}
                className={`w-full px-3 py-2 text-left text-xs font-bold rounded-lg transition-all flex items-center gap-2 ${
                  activeSubTab === "trace"
                    ? "bg-purple-50 text-purple-700 shadow-sm"
                    : "text-gray-500 hover:bg-gray-100/50 hover:text-gray-800"
                }`}
              >
                <Brain className="h-3.5 w-3.5" />
                Reasoning Trace
              </button>
              <button
                id="tab-tools"
                onClick={() => setActiveSubTab("tools")}
                className={`w-full px-3 py-2 text-left text-xs font-bold rounded-lg transition-all flex items-center gap-2 ${
                  activeSubTab === "tools"
                    ? "bg-blue-50 text-blue-700 shadow-sm"
                    : "text-gray-500 hover:bg-gray-100/50 hover:text-gray-800"
                }`}
              >
                <Terminal className="h-3.5 w-3.5" />
                Tool Executions
              </button>
              <button
                id="tab-memory"
                onClick={() => setActiveSubTab("memory")}
                className={`w-full px-3 py-2 text-left text-xs font-bold rounded-lg transition-all flex items-center gap-2 ${
                  activeSubTab === "memory"
                    ? "bg-emerald-50 text-emerald-700 shadow-sm"
                    : "text-gray-500 hover:bg-gray-100/50 hover:text-gray-800"
                }`}
              >
                <Activity className="h-3.5 w-3.5" />
                Semantic Memory
              </button>
              <button
                id="tab-safety"
                onClick={() => setActiveSubTab("safety")}
                className={`w-full px-3 py-2 text-left text-xs font-bold rounded-lg transition-all flex items-center gap-2 ${
                  activeSubTab === "safety"
                    ? "bg-amber-50 text-amber-700 shadow-sm"
                    : "text-gray-500 hover:bg-gray-100/50 hover:text-gray-800"
                }`}
              >
                <Shield className="h-3.5 w-3.5" />
                Safety Telemetry
              </button>
            </div>

            <div className="p-2 border-t border-gray-100 text-[10px] text-gray-400 font-medium">
              Real-time Agent Telemetry Active
            </div>
          </div>

          {/* Active Pane */}
          <div className="flex-1 p-5 overflow-y-auto bg-white">
            {activeSubTab === "trace" && (
              <div className="space-y-4 animate-in fade-in duration-300">
                <div className="flex items-center gap-2 mb-2">
                  <Brain className="h-4 w-4 text-purple-600" />
                  <h4 className="text-xs font-bold text-gray-800 uppercase tracking-wider">
                    Thoughts & Planner Steps
                  </h4>
                </div>

                {thoughts.length === 0 && planSteps.length === 0 ? (
                  <div className="text-center py-10 text-xs text-gray-400 italic">
                    No active agent turn in progress. Ask the Guardian a question to inspect thoughts.
                  </div>
                ) : (
                  <div className="space-y-4">
                    {thoughts.length > 0 && (
                      <div className="p-3 bg-purple-50/50 border border-purple-100 rounded-xl space-y-1">
                        <span className="text-[10px] font-bold text-purple-700 uppercase tracking-wide">
                          Current Thought Trace
                        </span>
                        <p className="text-xs text-purple-900 leading-relaxed font-medium">
                          {thoughts[thoughts.length - 1].content}
                        </p>
                      </div>
                    )}

                    {planSteps.length > 0 && (
                      <div className="space-y-2">
                        <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wide">
                          Execution Path
                        </span>
                        <div className="grid gap-2">
                          {planSteps.map((step) => (
                            <div
                              key={step.id}
                              className="flex items-start gap-2.5 p-2 bg-gray-50 rounded-lg border border-gray-100"
                            >
                              <div className="mt-0.5">
                                {step.status === "done" ? (
                                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                                ) : step.status === "running" ? (
                                  <CircleDot className="h-3.5 w-3.5 text-blue-500 animate-spin" />
                                ) : (
                                  <CircleDot className="h-3.5 w-3.5 text-gray-300" />
                                )}
                              </div>
                              <div className="text-xs text-gray-700 font-medium">
                                {step.text}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {activeSubTab === "tools" && (
              <div className="space-y-4 animate-in fade-in duration-300">
                <div className="flex items-center gap-2 mb-2">
                  <Terminal className="h-4 w-4 text-blue-600" />
                  <h4 className="text-xs font-bold text-gray-800 uppercase tracking-wider">
                    Executed Tool Registry
                  </h4>
                </div>

                {toolCalls.length === 0 ? (
                  <div className="text-center py-10 text-xs text-gray-400 italic">
                    No tools executed yet in this session.
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    {toolCalls.map((tc) => (
                      <div
                        key={tc.id}
                        className="p-3 bg-gray-50 rounded-xl border border-gray-200/60 flex flex-col gap-2 transition-all hover:bg-gray-100/50"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-mono font-bold text-[#0084C7] bg-blue-50 px-2.5 py-0.5 rounded-lg border border-blue-100">
                            {tc.name}
                          </span>
                          <span
                            className={`text-[9px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${
                              tc.status === "done"
                                ? "bg-emerald-50 text-emerald-700 border border-emerald-100"
                                : "bg-blue-50 text-blue-700 border border-blue-100 animate-pulse"
                            }`}
                          >
                            {tc.status}
                          </span>
                        </div>
                        <div className="text-[10px] text-gray-500 font-mono bg-white p-2 rounded-lg border border-gray-100 overflow-x-auto whitespace-pre-wrap">
                          <strong>Arguments:</strong>{" "}
                          {JSON.stringify(tc.args, null, 2)}
                        </div>
                        {tc.result && (
                          <div className="text-[10px] text-emerald-700 font-mono bg-emerald-50/30 p-2 rounded-lg border border-emerald-100/40">
                            <strong>Result Preview:</strong> {tc.result}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeSubTab === "memory" && (
              <div className="space-y-4 animate-in fade-in duration-300">
                <div className="flex items-center gap-2 mb-2">
                  <Brain className="h-4 w-4 text-emerald-600" />
                  <h4 className="text-xs font-bold text-gray-800 uppercase tracking-wider">
                    Semantic Facts Extraction
                  </h4>
                </div>

                {facts.length === 0 ? (
                  <div className="text-center py-10 text-xs text-gray-400 italic">
                    No semantic facts extracted yet from this contract.
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-3">
                    {facts.map((fact, index) => (
                      <div
                        key={index}
                        className="p-3 bg-emerald-50/20 border border-emerald-100 rounded-xl flex flex-col gap-1 hover:bg-emerald-50/40 transition-colors"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-bold text-emerald-800 uppercase">
                            {fact.key}
                          </span>
                          <span className="text-[9px] bg-emerald-50 text-emerald-700 px-1.5 py-0.2 rounded font-mono font-bold">
                            {(fact.confidence * 100).toFixed(0)}% conf
                          </span>
                        </div>
                        <p className="text-xs text-gray-700 font-medium">
                          {fact.value}
                        </p>
                        {fact.source && (
                          <span className="text-[9px] text-gray-400 italic mt-1 font-medium">
                            Source: {fact.source}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeSubTab === "safety" && (
              <div className="space-y-4 animate-in fade-in duration-300">
                <div className="flex items-center gap-2 mb-2">
                  <Shield className="h-4 w-4 text-amber-600" />
                  <h4 className="text-xs font-bold text-gray-800 uppercase tracking-wider">
                    Safety Limits & Observability Metrics
                  </h4>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 bg-gray-50 border border-gray-100 rounded-xl space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-gray-600 uppercase tracking-wider">
                        Session Spend
                      </span>
                      <DollarSign className="h-4 w-4 text-amber-600" />
                    </div>
                    <div className="text-2xl font-bold text-gray-800">
                      ${safetyStatus.cost_tracker.toFixed(4)}
                    </div>
                    <div className="w-full bg-gray-200 h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-amber-500 h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${Math.min(
                            100,
                            (safetyStatus.cost_tracker / safetyStatus.max_cost_usd) * 100
                          )}%`,
                        }}
                      />
                    </div>
                    <div className="text-[9px] text-gray-400 font-semibold uppercase tracking-wider flex justify-between">
                      <span>Limit</span>
                      <span>${safetyStatus.max_cost_usd.toFixed(2)} USD</span>
                    </div>
                  </div>

                  <div className="p-4 bg-gray-50 border border-gray-100 rounded-xl space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-gray-600 uppercase tracking-wider">
                        Iteration Load
                      </span>
                      <Activity className="h-4 w-4 text-blue-600" />
                    </div>
                    <div className="text-2xl font-bold text-gray-800">
                      {safetyStatus.iterations_used}{" "}
                      <span className="text-sm text-gray-400 font-medium">turns</span>
                    </div>
                    <div className="w-full bg-gray-200 h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-blue-500 h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${Math.min(
                            100,
                            (safetyStatus.iterations_used / safetyStatus.max_iterations) * 100
                          )}%`,
                        }}
                      />
                    </div>
                    <div className="text-[9px] text-gray-400 font-semibold uppercase tracking-wider flex justify-between">
                      <span>Max Iterations</span>
                      <span>{safetyStatus.max_iterations}</span>
                    </div>
                  </div>
                </div>

                <div className="p-3 bg-amber-50 border border-amber-100 rounded-xl flex gap-2">
                  <Shield className="h-4 w-4 text-amber-700 shrink-0 mt-0.5" />
                  <div className="text-[10px] text-amber-800 font-medium leading-relaxed">
                    <strong>Guardrails Active:</strong> Self-corrective prompt injection sanitizer, SQL injection blocker, and strict maximum model cost filters are verified active on all incoming and outgoing agent turns.
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
