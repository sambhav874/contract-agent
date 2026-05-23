"use client";

import React from "react";
import {
  ChevronDown,
  Database,
  Sparkles,
  FileText,
  Activity,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import {
  ComposedChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  Line,
  ResponsiveContainer,
} from "recharts";
import { KPI_TYPE_COLORS } from "@/lib/utils";

interface KpiRegistryProps {
  kpis: any[];
  activeBreaches: any[];
  expandedKpi: string | null;
  handleExpandKpi: (kpiId: string) => void;
  chartMode: "actual" | "cumulative";
  setChartMode: (mode: "actual" | "cumulative") => void;
  kpiTimeSeries: Record<string, any>;
  loading: boolean;
  extracting: boolean;
  onExtractKPIs: () => void;
}

export default function KpiRegistry({
  kpis,
  activeBreaches,
  expandedKpi,
  handleExpandKpi,
  chartMode,
  setChartMode,
  kpiTimeSeries,
  loading,
  extracting,
  onExtractKPIs,
}: KpiRegistryProps) {
  return (
    <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-gray-800">Extracted KPI Registry</h3>
          <p className="text-xs text-gray-400 mt-0.5">
            {kpis.length} performance metrics extracted from contract clauses
          </p>
        </div>
        <span className="flex items-center gap-1.5 text-[11px] text-gray-400 bg-gray-50 border border-gray-100 px-2.5 py-1 rounded-full">
          <Database className="h-3 w-3" /> MongoDB
        </span>
      </div>

      {/* Table header */}
      <div className="overflow-x-auto border-b border-gray-100 bg-gray-50">
      <div className="grid min-w-[980px] grid-cols-[minmax(280px,1fr)_90px_130px_100px_100px_170px_20px] gap-3 items-center px-5 py-2.5">
        <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500">KPI Name / Section</p>
        <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500">Type</p>
        <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500">Threshold</p>
        <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500">Penalty</p>
        <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500">Party</p>
        <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500">Remediation</p>
        <div />
      </div>
      </div>

      {/* Table body */}
      <div className="divide-y divide-gray-100 overflow-x-auto">
        {loading ? (
          <div className="py-12 text-center text-sm text-gray-400">Loading KPIs...</div>
        ) : kpis.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-4 px-6 py-14 text-center">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-800">No KPIs extracted yet</p>
              <p className="mt-1 text-xs text-gray-400">The contract is indexed and ready for KPI extraction.</p>
            </div>
            <button
              onClick={onExtractKPIs}
              disabled={extracting}
              className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Sparkles className={`h-3.5 w-3.5 ${extracting ? "animate-pulse" : ""}`} />
              {extracting ? "Extracting KPIs..." : "Extract KPIs"}
            </button>
          </div>
        ) : (
          kpis.map((kpi) => {
            const hasBreach = activeBreaches.some((b) => b.kpi_id === kpi.kpi_id);
            const isOpen = expandedKpi === kpi.kpi_id;
            return (
              <div key={kpi.kpi_id}>
                <div
                  onClick={() => handleExpandKpi(kpi.kpi_id)}
                  className={`grid min-w-[980px] grid-cols-[minmax(280px,1fr)_90px_130px_100px_100px_170px_20px] gap-3 items-center px-5 py-3 hover:bg-gray-50 transition-colors cursor-pointer ${
                    hasBreach ? "border-l-2 border-l-red-400" : ""
                  }`}
                >
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-gray-800 truncate">{kpi.name}</p>
                    <p className="text-[10px] text-gray-400 mt-0.5 truncate">
                      {kpi.kpi_id} · {kpi.section || "—"}
                    </p>
                  </div>
                  <div>
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                        KPI_TYPE_COLORS[kpi.kpi_type] || KPI_TYPE_COLORS.other
                      }`}
                    >
                      {kpi.kpi_type}
                    </span>
                  </div>
                  <div>
                    <p className="text-sm font-bold text-gray-800">
                      {kpi.operator} {kpi.value_min}
                      {kpi.value_max ? ` – ${kpi.value_max}` : ""}
                    </p>
                    <p className="text-[10px] text-gray-400">{kpi.unit}</p>
                  </div>
                  <div>
                    {kpi.consequence_value ? (
                      <p className="text-sm font-bold text-red-600">${kpi.consequence_value.toLocaleString()}</p>
                    ) : (
                      <p className="text-[10px] text-gray-300 italic">None</p>
                    )}
                    {kpi.consequence_unit && <p className="text-[10px] text-gray-400">{kpi.consequence_unit}</p>}
                  </div>
                  <p className="text-xs text-gray-600 truncate">{kpi.party || "—"}</p>
                  <div className="min-w-0">
                    {kpi.remediation ? (
                      <>
                        <p className="text-[11px] text-amber-700 font-medium truncate">{kpi.remediation}</p>
                        {kpi.remediation_sla && (
                          <p className="text-[9px] text-gray-400 uppercase font-bold mt-0.5">SLA: {kpi.remediation_sla}</p>
                        )}
                      </>
                    ) : (
                      <p className="text-[10px] text-gray-300 italic">Not defined</p>
                    )}
                  </div>
                  <ChevronDown className={`h-4 w-4 text-gray-300 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`} />
                </div>

                {/* ── Expanded Detail Panel ──────────────────── */}
                {isOpen && (
                  <div
                    className="px-10 pb-5 pt-2 bg-gray-50/60 border-t border-gray-100"
                    style={{ animation: "slideDown 0.2s ease-out" }}
                  >
                    <div className="space-y-4 pt-2">
                      {/* Clause Text */}
                      {kpi.clause_text && (
                        <div className="p-3 rounded-lg bg-white border border-gray-200">
                          <p className="text-[10px] font-bold uppercase text-gray-500 mb-1.5">Verbatim Contract Text</p>
                          <p className="text-sm text-gray-700 leading-relaxed italic">&ldquo;{kpi.clause_text}&rdquo;</p>
                        </div>
                      )}

                      {/* Grid: Threshold + Trigger + Penalty */}
                      <div className="grid grid-cols-3 gap-3">
                        <div className="p-3 rounded-lg bg-blue-50 border border-blue-100">
                          <p className="text-[10px] font-bold uppercase text-[#0084C7] mb-1">Threshold Rule</p>
                          <p className="text-sm font-bold text-blue-800">
                            {kpi.operator} {kpi.value_min}
                            {kpi.value_max ? ` – ${kpi.value_max}` : ""}
                          </p>
                          <p className="text-[10px] text-blue-600 mt-0.5">{kpi.unit}</p>
                        </div>
                        <div className="p-3 rounded-lg bg-amber-50 border border-amber-100">
                          <p className="text-[10px] font-bold uppercase text-amber-700 mb-1">Trigger Condition</p>
                          <p className="text-xs text-amber-800 leading-relaxed">{kpi.trigger_condition || "Not specified"}</p>
                        </div>
                        <div className="p-3 rounded-lg bg-red-50 border border-red-100">
                          <p className="text-[10px] font-bold uppercase text-red-600 mb-1">Penalty / Consequence</p>
                          {kpi.consequence_value ? (
                            <p className="text-sm font-bold text-red-700">
                              ${kpi.consequence_value.toLocaleString()}{" "}
                              <span className="text-[10px] font-normal text-red-500">{kpi.consequence_unit}</span>
                            </p>
                          ) : (
                            <p className="text-xs text-red-400 italic">No penalty defined</p>
                          )}
                        </div>
                      </div>

                      {/* Grid: Section Path + Party + Confidence */}
                      <div className="grid grid-cols-3 gap-3">
                        <div className="flex items-start gap-2 p-2.5 rounded-lg bg-white border border-gray-200">
                          <Sparkles className="h-3.5 w-3.5 mt-0.5 shrink-0 text-[#0084C7]" />
                          <div>
                            <p className="text-[10px] font-bold uppercase text-[#0084C7] mb-0.5">Structural Path</p>
                            <p className="text-xs text-gray-700 leading-relaxed">{kpi.structural_path || kpi.section || "—"}</p>
                          </div>
                        </div>
                        <div className="flex items-start gap-2 p-2.5 rounded-lg bg-white border border-gray-200">
                          <FileText className="h-3.5 w-3.5 mt-0.5 shrink-0 text-gray-400" />
                          <div>
                            <p className="text-[10px] font-bold uppercase text-gray-500 mb-0.5">Responsible Party</p>
                            <p className="text-xs font-semibold text-gray-700">{kpi.party || "—"}</p>
                          </div>
                        </div>
                        <div className="flex items-start gap-2 p-2.5 rounded-lg bg-white border border-gray-200">
                          <Activity className="h-3.5 w-3.5 mt-0.5 shrink-0 text-gray-400" />
                          <div>
                            <p className="text-[10px] font-bold uppercase text-gray-500 mb-0.5">Confidence</p>
                            <div className="flex items-center gap-2 mt-0.5">
                              <div className="w-20 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-[#0084C7] rounded-full"
                                  style={{ width: `${(kpi.confidence || 0) * 100}%` }}
                                />
                              </div>
                              <span className="text-xs font-bold text-gray-700">
                                {((kpi.confidence || 0) * 100).toFixed(0)}%
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Performance History Chart */}
                      <div className="p-3 rounded-lg bg-white border border-gray-200">
                        <div className="flex items-center justify-between mb-4">
                          <div className="flex items-center gap-2">
                            <p className="text-[10px] font-bold uppercase text-gray-500">Historical Performance Logs</p>
                            <div className="flex bg-gray-100 p-0.5 rounded-md border border-gray-200">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setChartMode("actual");
                                }}
                                className={`px-2 py-0.5 rounded text-[9px] font-bold transition-all ${
                                  chartMode === "actual"
                                    ? "bg-white text-blue-600 shadow-sm"
                                    : "text-gray-400 hover:text-gray-600"
                                }`}
                              >
                                ACTUAL
                              </button>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setChartMode("cumulative");
                                }}
                                className={`px-2 py-0.5 rounded text-[9px] font-bold transition-all ${
                                  chartMode === "cumulative"
                                    ? "bg-white text-blue-600 shadow-sm"
                                    : "text-gray-400 hover:text-gray-600"
                                }`}
                              >
                                CUMULATIVE
                              </button>
                            </div>
                          </div>
                          <span className="text-[10px] font-medium text-[#0084C7] bg-blue-50 px-2 py-0.5 rounded-full">
                            {kpiTimeSeries[kpi.kpi_id]?.data?.length || 0} records
                          </span>
                        </div>
                        <div className="h-[200px] w-full">
                          {!kpiTimeSeries[kpi.kpi_id] ? (
                            <div className="h-full flex items-center justify-center">
                              <RefreshCw className="h-5 w-5 text-gray-300 animate-spin" />
                            </div>
                          ) : (
                            <ResponsiveContainer width="100%" height="100%">
                              <ComposedChart
                                data={(() => {
                                  const rawData = kpiTimeSeries[kpi.kpi_id].data;
                                  if (chartMode === "actual") return rawData;

                                  let runningTotal = 0;
                                  return rawData.map((d: any) => {
                                    runningTotal += Number(d.value || 0);
                                    return { ...d, value: runningTotal };
                                  });
                                })()}
                                margin={{ top: 5, right: 5, left: -20, bottom: 0 }}
                              >
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                <XAxis
                                  dataKey="timestamp"
                                  tickFormatter={(t) =>
                                    new Date(t).toLocaleDateString(undefined, { month: "short", day: "numeric" })
                                  }
                                  axisLine={false}
                                  tickLine={false}
                                  tick={{ fontSize: 10, fill: "#94a3b8" }}
                                />
                                <YAxis yAxisId="left" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: "#94a3b8" }} />
                                <Tooltip
                                  labelFormatter={(t) => new Date(t).toLocaleString()}
                                  contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px", padding: "8px" }}
                                />
                                <Legend wrapperStyle={{ fontSize: "10px" }} />
                                <Line
                                  yAxisId="left"
                                  type="monotone"
                                  dataKey="value"
                                  name={chartMode === "cumulative" ? "Cumulative Progress" : "Daily Delivery"}
                                  stroke="#0084C7"
                                  strokeWidth={2}
                                  dot={chartMode === "actual" ? { r: 3, fill: "#0084C7" } : false}
                                  activeDot={{ r: 5 }}
                                />
                                {kpiTimeSeries[kpi.kpi_id].trend?.threshold && (
                                  <Line
                                    yAxisId="left"
                                    type="step"
                                    dataKey={() => kpiTimeSeries[kpi.kpi_id].trend.threshold}
                                    name="Threshold"
                                    stroke="#ef4444"
                                    strokeWidth={1}
                                    strokeDasharray="5 5"
                                    dot={false}
                                    activeDot={false}
                                  />
                                )}
                              </ComposedChart>
                            </ResponsiveContainer>
                          )}
                        </div>
                      </div>

                      {/* Remediation */}
                      <div
                        className={`flex items-start gap-2 p-2.5 rounded-lg ${
                          kpi.remediation ? "bg-amber-50 border-amber-200" : "bg-gray-50 border-gray-200"
                        } border`}
                      >
                        <ShieldCheck
                          className={`h-3.5 w-3.5 mt-0.5 shrink-0 ${kpi.remediation ? "text-amber-600" : "text-gray-400"}`}
                        />
                        <div className="w-full">
                          <p
                            className={`text-[10px] font-bold uppercase mb-0.5 ${
                              kpi.remediation ? "text-amber-600" : "text-gray-500"
                            }`}
                          >
                            Remediation Protocol
                          </p>
                          <p className="text-xs text-gray-700 leading-relaxed">
                            {kpi.remediation || "No remediation defined for this KPI."}
                          </p>
                          {kpi.remediation_sla && (
                            <p className="text-[10px] font-bold text-amber-700 mt-1.5 uppercase">
                              Response SLA: {kpi.remediation_sla}
                            </p>
                          )}
                        </div>
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
