"use client";

import React from "react";
import {
  Clock,
  ChevronDown,
  Sparkles,
  Database,
  ShieldCheck,
  Bell,
  Bot,
  MailWarning,
  Trash2,
} from "lucide-react";
import { SEV_CONFIG, STATUS_CONFIG } from "@/lib/utils";

interface ComplianceFlagsProps {
  flags: any[];
  expandedFlag: string | null;
  setExpandedFlag: (flagId: string | null) => void;
  handleUpdateStatus: (breachId: string, newStatus: string) => void;
  handleUpdateNotes: (breachId: string, newNotes: string) => void;
  handleChat: (query: string, breachId?: string) => void;
  handleOpenEmailModal: (breachId: string) => void;
  handleRemoveFlag: (breachId: string) => void;
}

export default function ComplianceFlags({
  flags,
  expandedFlag,
  setExpandedFlag,
  handleUpdateStatus,
  handleUpdateNotes,
  handleChat,
  handleOpenEmailModal,
  handleRemoveFlag,
}: ComplianceFlagsProps) {
  return (
    <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
      <div className="px-5 py-4 border-b border-gray-100">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-sm font-semibold text-gray-800">Compliance Flags</h3>
            <p className="text-xs text-gray-400 mt-0.5">
              Breach evaluation results · sorted Critical → OK · click to expand
            </p>
          </div>
        </div>
        <div className="-mx-5 mt-4 overflow-x-auto border-t border-gray-100 bg-gray-50">
        <div className="grid min-w-[760px] grid-cols-[20px_minmax(260px,1fr)_120px_120px_104px_20px] gap-4 items-center px-5 py-2.5">
          <div />
          <p className="text-[11px] font-bold uppercase tracking-wider text-gray-500">Flag / KPI</p>
          <p className="text-[11px] font-bold uppercase tracking-wider text-gray-500 text-right">Impact</p>
          <p className="text-[11px] font-bold uppercase tracking-wider text-gray-500">Status</p>
          <p className="text-[11px] font-bold uppercase tracking-wider text-gray-500">Severity</p>
          <div className="w-4" />
        </div>
        </div>
      </div>

      <div className="divide-y divide-gray-100 overflow-x-auto">
        {flags.length === 0 ? (
          <div className="py-12 text-center text-sm text-gray-400 italic">
            No breach data available. Run the breach engine first.
          </div>
        ) : (
          flags.map((flag) => {
            const s = SEV_CONFIG[flag.severity] || SEV_CONFIG.LOW;
            const Icon = s.icon;
            const isOpen = expandedFlag === flag.breach_id;
            const kpi = flag.kpi;
            const impactStr = flag.penalty_amount
              ? `-$${Math.abs(flag.penalty_amount).toLocaleString()}`
              : flag.penalty_triggered || "None";

            return (
              <div key={flag.breach_id} className="hover:bg-gray-50 transition-colors">
                <div
                  className="grid min-w-[760px] grid-cols-[20px_minmax(260px,1fr)_120px_120px_104px_20px] gap-4 items-center px-5 py-3.5 cursor-pointer"
                  onClick={() => setExpandedFlag(isOpen ? null : flag.breach_id)}
                >
                  <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${s.dot}`} />
                  <div className="min-w-0 pr-4">
                    <p className="text-sm font-semibold text-gray-800 truncate">{kpi?.name || flag.kpi_id}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <p className="text-[11px] text-gray-400">
                        {flag.kpi_id} · {kpi?.kpi_type || "compliance"}
                      </p>
                      {flag.remediation_sla && (
                        <span className="flex items-center gap-1 bg-amber-50 text-amber-700 border border-amber-200 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider">
                          <Clock className="h-2.5 w-2.5" /> SLA: {flag.remediation_sla}
                        </span>
                      )}
                    </div>
                  </div>
                  <span className="line-clamp-2 text-right text-xs font-semibold text-red-600">{impactStr}</span>

                  <div>
                    <select
                      value={flag.status || "Open"}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => handleUpdateStatus(flag.breach_id || flag._id, e.target.value)}
                      className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                        STATUS_CONFIG[flag.status || "Open"]?.bg
                      } ${STATUS_CONFIG[flag.status || "Open"]?.color} ${
                        STATUS_CONFIG[flag.status || "Open"]?.border
                      } focus:ring-0 cursor-pointer`}
                    >
                      <option value="Open">Open</option>
                      <option value="In Progress">In Progress</option>
                      <option value="Resolved">Resolved</option>
                      <option value="Waived">Waived</option>
                    </select>
                  </div>

                  <span
                    className={`flex items-center justify-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-semibold ${s.badge}`}
                  >
                    <Icon className="h-3 w-3 shrink-0" />{" "}
                    <span className="truncate">
                      {flag.severity === "LOW" ? "OK" : flag.severity.charAt(0) + flag.severity.slice(1).toLowerCase()}
                    </span>
                  </span>
                  <ChevronDown className={`h-4 w-4 text-gray-300 transition-transform ${isOpen ? "rotate-180" : ""}`} />
                </div>

                {isOpen && (
                  <div
                    className="px-10 pb-5 pt-1 bg-gray-50/60 border-t border-gray-100"
                    style={{ animation: "slideDown 0.2s ease-out" }}
                  >
                    <div className="pt-3 space-y-4">
                      <p className="text-sm text-gray-600 leading-relaxed">
                        {flag.is_breach
                          ? `Actual value (${flag.actual_value}) ${
                              flag.operator === ">=" ? "fell below" : "exceeded"
                            } the contractual threshold (${flag.threshold_value}). ${kpi?.trigger_condition || ""}`
                          : `Performance is within the contractual threshold. No action required.`}
                      </p>

                      {/* Expected vs Actual */}
                      <div className="grid grid-cols-2 gap-3">
                        <div className="p-3 rounded-lg bg-green-50 border border-green-100">
                          <p className="text-[10px] font-bold uppercase text-green-600">Expected (Contract)</p>
                          <p className="text-sm text-green-700 font-semibold mt-1">
                            {kpi?.operator} {kpi?.value_min} {kpi?.unit}
                          </p>
                        </div>
                        <div className={`p-3 rounded-lg ${s.bg} border ${s.border}`}>
                          <p className={`text-[10px] font-bold uppercase ${s.color}`}>Actual (Ingested)</p>
                          <p className={`text-sm font-semibold mt-1 ${s.color}`}>
                            {flag.actual_value} {kpi?.unit}
                            {flag.sample_count > 1 && (
                              <span className="text-[10px] opacity-60 ml-1.5 font-normal tracking-tight italic">
                                (Avg of {flag.sample_count})
                              </span>
                            )}
                          </p>
                        </div>
                      </div>

                      {/* Clause + Data Source */}
                      <div className="grid grid-cols-2 gap-3">
                        <div className="flex items-start gap-2 p-2.5 rounded-lg bg-blue-50 border border-blue-100">
                          <Sparkles className="h-3.5 w-3.5 mt-0.5 shrink-0 text-[#0084C7]" />
                          <div>
                            <p className="text-[10px] font-bold uppercase text-[#0084C7] mb-0.5">Contract Clause</p>
                            <p className="text-xs text-blue-700 leading-relaxed">
                              {kpi?.structural_path || kpi?.section || "—"}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-start gap-2 p-2.5 rounded-lg bg-gray-100 border border-gray-200">
                          <Database className="h-3.5 w-3.5 mt-0.5 shrink-0 text-gray-400" />
                          <div>
                            <p className="text-[10px] font-bold uppercase text-gray-500 mb-0.5">Data Source</p>
                            <p className="text-xs font-semibold text-gray-700">Breach Engine (Automated)</p>
                            <p className="text-[11px] text-gray-400 mt-0.5">Timestamp: {flag.timestamp || "—"}</p>
                          </div>
                        </div>
                      </div>

                      {/* Remediation */}
                      <div className={`flex items-start gap-2 p-2.5 rounded-lg ${s.bg} border ${s.border}`}>
                        <ShieldCheck className={`h-3.5 w-3.5 mt-0.5 shrink-0 ${s.color}`} />
                        <div className="w-full">
                          <p className={`text-[10px] font-bold uppercase mb-0.5 ${s.color}`}>Recommended Action</p>
                          <p className="text-xs text-gray-700 leading-relaxed">
                            {flag.remediation || kpi?.remediation || "Standard monitoring — no escalation required."}
                          </p>
                          <div className="flex items-center gap-4 mt-2">
                            <span className="text-[11px] text-gray-500">
                              Party: <span className="font-semibold text-gray-700">{kpi?.party || "—"}</span>
                            </span>
                            <span className={`text-[11px] font-bold ${s.color}`}>Response: {s.response}</span>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 text-xs text-gray-400">
                        <Bell className="h-3 w-3" />
                        Penalty:{" "}
                        <span className="font-semibold text-gray-600">
                          {flag.penalty_amount ? `$${flag.penalty_amount.toLocaleString()}` : "None"}
                        </span>
                        {flag.penalty_triggered && (
                          <>
                            {" "}
                            · Trigger: <span className="font-semibold text-gray-600">{flag.penalty_triggered}</span>
                          </>
                        )}
                      </div>

                      {/* Remediation Notes */}
                      <div className="p-3 rounded-lg bg-white border border-gray-200">
                        <p className="text-[10px] font-bold uppercase text-gray-500 mb-1.5">Remediation Notes / CAP</p>
                        <textarea
                          defaultValue={flag.notes || ""}
                          onBlur={(e) => handleUpdateNotes(flag.breach_id || flag._id, e.target.value)}
                          placeholder="Add notes, link to CAP documents, or record root cause analysis..."
                          className="w-full text-xs text-gray-700 bg-gray-50 border border-gray-100 rounded p-2 h-20 focus:ring-1 focus:ring-blue-200 focus:border-blue-300 resize-none transition-all"
                        />
                        <p className="text-[9px] text-gray-400 mt-1 flex items-center gap-1 italic">
                          <Sparkles className="h-2 w-2" /> Auto-saves when you click outside the box
                        </p>
                      </div>

                      <div className="grid grid-cols-3 gap-2 mt-2">
                        <button
                          onClick={() =>
                            handleChat(
                              `Explain the penalty logic and any excusable delays for this ${flag.kpi_id} breach.`,
                              flag.breach_id || flag._id
                            )
                          }
                          className="w-full flex items-center justify-center gap-2 py-2 px-4 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-[11px] font-bold transition-all shadow-md active:scale-[0.98]"
                        >
                          <Bot className="h-3.5 w-3.5" />
                          Ask AI to Analyze
                        </button>
                        <button
                          onClick={() => handleRemoveFlag(flag.breach_id || flag._id)}
                          className="w-full flex items-center justify-center gap-2 py-2 px-4 rounded-lg bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 text-[11px] font-bold transition-all shadow-sm active:scale-[0.98]"
                        >
                          <Trash2 className="h-3.5 w-3.5 text-gray-500" />
                          Remove Flag
                        </button>
                        <button
                          onClick={() => handleOpenEmailModal(flag.breach_id || flag._id)}
                          className="w-full flex items-center justify-center gap-2 py-2 px-4 rounded-lg bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 text-[11px] font-bold transition-all shadow-sm active:scale-[0.98]"
                        >
                          <MailWarning className="h-3.5 w-3.5 text-amber-600" />
                          Send Escalation Alert
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
