"use client";

import React from "react";
import {
  Activity,
  CheckCircle2,
  ChevronDown,
  Database,
  FileSpreadsheet,
  RefreshCw,
  ServerCog,
} from "lucide-react";

interface PerformanceActualsProps {
  actuals: any[];
  kpis?: any[];
  integrationConfigs?: Record<string, any>;
  sourceLabels?: Record<string, string>;
  sourceSync?: Record<string, "waiting" | "syncing" | "connected">;
}

type FetchLog = {
  id: string;
  label: string;
  timestamp: string;
  sourceId: string;
  sourceLabel: string;
  connector: string;
  status: string;
  duration: string;
  records: number;
  kpiIds: string[];
  rows: any[];
};

function sourceIdForActual(actual: any) {
  const haystack = [
    actual?.source,
    actual?.metadata?.source_type,
    actual?.metadata?.endpoint,
    actual?.metadata?.workbook,
    actual?.metadata?.sheet,
    actual?.metadata?.ticket,
    actual?.metadata?.queue,
  ].filter(Boolean).join(" ").toLowerCase();

  if (haystack.includes("erp") || haystack.includes("dispatch")) return "erp";
  if (haystack.includes("servicenow") || haystack.includes("ticket") || haystack.includes("emergency")) return "service";
  if (haystack.includes("excel") || haystack.includes("workbook") || haystack.includes("sheet") || haystack.includes("sustainability")) return "excel";
  if (haystack.includes("rest") || haystack.includes("iot") || haystack.includes("temperature") || haystack.includes("incident")) return "rest";
  return "erp";
}

function sourceIcon(sourceId: string) {
  if (sourceId === "erp") return <ServerCog className="h-4 w-4" />;
  if (sourceId === "excel") return <FileSpreadsheet className="h-4 w-4" />;
  if (sourceId === "service") return <Database className="h-4 w-4" />;
  return <Activity className="h-4 w-4" />;
}

function formatTimestamp(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function sampleFields(row: any) {
  const metadata = row?.metadata && typeof row.metadata === "object" ? row.metadata : {};
  return Object.entries({
    timestamp: row?.timestamp,
    value: row?.value,
    unit: row?.unit,
    ...metadata,
  })
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .slice(0, 6);
}

const fallbackRows: Record<string, any[]> = {
  erp: [
    {
      kpi_id: "KPI-001",
      value: 96.4,
      unit: "%",
      timestamp: "2026-05-27T07:00:00Z",
      metadata: { flight_leg_id: "AA-1842-JFK-LAX", catering_order_id: "CTR-90418", delivery_scan_utc: "2026-05-27T10:12:00Z" },
    },
  ],
  rest: [
    {
      kpi_id: "KPI-006",
      value: 97.5,
      unit: "%",
      timestamp: "2026-05-27T06:15:00Z",
      metadata: { endpoint: "/iot/catering/v1/temperature-readings", cart_id: "CART-77", probe_temp_c: "7.9" },
    },
    {
      kpi_id: "KPI-007",
      value: 0,
      unit: "incidents",
      timestamp: "2026-05-27T06:15:00Z",
      metadata: { endpoint: "/aidx/catering/v1/safety-events", station_code: "JFK", severity: "none" },
    },
  ],
  excel: [
    {
      kpi_id: "KPI-003",
      value: 98.9,
      unit: "%",
      timestamp: "2026-05-27T07:20:00Z",
      metadata: { workbook: "catering_order_recon_2026_05_27.xlsx", sheet: "daily_recon", meals_loaded: "18,924" },
    },
    {
      kpi_id: "KPI-015-A",
      value: 44,
      unit: "%",
      timestamp: "2026-05-27T07:20:00Z",
      metadata: { workbook: "packaging_mix_2026_05_27.xlsx", sheet: "sustainability", biodegradable_mix: "44%" },
    },
  ],
  service: [
    {
      kpi_id: "KPI-014",
      value: 42,
      unit: "minutes",
      timestamp: "2026-05-27T08:00:00Z",
      metadata: { number: "INC-7421", assignment_group: "Catering Response", state: "Open" },
    },
  ],
};

function buildFetchLogs(
  actuals: any[],
  sourceLabels: Record<string, string>,
  sourceSync?: Record<string, "waiting" | "syncing" | "connected">
): FetchLog[] {
  const templates = [
    {
      id: "erp-today",
      label: "Today 07:00",
      timestamp: "2026-05-27T07:00:00Z",
      sourceId: "erp",
      connector: "BAPI Z_CTR_FLIGHT_DELIVERY_GET",
      duration: "2.1s",
      records: 224,
      kpiIds: ["KPI-001"],
    },
    {
      id: "rest-today",
      label: "Today 06:15",
      timestamp: "2026-05-27T06:15:00Z",
      sourceId: "rest",
      connector: "GET /iot/catering/v1/temperature-readings + /aidx/catering/v1/safety-events",
      duration: "1.6s",
      records: 126,
      kpiIds: ["KPI-006", "KPI-007"],
    },
    {
      id: "excel-today",
      label: "Today 07:20",
      timestamp: "2026-05-27T07:20:00Z",
      sourceId: "excel",
      connector: "sftp://ops-share/catering/reconciliation/*.xlsx",
      duration: "4.4s",
      records: 86,
      kpiIds: ["KPI-003", "KPI-015-A", "TIM-001"],
    },
    {
      id: "service-today",
      label: "Today 08:00",
      timestamp: "2026-05-27T08:00:00Z",
      sourceId: "service",
      connector: "GET /api/now/table/incident",
      duration: "1.2s",
      records: 14,
      kpiIds: ["KPI-014"],
    },
  ];

  return templates
    .filter((template) => {
      if (!sourceSync) return actuals.length > 0;
      return (sourceSync[template.sourceId] || "waiting") !== "waiting";
    })
    .map((template) => {
      const syncStatus = sourceSync?.[template.sourceId] || "connected";
      const sourceRows = actuals.filter((actual) => sourceIdForActual(actual) === template.sourceId);
      const kpiRows = actuals.filter((actual) => template.kpiIds.includes(actual.kpi_id));
      const rows = (kpiRows.length ? kpiRows : sourceRows).slice(-4).reverse();
      return {
        ...template,
        sourceLabel: sourceLabels[template.sourceId] || template.sourceId,
        status: syncStatus === "syncing" ? "Fetching" : "Completed",
        rows: rows.length ? rows : fallbackRows[template.sourceId] || [],
      };
    })
}

export default function PerformanceActuals({
  actuals,
  kpis = [],
  integrationConfigs = {},
  sourceLabels = {},
  sourceSync,
}: PerformanceActualsProps) {
  const [expandedLogId, setExpandedLogId] = React.useState<string | null>(null);
  const kpiMap = React.useMemo(() => new Map(kpis.map((kpi) => [kpi.kpi_id, kpi])), [kpis]);
  const logs = React.useMemo(() => buildFetchLogs(actuals, sourceLabels, sourceSync), [actuals, sourceLabels, sourceSync]);
  const totalRecords = logs.reduce((sum, log) => sum + log.records, 0);

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
        <div>
          <h3 className="text-sm font-semibold text-gray-800">Performance Logs</h3>
          <p className="mt-0.5 text-xs text-gray-400">Source fetch runs and field usage for compliance evaluation</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 rounded-full border border-blue-100 bg-blue-50 px-2.5 py-1 text-[11px] text-[#0084C7]">
            <RefreshCw className="h-3 w-3" /> {logs.length} fetch runs
          </span>
          <span className="flex items-center gap-1.5 rounded-full border border-emerald-100 bg-emerald-50 px-2.5 py-1 text-[11px] text-emerald-700">
            <Database className="h-3 w-3" /> {totalRecords.toLocaleString()} records fetched
          </span>
        </div>
      </div>

      {logs.length === 0 ? (
        <div className="py-12 text-center text-sm italic text-gray-400">
          No source fetches have run yet. Connect configured sources to start the performance log.
        </div>
      ) : (
        <div className="divide-y divide-gray-100">
          {logs.map((log) => {
            const isOpen = expandedLogId === log.id;
            return (
              <div key={log.id} className="bg-white">
                <button
                  type="button"
                  onClick={() => setExpandedLogId(isOpen ? null : log.id)}
                  className="grid w-full grid-cols-[minmax(160px,0.8fr)_minmax(240px,1.2fr)_minmax(240px,1.4fr)_120px_140px_32px] items-center gap-4 px-5 py-3 text-left transition-colors hover:bg-gray-50"
                >
                  <div>
                    <p className="text-xs font-bold text-slate-800">{log.label}</p>
                    <p className="mt-0.5 text-[10px] font-mono text-slate-400">{formatTimestamp(log.timestamp)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="rounded-md bg-blue-50 p-1.5 text-[#0084C7]">{sourceIcon(log.sourceId)}</span>
                    <div>
                      <p className="text-xs font-bold text-slate-800">{log.sourceLabel}</p>
                      <p className="mt-0.5 text-[10px] uppercase tracking-wide text-slate-400">{log.sourceId}</p>
                    </div>
                  </div>
                  <p className="truncate font-mono text-[11px] text-slate-500">{log.connector}</p>
                  <span className={`inline-flex w-fit items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-bold ${
                    log.status === "Fetching"
                      ? "border-blue-200 bg-blue-50 text-blue-700"
                      : "border-emerald-200 bg-emerald-50 text-emerald-700"
                  }`}>
                    {log.status === "Fetching" ? <RefreshCw className="h-3 w-3 animate-spin" /> : <CheckCircle2 className="h-3 w-3" />}
                    {log.status}
                  </span>
                  <div>
                    <p className="text-xs font-bold text-slate-800">{log.records.toLocaleString()} records</p>
                    <p className="mt-0.5 text-[10px] text-slate-400">{log.duration} fetch time</p>
                  </div>
                  <ChevronDown className={`h-4 w-4 text-slate-300 transition-transform ${isOpen ? "rotate-180" : ""}`} />
                </button>

                {isOpen && (
                  <div className="border-t border-gray-100 bg-slate-50 px-5 py-4">
                    <div className="mb-3 flex flex-wrap items-center gap-2">
                      <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Used by</p>
                      {log.kpiIds.map((kpiId) => (
                        <span key={kpiId} className="rounded-full border border-blue-100 bg-white px-2 py-0.5 text-[10px] font-bold text-blue-700">
                          {kpiId}
                        </span>
                      ))}
                    </div>
                    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
                      <div className="grid grid-cols-[minmax(180px,0.8fr)_minmax(260px,1.2fr)_minmax(260px,1fr)] gap-3 border-b border-slate-100 bg-slate-50 px-4 py-2">
                        <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Fetched data</p>
                        <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Field sample</p>
                        <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Mapped usage</p>
                      </div>
                      <div className="divide-y divide-slate-100">
                        {log.rows.map((row, index) => {
                          const kpi = kpiMap.get(row.kpi_id);
                          const config = integrationConfigs[row.kpi_id];
                          return (
                            <div key={`${log.id}-${row.actual_id || index}`} className="grid grid-cols-[minmax(180px,0.8fr)_minmax(260px,1.2fr)_minmax(260px,1fr)] gap-3 px-4 py-3">
                              <div>
                                <p className="text-xs font-bold text-slate-800">{row.kpi_id}</p>
                                <p className="mt-0.5 line-clamp-2 text-[11px] text-slate-500">{kpi?.name || "Mapped KPI"}</p>
                              </div>
                              <div className="flex flex-wrap gap-1.5">
                                {sampleFields(row).map(([key, value]) => (
                                  <span key={`${row.actual_id || index}-${key}`} className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">
                                    <span className="font-bold text-slate-400">{String(key).replace(/_/g, " ")}:</span> {String(value)}
                                  </span>
                                ))}
                              </div>
                              <div>
                                <p className="text-[11px] font-semibold text-slate-700">
                                  Feeds threshold check {kpi?.operator || ""} {kpi?.value_min ?? kpi?.value ?? ""} {kpi?.unit || ""}
                                </p>
                                <p className="mt-1 text-[10px] text-slate-400">
                                  Join: {config?.joinKey || "contract_id + kpi_id"} · Watermark: {config?.watermark || "timestamp"}
                                </p>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
