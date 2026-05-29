"use client";

import React from "react";
import {
  CheckCircle2,
  Database,
  FileSpreadsheet,
  Link2,
  RefreshCw,
  ServerCog,
  Settings2,
  ShieldCheck,
} from "lucide-react";

interface IntegrationConfig {
  sourceId: string;
  pollSchedule: string;
  connector: string;
  interfaceName?: string;
  bapiFunction?: string;
  endpoint?: string;
  filePattern?: string;
  authMode?: string;
  watermark?: string;
  joinKey?: string;
  transform?: string;
  requiredHeaders: string[];
  detectedHeaders: string[];
  validationStatus: "valid" | "warning" | "missing";
}

interface IntegrationConfiguratorProps {
  kpis: any[];
  trackedKpiIds: Set<string>;
  configs: Record<string, IntegrationConfig>;
  sources: Array<{ id: string; label: string; type: string; description: string }>;
  sourceSync: Record<string, "waiting" | "syncing" | "connected">;
  actualCountsBySource: Record<string, number>;
  isConnecting: boolean;
  onUpdateConfig: (kpiId: string, patch: Partial<IntegrationConfig>) => void;
  onConnectSources: () => void;
}

const POLL_SCHEDULES = ["Every 15 min", "Hourly", "Daily 06:00", "On file arrival"];

function sourceIcon(sourceId: string) {
  if (sourceId === "excel") return <FileSpreadsheet className="h-4 w-4" />;
  if (sourceId === "erp") return <ServerCog className="h-4 w-4" />;
  return <Database className="h-4 w-4" />;
}

function statusLabel(status: IntegrationConfig["validationStatus"]) {
  if (status === "valid") return "Header check passed";
  if (status === "warning") return "Mapping review needed";
  return "Headers missing";
}

function normalizeHeaderList(value: string) {
  return Array.from(
    new Set(
      value
        .split(/[,\n]/)
        .map((header) => header.trim())
        .filter(Boolean)
    )
  );
}

function validationStatus(requiredHeaders: string[], detectedHeaders: string[]): IntegrationConfig["validationStatus"] {
  if (requiredHeaders.length === 0) return "missing";
  const matched = requiredHeaders.filter((header) => detectedHeaders.includes(header)).length;
  if (matched === requiredHeaders.length) return "valid";
  if (matched > 0) return "warning";
  return "missing";
}

function uniqueList(values: string[]) {
  return Array.from(new Set(values.filter(Boolean)));
}

function fieldDescription(field: string) {
  const normalized = field.toLowerCase();
  if (normalized.includes("flight_leg")) return "Flight leg key";
  if (normalized.includes("catering_order")) return "Catering order key";
  if (normalized.includes("departure") || normalized.includes("std")) return "Scheduled departure timestamp";
  if (normalized.includes("delivery") || normalized.includes("scan")) return "Delivery confirmation timestamp";
  if (normalized.includes("station")) return "Airport station";
  if (normalized.includes("temp") || normalized.includes("probe")) return "Temperature reading";
  if (normalized.includes("incident") || normalized.includes("ticket") || normalized === "number") return "Incident or ticket identifier";
  if (normalized.includes("state") || normalized.includes("priority")) return "Remediation workflow state";
  if (normalized.includes("service_date")) return "Operational service date";
  if (normalized.includes("reviewer")) return "Reviewer or approver";
  if (normalized.includes("kpi")) return "Mapped KPI measurement";
  return "Source field";
}

const detailRows = [
  { key: "authMode", label: "Auth" },
  { key: "watermark", label: "Incremental key" },
  { key: "joinKey", label: "Join key" },
  { key: "transform", label: "Transform" },
] as const;

export default function IntegrationConfigurator({
  kpis,
  trackedKpiIds,
  configs,
  sources,
  sourceSync,
  actualCountsBySource,
  isConnecting,
  onUpdateConfig,
  onConnectSources,
}: IntegrationConfiguratorProps) {
  const trackedKpis = kpis.filter((kpi) => trackedKpiIds.has(kpi.kpi_id));
  const untrackedCount = Math.max(0, kpis.length - trackedKpis.length);
  const sourceOptions = sources.map((source) => ({ value: source.id, label: `${source.type} - ${source.label}` }));
  const streamGroups = sources
    .map((source) => {
      const mappedKpis = trackedKpis.filter((kpi) => configs[kpi.kpi_id]?.sourceId === source.id);
      const mappedConfigs = mappedKpis.map((kpi) => configs[kpi.kpi_id]).filter(Boolean);
      const primaryConfig = mappedConfigs[0];
      const requiredHeaders = uniqueList(mappedConfigs.flatMap((config) => config.requiredHeaders || []));
      const detectedHeaders = uniqueList(mappedConfigs.flatMap((config) => config.detectedHeaders || []));
      return {
        source,
        mappedKpis,
        mappedConfigs,
        primaryConfig,
        requiredHeaders,
        detectedHeaders,
        status: sourceSync[source.id] || "waiting",
      };
    })
    .filter((group) => group.mappedKpis.length > 0);

  const updateHeaderFields = (
    kpiId: string,
    config: IntegrationConfig,
    field: "requiredHeaders" | "detectedHeaders",
    value: string
  ) => {
    const headers = normalizeHeaderList(value);
    const nextRequired = field === "requiredHeaders" ? headers : config.requiredHeaders;
    const nextDetected = field === "detectedHeaders" ? headers : config.detectedHeaders;
    onUpdateConfig(kpiId, {
      [field]: headers,
      validationStatus: validationStatus(nextRequired, nextDetected),
    } as Partial<IntegrationConfig>);
  };

  const updateStreamConfig = (sourceId: string, patch: Partial<IntegrationConfig>) => {
    trackedKpis
      .filter((kpi) => configs[kpi.kpi_id]?.sourceId === sourceId)
      .forEach((kpi) => onUpdateConfig(kpi.kpi_id, patch));
  };

  const updateStreamHeaderFields = (
    sourceId: string,
    field: "requiredHeaders" | "detectedHeaders",
    value: string
  ) => {
    const headers = normalizeHeaderList(value);
    trackedKpis
      .filter((kpi) => configs[kpi.kpi_id]?.sourceId === sourceId)
      .forEach((kpi) => {
        const config = configs[kpi.kpi_id];
        if (!config) return;
        const nextRequired = field === "requiredHeaders" ? headers : config.requiredHeaders;
        const nextDetected = field === "detectedHeaders" ? headers : config.detectedHeaders;
        onUpdateConfig(kpi.kpi_id, {
          [field]: headers,
          validationStatus: validationStatus(nextRequired, nextDetected),
        } as Partial<IntegrationConfig>);
      });
  };

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wide text-[#0084C7]">Integration Setup</p>
            <h2 className="mt-1 text-base font-bold text-slate-900">Configure evidence fields for tracked KPIs</h2>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-500">
              Source setup is field based: one ERP call, REST payload, workbook, or ticket queue can expose fields that feed multiple tracked KPIs. Accepted-but-deferred KPIs stay out of mapping until tracking is switched on.
            </p>
          </div>
          <button
            onClick={onConnectSources}
            disabled={isConnecting || trackedKpis.length === 0}
            className="inline-flex items-center justify-center gap-2 rounded-md bg-[#0084C7] px-4 py-2 text-xs font-bold text-white shadow-sm transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Link2 className={`h-3.5 w-3.5 ${isConnecting ? "animate-pulse" : ""}`} />
            {isConnecting ? "Connecting..." : "Connect Configured Sources"}
          </button>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-4">
          {sources.map((source) => {
            const status = sourceSync[source.id] || "waiting";
            const configuredCount = trackedKpis.filter((kpi) => configs[kpi.kpi_id]?.sourceId === source.id).length;
            return (
              <div key={source.id} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2 text-slate-600">
                    <span className="rounded-md bg-white p-1.5 text-[#0084C7]">{sourceIcon(source.id)}</span>
                    <div>
                      <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">{source.type}</p>
                      <p className="text-sm font-bold text-slate-900">{source.label}</p>
                    </div>
                  </div>
                  <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold uppercase ${
                    status === "connected" ? "bg-emerald-100 text-emerald-700" :
                    status === "syncing" ? "bg-blue-100 text-blue-700" :
                    "bg-white text-slate-400"
                  }`}>
                    {status}
                  </span>
                </div>
                <p className="mt-3 text-[11px] leading-snug text-slate-500">{source.description}</p>
                <p className="mt-2 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                  {configuredCount} mapped KPIs · {(actualCountsBySource[source.id] || 0).toLocaleString()} records
                </p>
              </div>
            );
          })}
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Field-level Source Mapping</h3>
            <p className="mt-1 text-xs text-slate-400">
              {trackedKpis.length} tracked KPIs mapped across {streamGroups.length} evidence streams. {untrackedCount} extracted KPIs are approved or pending but not actively monitored yet.
            </p>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[11px] font-bold text-emerald-700">
            <ShieldCheck className="h-3.5 w-3.5" />
            Review approved
          </span>
        </div>

        {trackedKpis.length === 0 ? (
          <div className="p-10 text-center">
            <Settings2 className="mx-auto h-7 w-7 text-slate-300" />
            <p className="mt-3 text-sm font-semibold text-slate-700">No KPIs selected for tracking</p>
            <p className="mt-1 text-xs text-slate-400">Return to KPI Review and accept at least one KPI.</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {streamGroups.map((group) => {
              const config = group.primaryConfig;
              if (!config) return null;
              const aggregateStatus: IntegrationConfig["validationStatus"] = group.mappedConfigs.some((item) => item.validationStatus === "missing")
                ? "missing"
                : group.mappedConfigs.some((item) => item.validationStatus === "warning")
                  ? "warning"
                  : "valid";
              return (
                <div key={group.source.id} className="px-5 py-4">
                  <div className="rounded-lg border border-slate-200 bg-white p-4">
                    <div className="flex flex-col gap-3 border-b border-slate-100 pb-3 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0">
                        <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">{group.source.type} evidence stream</p>
                        <h4 className="mt-1 flex items-center gap-2 text-sm font-bold text-slate-900">
                          {sourceIcon(group.source.id)}
                          {group.source.label}
                        </h4>
                        <p className="mt-1 max-w-4xl text-xs leading-relaxed text-slate-500">{group.source.description}</p>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {group.mappedKpis.map((kpi) => (
                            <span key={kpi.kpi_id} className="rounded-full border border-blue-100 bg-blue-50 px-2 py-0.5 text-[10px] font-bold text-blue-700">
                              {kpi.kpi_id}
                            </span>
                          ))}
                        </div>
                      </div>
                      <span className={`w-fit rounded-full px-2.5 py-1 text-[9px] font-bold uppercase ${
                        aggregateStatus === "valid" ? "bg-emerald-100 text-emerald-700" :
                        aggregateStatus === "warning" ? "bg-amber-100 text-amber-700" :
                        "bg-red-100 text-red-700"
                      }`}>
                        {statusLabel(aggregateStatus)}
                      </span>
                    </div>

                    <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(300px,0.8fr)_minmax(360px,1fr)_minmax(520px,1.4fr)]">
                      <div className="grid gap-3 rounded-lg border border-slate-100 bg-slate-50 p-3">
                        <div className="rounded-md border border-slate-200 bg-white px-3 py-2">
                          <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Source contract</p>
                          <p className="mt-1 text-xs font-bold text-slate-800">{group.source.type} - {group.source.label}</p>
                          <p className="mt-1 text-[11px] leading-snug text-slate-500">
                            This stream can feed {group.mappedKpis.length} KPI{group.mappedKpis.length === 1 ? "" : "s"} from the same fetched dataset.
                          </p>
                        </div>

                        <label className="block">
                          <span className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Polling Schedule</span>
                          <select
                            value={config.pollSchedule}
                            onChange={(event) => updateStreamConfig(group.source.id, { pollSchedule: event.target.value })}
                            className="mt-1 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 focus:border-blue-300 focus:ring-blue-100"
                          >
                            {POLL_SCHEDULES.map((schedule) => (
                              <option key={schedule} value={schedule}>{schedule}</option>
                            ))}
                          </select>
                        </label>
                      </div>

                      <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                        <div className="flex items-start gap-2">
                          <span className="mt-0.5 rounded-md bg-white p-1.5 text-[#0084C7]">{sourceIcon(config.sourceId)}</span>
                          <div>
                            <p className="text-xs font-bold text-slate-800">{group.source.label}</p>
                            {config.interfaceName && (
                              <p className="mt-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400">{config.interfaceName}</p>
                            )}
                          </div>
                        </div>

                        {config.sourceId === "erp" && (
                          <label className="mt-3 block">
                            <span className="text-[10px] font-bold uppercase tracking-wide text-slate-400">ERP BAPI Call</span>
                            <input
                              value={config.bapiFunction || ""}
                              onChange={(event) => updateStreamConfig(group.source.id, { bapiFunction: event.target.value })}
                              className="mt-1 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-xs font-mono text-slate-700 focus:border-blue-300 focus:ring-blue-100"
                            />
                          </label>
                        )}

                        {config.sourceId === "rest" && (
                          <label className="mt-3 block">
                            <span className="text-[10px] font-bold uppercase tracking-wide text-slate-400">REST Endpoint</span>
                            <input
                              value={config.endpoint || ""}
                              onChange={(event) => updateStreamConfig(group.source.id, { endpoint: event.target.value })}
                              className="mt-1 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-xs font-mono text-slate-700 focus:border-blue-300 focus:ring-blue-100"
                            />
                          </label>
                        )}

                        {config.sourceId === "service" && (
                          <label className="mt-3 block">
                            <span className="text-[10px] font-bold uppercase tracking-wide text-slate-400">ServiceNow Table API Query</span>
                            <input
                              value={config.endpoint || ""}
                              onChange={(event) => updateStreamConfig(group.source.id, { endpoint: event.target.value })}
                              className="mt-1 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-xs font-mono text-slate-700 focus:border-blue-300 focus:ring-blue-100"
                            />
                          </label>
                        )}

                        {config.sourceId === "excel" && (
                          <label className="mt-3 block">
                            <span className="text-[10px] font-bold uppercase tracking-wide text-slate-400">CSV/XLSX Landing Pattern</span>
                            <input
                              value={config.filePattern || ""}
                              onChange={(event) => updateStreamConfig(group.source.id, { filePattern: event.target.value })}
                              className="mt-1 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-xs font-mono text-slate-700 focus:border-blue-300 focus:ring-blue-100"
                            />
                          </label>
                        )}

                        <div className="mt-3 grid gap-2">
                          {detailRows.map(({ key, label }) => {
                            const value = config[key];
                            if (!value) return null;
                            return (
                              <div key={key} className="rounded-md border border-slate-200 bg-white px-3 py-2">
                                <p className="text-[9px] font-bold uppercase tracking-wide text-slate-400">{label}</p>
                                <p className="mt-0.5 break-words text-[11px] font-semibold leading-snug text-slate-700">{value}</p>
                              </div>
                            );
                          })}
                        </div>
                      </div>

                      <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Header Field Mapping</p>
                          <button
                            type="button"
                            onClick={() => updateStreamConfig(group.source.id, {
                              validationStatus: validationStatus(group.requiredHeaders, group.detectedHeaders),
                            })}
                            className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-[10px] font-bold text-slate-600 hover:bg-slate-100"
                          >
                            <RefreshCw className="h-3 w-3" />
                            Validate Headers
                          </button>
                        </div>
                        <div className="mt-2 grid gap-2 md:grid-cols-2">
                          <label className="block">
                            <span className="text-[9px] font-bold uppercase tracking-wide text-slate-400">Required Headers</span>
                            <textarea
                              key={`${group.source.id}-required`}
                              rows={2}
                              defaultValue={group.requiredHeaders.join(", ")}
                              onBlur={(event) => updateStreamHeaderFields(group.source.id, "requiredHeaders", event.target.value)}
                              className="mt-1 w-full resize-none rounded-md border border-slate-200 bg-white px-3 py-2 font-mono text-[11px] text-slate-700 focus:border-blue-300 focus:ring-blue-100"
                            />
                          </label>
                          <label className="block">
                            <span className="text-[9px] font-bold uppercase tracking-wide text-slate-400">Detected Sample Headers</span>
                            <textarea
                              key={`${group.source.id}-detected`}
                              rows={2}
                              defaultValue={group.detectedHeaders.join(", ")}
                              onBlur={(event) => updateStreamHeaderFields(group.source.id, "detectedHeaders", event.target.value)}
                              className="mt-1 w-full resize-none rounded-md border border-slate-200 bg-white px-3 py-2 font-mono text-[11px] text-slate-700 focus:border-blue-300 focus:ring-blue-100"
                            />
                          </label>
                        </div>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {group.requiredHeaders.map((header) => {
                            const found = group.detectedHeaders.includes(header);
                            return (
                              <span key={header} className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
                                found ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-slate-200 bg-white text-slate-400"
                              }`}>
                                {found && <CheckCircle2 className="h-3 w-3" />}
                                {header}
                              </span>
                            );
                          })}
                        </div>
                      </div>
                    </div>

                    <div className="mt-4 rounded-lg border border-slate-100 bg-slate-50">
                      <div className="grid grid-cols-[minmax(220px,0.8fr)_minmax(220px,1fr)_minmax(320px,1.4fr)] gap-3 border-b border-slate-100 px-3 py-2">
                        <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Source field</p>
                        <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Meaning</p>
                        <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Used by</p>
                      </div>
                      <div className="divide-y divide-slate-100">
                        {group.requiredHeaders.map((header) => {
                          const metricOwners = group.mappedKpis.filter((kpi) => {
                            const metric = String(kpi.kpi_id || "").toLowerCase().replace(/[^a-z0-9]+/g, "_");
                            return header.includes(metric) || !header.includes("kpi_");
                          });
                          const usedBy = metricOwners.length ? metricOwners : group.mappedKpis;
                          return (
                            <div key={`${group.source.id}-${header}`} className="grid grid-cols-[minmax(220px,0.8fr)_minmax(220px,1fr)_minmax(320px,1.4fr)] gap-3 px-3 py-2">
                              <p className="font-mono text-[11px] font-semibold text-slate-700">{header}</p>
                              <p className="text-[11px] text-slate-500">{fieldDescription(header)}</p>
                              <div className="flex flex-wrap gap-1.5">
                                {usedBy.map((kpi) => (
                                  <span key={`${header}-${kpi.kpi_id}`} className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-600">
                                    {kpi.kpi_id}
                                  </span>
                                ))}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
