"use client";

import React from "react";
import {
  CheckCircle2,
  ChevronDown,
  Database,
  Sparkles,
  FileText,
  Activity,
  RefreshCw,
  ShieldCheck,
  Trash2,
  RotateCcw,
  Lock,
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
  actualsConnected: boolean;
  onReferContract: (kpi: any) => void;
  approvedKpiIds?: Set<string>;
  trackedKpiIds?: Set<string>;
  removedKpiIds?: Set<string>;
  onApproveKpi?: (kpiId: string) => void;
  onApproveAllKpis?: () => void;
  onAmendKpi?: (kpiId: string, patch: Record<string, any>) => void;
  onToggleKpiTracking?: (kpiId: string) => void;
  onTrackRecommendedKpis?: () => void;
  onRemoveKpi?: (kpiId: string) => void;
  onRestoreKpi?: (kpiId: string) => void;
  reviewMode?: boolean;
  integrationConfigs?: Record<string, any>;
  sourceLabels?: Record<string, string>;
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
  actualsConnected,
  onReferContract,
  approvedKpiIds,
  trackedKpiIds,
  removedKpiIds,
  onApproveKpi,
  onApproveAllKpis,
  onToggleKpiTracking,
  onTrackRecommendedKpis,
  onRemoveKpi,
  onRestoreKpi,
  onAmendKpi,
  reviewMode = false,
  integrationConfigs = {},
  sourceLabels = {},
}: KpiRegistryProps) {
  const isTracked = React.useCallback((kpiId: string) => !trackedKpiIds || trackedKpiIds.has(kpiId), [trackedKpiIds]);
  const isApproved = React.useCallback((kpiId: string) => !approvedKpiIds || approvedKpiIds.has(kpiId), [approvedKpiIds]);
  const isRemoved = React.useCallback((kpiId: string) => Boolean(removedKpiIds?.has(kpiId)), [removedKpiIds]);
  const orderedKpis = React.useMemo(() => {
    return [...kpis].sort((a, b) => {
      const rank = (kpi: any) => {
        if (isRemoved(kpi.kpi_id)) return 3;
        if (isTracked(kpi.kpi_id)) return 0;
        if (isApproved(kpi.kpi_id)) return 1;
        return 2;
      };
      return rank(a) - rank(b);
    });
  }, [isApproved, isRemoved, isTracked, kpis]);
  const approvedCount = approvedKpiIds ? kpis.filter((kpi) => approvedKpiIds.has(kpi.kpi_id)).length : kpis.length;
  const trackedCount = trackedKpiIds ? kpis.filter((kpi) => trackedKpiIds.has(kpi.kpi_id)).length : kpis.length;
  const removedCount = removedKpiIds ? kpis.filter((kpi) => removedKpiIds.has(kpi.kpi_id)).length : 0;
  const deferredCount = Math.max(0, approvedCount - trackedCount);
  const pendingCount = Math.max(0, kpis.length - approvedCount - removedCount);
  const canApproveAll = reviewMode && pendingCount > 0;
  const canTrackRecommended = reviewMode && approvedCount > 0 && trackedCount === 0;
  const amendText = React.useCallback((kpiId: string, key: string, value: string) => {
    onAmendKpi?.(kpiId, { [key]: value });
  }, [onAmendKpi]);
  const amendNumber = React.useCallback((kpiId: string, key: string, value: string) => {
    const normalized = value.trim();
    onAmendKpi?.(kpiId, { [key]: normalized === "" ? null : Number(normalized) });
  }, [onAmendKpi]);

  return (
    <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-gray-800">{reviewMode ? "KPI Review" : "Extracted KPI Registry"}</h3>
          <p className="text-xs text-gray-400 mt-0.5">
            {reviewMode
              ? `${approvedCount} approved · ${trackedCount} tracked now · ${deferredCount} deferred · ${pendingCount} pending · ${removedCount} removed.`
              : `${kpis.length} performance metrics extracted from contract clauses`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {reviewMode && (
            <>
              <button
                type="button"
                onClick={onApproveAllKpis}
                disabled={!canApproveAll}
                className="inline-flex items-center gap-1.5 rounded-md bg-slate-900 px-3 py-1.5 text-[11px] font-bold text-white shadow-sm transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-500"
              >
                <CheckCircle2 className="h-3.5 w-3.5" />
                {canApproveAll ? "Accept All KPIs" : "All KPIs Accepted"}
              </button>
              <button
                type="button"
                onClick={onTrackRecommendedKpis}
                disabled={!canTrackRecommended}
                className="inline-flex items-center gap-1.5 rounded-md border border-blue-200 bg-blue-50 px-3 py-1.5 text-[11px] font-bold text-blue-700 shadow-sm transition-colors hover:bg-blue-100 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-50 disabled:text-slate-400"
              >
                <ShieldCheck className="h-3.5 w-3.5" />
                Track Recommended KPIs
              </button>
            </>
          )}
          <span className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] ${
            reviewMode ? "border-amber-200 bg-amber-50 text-amber-700" : "border-gray-100 bg-gray-50 text-gray-400"
          }`}>
            {reviewMode ? <ShieldCheck className="h-3 w-3" /> : <Database className="h-3 w-3" />}
            {reviewMode ? "Uploader review" : "MongoDB"}
          </span>
        </div>
      </div>

      {reviewMode && kpis.length > 0 && (
        <div className="border-b border-amber-100 bg-amber-50 px-5 py-3 text-xs text-amber-800">
          Accept means the extracted KPI is valid. Track now is separate: only tracked KPIs move into source setup and dashboard metrics, while accepted-but-deferred KPIs stay in the registry for later activation.
        </div>
      )}

      {/* Table header */}
      <div className="overflow-x-auto border-b border-gray-100 bg-gray-50">
      <div className="grid min-w-[1540px] grid-cols-[minmax(280px,1fr)_130px_130px_90px_130px_100px_100px_170px_130px_120px_20px] gap-3 items-center px-5 py-2.5">
        <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500">KPI Name / Section</p>
        <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500">Review</p>
        <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500">Tracking</p>
        <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500">Type</p>
        <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500">Threshold</p>
        <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500">Penalty</p>
        <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500">Party</p>
        <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500">Remediation</p>
        <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500">Source Config</p>
        <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500">Contract</p>
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
          orderedKpis.map((kpi) => {
            const hasBreach = activeBreaches.some((b) => b.kpi_id === kpi.kpi_id);
            const isOpen = expandedKpi === kpi.kpi_id;
            const approved = isApproved(kpi.kpi_id);
            const tracked = isTracked(kpi.kpi_id);
            const removed = isRemoved(kpi.kpi_id);
            const config = integrationConfigs[kpi.kpi_id];
            return (
              <div key={kpi.kpi_id}>
                <div
                  onClick={() => handleExpandKpi(kpi.kpi_id)}
                  className={`grid min-w-[1540px] grid-cols-[minmax(280px,1fr)_130px_130px_90px_130px_100px_100px_170px_130px_120px_20px] gap-3 items-center px-5 py-3 transition-colors cursor-pointer ${
                    removed
                      ? "bg-rose-50/40 opacity-60 hover:bg-rose-50"
                      : tracked
                        ? "hover:bg-gray-50"
                        : approved
                          ? "bg-slate-50/60 opacity-85 hover:bg-slate-100"
                          : "bg-slate-50/70 opacity-70 hover:bg-slate-100"
                  } ${
                    hasBreach && tracked && !removed ? "border-l-2 border-l-red-400" : ""
                  }`}
                >
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-gray-800 truncate">{kpi.name}</p>
                    <p className="text-[10px] text-gray-400 mt-0.5 truncate">
                      {kpi.kpi_id} · {kpi.section || "—"}
                    </p>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {reviewMode ? (
                      removed ? (
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            onRestoreKpi?.(kpi.kpi_id);
                          }}
                          className="inline-flex w-fit items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[10px] font-bold text-slate-600 transition-colors hover:bg-slate-100"
                        >
                          <RotateCcw className="h-3 w-3" />
                          Restore
                        </button>
                      ) : approved ? (
                        <span className="inline-flex w-fit items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[10px] font-bold text-emerald-700">
                          <Lock className="h-3 w-3" />
                          Accepted
                        </span>
                      ) : (
                        <>
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              onApproveKpi?.(kpi.kpi_id);
                            }}
                            className="inline-flex w-fit items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[10px] font-bold text-emerald-700 transition-colors hover:bg-emerald-100"
                          >
                            <CheckCircle2 className="h-3 w-3" />
                            Accept
                          </button>
                          <button
                            type="button"
                            aria-label={`Remove ${kpi.name}`}
                            onClick={(event) => {
                              event.stopPropagation();
                              onRemoveKpi?.(kpi.kpi_id);
                            }}
                            className="inline-flex h-6 w-6 items-center justify-center rounded-full border border-rose-200 bg-white text-rose-500 transition-colors hover:bg-rose-50"
                          >
                            <Trash2 className="h-3 w-3" />
                          </button>
                        </>
                      )
                    ) : (
                      <span className={`inline-flex w-fit items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-bold ${
                        approved
                          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                          : "border-slate-200 bg-white text-slate-400"
                      }`}>
                        <ShieldCheck className="h-3 w-3" />
                        {approved ? "Accepted" : "Inactive"}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5">
                    {removed ? (
                      <span className="inline-flex w-fit rounded-full border border-rose-200 bg-white px-2.5 py-1 text-[10px] font-bold text-rose-500">
                        Removed
                      </span>
                    ) : !approved ? (
                      <span className="inline-flex w-fit rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[10px] font-bold text-slate-400">
                        Not tracked
                      </span>
                    ) : reviewMode ? (
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          onToggleKpiTracking?.(kpi.kpi_id);
                        }}
                        className={`inline-flex w-fit items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-bold transition-colors ${
                          tracked
                            ? "border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100"
                            : "border-slate-200 bg-white text-slate-500 hover:bg-slate-100 hover:text-slate-800"
                        }`}
                      >
                        <ShieldCheck className="h-3 w-3" />
                        {tracked ? "Tracked" : "Track now"}
                      </button>
                    ) : (
                      <span className={`inline-flex w-fit items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-bold ${
                        tracked ? "border-blue-200 bg-blue-50 text-blue-700" : "border-slate-200 bg-white text-slate-400"
                      }`}>
                        <ShieldCheck className="h-3 w-3" />
                        {tracked ? "Tracked" : "Deferred"}
                      </span>
                    )}
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
                  <div className="min-w-0">
                    {tracked && !removed && config ? (
                      <>
                        <p className="truncate text-[11px] font-bold text-slate-700">{sourceLabels[config.sourceId] || config.connector || "Configured"}</p>
                        <p className="truncate text-[9px] font-semibold uppercase text-slate-400">{config.pollSchedule}</p>
                      </>
                    ) : (
                      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-300">Inactive</p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      onReferContract(kpi);
                    }}
                    className="inline-flex w-fit items-center gap-1.5 rounded-md border border-blue-100 bg-blue-50 px-2.5 py-1.5 text-[10px] font-bold text-blue-700 shadow-sm transition-colors hover:border-blue-200 hover:bg-blue-100"
                  >
                    <FileText className="h-3 w-3" />
                    Refer Contract
                  </button>
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

                      {reviewMode && (
                        <div className="rounded-lg border border-amber-100 bg-amber-50 p-3">
                          <div className="flex flex-col gap-2 border-b border-amber-100 pb-3 md:flex-row md:items-center md:justify-between">
                            <div>
                              <p className="text-[10px] font-bold uppercase tracking-wide text-amber-700">KPI amendment</p>
                              <p className="mt-0.5 text-xs text-amber-800">
                                Edit extracted fields before accepting the KPI. Accepted KPIs are locked from removal.
                              </p>
                            </div>
                            <div className="rounded-md border border-amber-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700">
                              {removed ? "Removed from this review" : approved ? (tracked ? "Accepted and tracked now" : "Accepted, not tracked yet") : "Pending reviewer decision"}
                            </div>
                          </div>

                          <div className="mt-3 grid gap-3 md:grid-cols-4">
                            <label className="block md:col-span-2">
                              <span className="text-[10px] font-bold uppercase tracking-wide text-amber-700">KPI name</span>
                              <input
                                defaultValue={kpi.name}
                                disabled={approved || removed}
                                className="mt-1 w-full rounded-md border border-amber-200 bg-white px-3 py-2 text-xs font-semibold text-slate-800 focus:border-amber-300 focus:ring-amber-100 disabled:bg-slate-50 disabled:text-slate-400"
                                onClick={(event) => event.stopPropagation()}
                                onBlur={(event) => amendText(kpi.kpi_id, "name", event.target.value)}
                              />
                            </label>
                            <label className="block">
                              <span className="text-[10px] font-bold uppercase tracking-wide text-amber-700">Operator</span>
                              <input
                                defaultValue={kpi.operator || ""}
                                disabled={approved || removed}
                                className="mt-1 w-full rounded-md border border-amber-200 bg-white px-3 py-2 text-xs font-semibold text-slate-800 focus:border-amber-300 focus:ring-amber-100 disabled:bg-slate-50 disabled:text-slate-400"
                                onClick={(event) => event.stopPropagation()}
                                onBlur={(event) => amendText(kpi.kpi_id, "operator", event.target.value)}
                              />
                            </label>
                            <label className="block">
                              <span className="text-[10px] font-bold uppercase tracking-wide text-amber-700">Unit</span>
                              <input
                                defaultValue={kpi.unit || ""}
                                disabled={approved || removed}
                                className="mt-1 w-full rounded-md border border-amber-200 bg-white px-3 py-2 text-xs font-semibold text-slate-800 focus:border-amber-300 focus:ring-amber-100 disabled:bg-slate-50 disabled:text-slate-400"
                                onClick={(event) => event.stopPropagation()}
                                onBlur={(event) => amendText(kpi.kpi_id, "unit", event.target.value)}
                              />
                            </label>
                            <label className="block">
                              <span className="text-[10px] font-bold uppercase tracking-wide text-amber-700">Threshold min</span>
                              <input
                                type="number"
                                step="0.01"
                                defaultValue={kpi.value_min ?? ""}
                                disabled={approved || removed}
                                className="mt-1 w-full rounded-md border border-amber-200 bg-white px-3 py-2 text-xs font-semibold text-slate-800 focus:border-amber-300 focus:ring-amber-100 disabled:bg-slate-50 disabled:text-slate-400"
                                onClick={(event) => event.stopPropagation()}
                                onBlur={(event) => amendNumber(kpi.kpi_id, "value_min", event.target.value)}
                              />
                            </label>
                            <label className="block">
                              <span className="text-[10px] font-bold uppercase tracking-wide text-amber-700">Threshold max</span>
                              <input
                                type="number"
                                step="0.01"
                                defaultValue={kpi.value_max ?? ""}
                                disabled={approved || removed}
                                className="mt-1 w-full rounded-md border border-amber-200 bg-white px-3 py-2 text-xs font-semibold text-slate-800 focus:border-amber-300 focus:ring-amber-100 disabled:bg-slate-50 disabled:text-slate-400"
                                onClick={(event) => event.stopPropagation()}
                                onBlur={(event) => amendNumber(kpi.kpi_id, "value_max", event.target.value)}
                              />
                            </label>
                            <label className="block">
                              <span className="text-[10px] font-bold uppercase tracking-wide text-amber-700">Penalty value</span>
                              <input
                                type="number"
                                step="0.01"
                                defaultValue={kpi.consequence_value ?? ""}
                                disabled={approved || removed}
                                className="mt-1 w-full rounded-md border border-amber-200 bg-white px-3 py-2 text-xs font-semibold text-slate-800 focus:border-amber-300 focus:ring-amber-100 disabled:bg-slate-50 disabled:text-slate-400"
                                onClick={(event) => event.stopPropagation()}
                                onBlur={(event) => amendNumber(kpi.kpi_id, "consequence_value", event.target.value)}
                              />
                            </label>
                            <label className="block">
                              <span className="text-[10px] font-bold uppercase tracking-wide text-amber-700">Responsible party</span>
                              <input
                                defaultValue={kpi.party || ""}
                                disabled={approved || removed}
                                className="mt-1 w-full rounded-md border border-amber-200 bg-white px-3 py-2 text-xs font-semibold text-slate-800 focus:border-amber-300 focus:ring-amber-100 disabled:bg-slate-50 disabled:text-slate-400"
                                onClick={(event) => event.stopPropagation()}
                                onBlur={(event) => amendText(kpi.kpi_id, "party", event.target.value)}
                              />
                            </label>
                            <label className="block md:col-span-2">
                              <span className="text-[10px] font-bold uppercase tracking-wide text-amber-700">Trigger condition</span>
                              <input
                                defaultValue={kpi.trigger_condition || ""}
                                disabled={approved || removed}
                                className="mt-1 w-full rounded-md border border-amber-200 bg-white px-3 py-2 text-xs font-semibold text-slate-800 focus:border-amber-300 focus:ring-amber-100 disabled:bg-slate-50 disabled:text-slate-400"
                                onClick={(event) => event.stopPropagation()}
                                onBlur={(event) => amendText(kpi.kpi_id, "trigger_condition", event.target.value)}
                              />
                            </label>
                            <label className="block">
                              <span className="text-[10px] font-bold uppercase tracking-wide text-amber-700">Remediation SLA</span>
                              <input
                                defaultValue={kpi.remediation_sla || ""}
                                disabled={approved || removed}
                                className="mt-1 w-full rounded-md border border-amber-200 bg-white px-3 py-2 text-xs font-semibold text-slate-800 focus:border-amber-300 focus:ring-amber-100 disabled:bg-slate-50 disabled:text-slate-400"
                                onClick={(event) => event.stopPropagation()}
                                onBlur={(event) => amendText(kpi.kpi_id, "remediation_sla", event.target.value)}
                              />
                            </label>
                            <label className="block md:col-span-3">
                              <span className="text-[10px] font-bold uppercase tracking-wide text-amber-700">Remediation action</span>
                              <input
                                defaultValue={kpi.remediation || ""}
                                disabled={approved || removed}
                                className="mt-1 w-full rounded-md border border-amber-200 bg-white px-3 py-2 text-xs font-semibold text-slate-800 focus:border-amber-300 focus:ring-amber-100 disabled:bg-slate-50 disabled:text-slate-400"
                                onClick={(event) => event.stopPropagation()}
                                onBlur={(event) => amendText(kpi.kpi_id, "remediation", event.target.value)}
                              />
                            </label>
                          </div>

                          <div className="mt-3 flex flex-wrap items-center gap-2">
                            {removed ? (
                              <button
                                type="button"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  onRestoreKpi?.(kpi.kpi_id);
                                }}
                                className="inline-flex h-9 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 text-xs font-bold text-slate-700 hover:bg-slate-100"
                              >
                                <RotateCcw className="h-3.5 w-3.5" />
                                Restore
                              </button>
                            ) : approved ? (
                              <button
                                type="button"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  onToggleKpiTracking?.(kpi.kpi_id);
                                }}
                                className={`inline-flex h-9 items-center gap-1.5 rounded-md px-3 text-xs font-bold ${
                                  tracked
                                    ? "border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100"
                                    : "border border-slate-200 bg-white text-slate-700 hover:bg-slate-100"
                                }`}
                              >
                                <ShieldCheck className="h-3.5 w-3.5" />
                                {tracked ? "Tracking Now" : "Track Now"}
                              </button>
                            ) : (
                              <>
                                <button
                                  type="button"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    onApproveKpi?.(kpi.kpi_id);
                                  }}
                                  className="inline-flex h-9 items-center gap-1.5 rounded-md bg-slate-900 px-3 text-xs font-bold text-white hover:bg-slate-800"
                                >
                                  <ShieldCheck className="h-3.5 w-3.5" />
                                  Accept KPI
                                </button>
                                <button
                                  type="button"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    onRemoveKpi?.(kpi.kpi_id);
                                  }}
                                  className="inline-flex h-9 items-center gap-1.5 rounded-md border border-rose-200 bg-white px-3 text-xs font-bold text-rose-600 hover:bg-rose-50"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                  Remove
                                </button>
                              </>
                            )}
                          </div>
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
                            {actualsConnected && (
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
                            )}
                          </div>
                          <span className="text-[10px] font-medium text-[#0084C7] bg-blue-50 px-2 py-0.5 rounded-full">
                            {actualsConnected ? kpiTimeSeries[kpi.kpi_id]?.data?.length || 0 : 0} records
                          </span>
                        </div>
                        <div className="h-[200px] w-full">
                          {!actualsConnected ? (
                            <div className="flex h-full items-center justify-center rounded-lg border border-dashed border-gray-200 bg-gray-50 text-center">
                              <div>
                                <Database className="mx-auto h-5 w-5 text-gray-300" />
                                <p className="mt-2 text-xs font-semibold text-gray-500">No actuals connected yet</p>
                                <p className="mt-1 text-[11px] text-gray-400">Connect evidence sources to populate KPI history.</p>
                              </div>
                            </div>
                          ) : !kpiTimeSeries[kpi.kpi_id] ? (
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
