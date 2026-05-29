"use client";

import React from "react";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  AreaChart,
  Area,
  Legend,
  ReferenceLine,
} from "recharts";
import {
  TYPE_COLORS,
  PARTY_COLORS,
  STATUS_BAR_COLORS,
  classifySeverity,
} from "@/lib/utils";

interface PerformanceCockpitProps {
  kpis: any[];
  actuals: any[];
  breaches: any[];
  activeBreaches: any[];
  sevCounts: { CRITICAL: number; HIGH: number; MEDIUM: number; LOW: number };
  kpiTypeCounts: any[];
  penaltyByParty: any[];
  actualVsThreshold: any[];
  flags: any[];
  breachStatusCounts: any[];
  penaltyAccrualData: any[];
  severityStatusMatrix: any;
}

const TREND_COLORS = ["#2563eb", "#16a34a", "#f59e0b", "#ef4444", "#7c3aed"];

function asNumber(value: unknown) {
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? numberValue : null;
}

function kpiThreshold(kpi: any) {
  const min = asNumber(kpi?.value_min ?? kpi?.threshold_value ?? kpi?.value);
  const max = asNumber(kpi?.value_max);
  return { min, max };
}

function shortKpiLabel(kpi: any, fallback: string) {
  return String(kpi?.name || fallback || "KPI")
    .replace(/^KPI-\d+:\s*/i, "")
    .replace(/\s+Target$/i, "")
    .replace(/\s+Performance$/i, "")
    .substring(0, 24);
}

function actualTimestamp(actual: any) {
  return actual?.timestamp || actual?.scheduled_departure || actual?.audit_date || actual?.date || actual?.month;
}

function monthBucket(timestamp: string) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return null;
  const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
  const label = date.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
  return { key, label };
}

function isActualBreach(kpi: any, value: number) {
  const { min, max } = kpiThreshold(kpi);
  if (min == null && max == null) return false;

  switch (kpi?.operator) {
    case ">=":
      return min != null ? value < min : false;
    case ">":
      return min != null ? value <= min : false;
    case "<=":
      return min != null ? value > min : false;
    case "<":
      return min != null ? value >= min : false;
    case "between":
      return (min != null && value < min) || (max != null && value > max);
    case "==":
    default:
      if (min == null) return false;
      return Math.abs(value - min) > 0.01;
  }
}

function targetAttainment(kpi: any, value: number) {
  const { min, max } = kpiThreshold(kpi);
  if (min == null && max == null) return null;

  let attainment: number | null = null;
  switch (kpi?.operator) {
    case ">=":
    case ">":
      attainment = min && min !== 0 ? (value / min) * 100 : null;
      break;
    case "<=":
    case "<":
      attainment = value !== 0 && min != null ? (min / value) * 100 : null;
      break;
    case "between":
      if (min != null && value < min && min !== 0) attainment = (value / min) * 100;
      else if (max != null && value > max && value !== 0) attainment = (max / value) * 100;
      else attainment = 100;
      break;
    case "==":
    default:
      if (min == null) return null;
      attainment = 100 - (Math.abs(value - min) / Math.max(Math.abs(min), 1)) * 100;
  }

  if (attainment == null || !Number.isFinite(attainment)) return null;
  return Math.max(60, Math.min(120, attainment));
}

export default function PerformanceCockpit({
  kpis,
  actuals,
  breaches,
  activeBreaches,
  sevCounts,
  kpiTypeCounts,
  penaltyByParty,
  actualVsThreshold,
  flags,
  breachStatusCounts,
  penaltyAccrualData,
  severityStatusMatrix,
}: PerformanceCockpitProps) {
  const openBreaches = activeBreaches.filter((b) => b.status !== "Resolved" && b.status !== "Waived");
  const nextAction = openBreaches[0];
  const nextActionKpi = kpis.find((k) => k.kpi_id === nextAction?.kpi_id);
  const kpisById = React.useMemo(() => new Map(kpis.map((kpi) => [kpi.kpi_id, kpi])), [kpis]);

  const thresholdComparisonData = React.useMemo(() => {
    const latestByKpi = new Map<string, any>();
    [...actuals]
      .filter((actual) => actual?.kpi_id && asNumber(actual.value) != null && actualTimestamp(actual))
      .sort((a, b) => new Date(actualTimestamp(a)).getTime() - new Date(actualTimestamp(b)).getTime())
      .forEach((actual) => latestByKpi.set(actual.kpi_id, actual));

    const preferred = ["KPI-001", "KPI-002", "KPI-003", "KPI-005", "KPI-006", "KPI-012", "KPI-015-A"];
    const rows = preferred
      .map((id) => {
        const actual = latestByKpi.get(id);
        const kpi = kpisById.get(id);
        const actualValue = asNumber(actual?.value);
        const { min } = kpiThreshold(kpi);
        if (!actual || !kpi || actualValue == null || min == null) return null;
        return {
          name: shortKpiLabel(kpi, id),
          actual: Number(actualValue.toFixed(2)),
          threshold: Number(min.toFixed(2)),
          breach: isActualBreach(kpi, actualValue),
          unit: actual.unit || kpi.unit || "",
        };
      })
      .filter(Boolean) as Array<{ name: string; actual: number; threshold: number; breach: boolean; unit: string }>;

    if (rows.length) return rows;

    return actualVsThreshold.slice(0, 7).map((row) => ({
      name: row.name,
      actual: Number(row.actual || 0),
      threshold: Number(row.threshold || 0),
      breach: row.isBreach,
      unit: row.unit || "",
    }));
  }, [actuals, actualVsThreshold, kpisById]);

  const oneYearTrendData = React.useMemo(() => {
    const trackedIds = ["KPI-001", "KPI-003", "KPI-006", "KPI-012", "KPI-015-A"];
    const labels = new Map<string, string>();
    const buckets = new Map<string, { period: string; values: Record<string, { sum: number; count: number }> }>();

    actuals.forEach((actual) => {
      if (!trackedIds.includes(actual?.kpi_id)) return;
      const value = asNumber(actual.value);
      const timestamp = actualTimestamp(actual);
      if (value == null || !timestamp) return;
      const kpi = kpisById.get(actual.kpi_id);
      const attainment = kpi ? targetAttainment(kpi, value) : null;
      if (attainment == null) return;
      const bucket = monthBucket(timestamp);
      if (!bucket) return;
      labels.set(actual.kpi_id, shortKpiLabel(kpisById.get(actual.kpi_id), actual.kpi_id));
      const month = buckets.get(bucket.key) || { period: bucket.label, values: {} };
      const metric = month.values[actual.kpi_id] || { sum: 0, count: 0 };
      month.values[actual.kpi_id] = { sum: metric.sum + attainment, count: metric.count + 1 };
      buckets.set(bucket.key, month);
    });

    const rows = [...buckets.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-12)
      .map(([, bucket]) => {
        const row: Record<string, string | number> = { period: bucket.period };
        trackedIds.forEach((id) => {
          const label = labels.get(id);
          const metric = bucket.values[id];
          if (label && metric?.count) row[label] = Number((metric.sum / metric.count).toFixed(2));
        });
        return row;
      });

    const trendLabels = trackedIds.map((id) => labels.get(id)).filter(Boolean) as string[];
    const values = rows.flatMap((row) => trendLabels.map((label) => asNumber(row[label])).filter((value) => value != null) as number[]);
    const minValue = values.length ? Math.min(...values, 100) : 90;
    const maxValue = values.length ? Math.max(...values, 100) : 105;
    const domain: [number, number] = [
      Math.max(60, Math.floor(minValue - 4)),
      Math.min(120, Math.ceil(maxValue + 4)),
    ];

    return { rows, labels: trendLabels, domain };
  }, [actuals, kpisById]);

  const monthlyBreachTrend = React.useMemo(() => {
    const buckets = new Map<string, { period: string; flagged: number; onTrack: number }>();

    actuals.forEach((actual) => {
      const value = asNumber(actual?.value);
      const timestamp = actualTimestamp(actual);
      const kpi = kpisById.get(actual?.kpi_id);
      if (value == null || !timestamp || !kpi) return;
      const bucket = monthBucket(timestamp);
      if (!bucket) return;
      const month = buckets.get(bucket.key) || { period: bucket.label, flagged: 0, onTrack: 0 };
      if (isActualBreach(kpi, value)) month.flagged += 1;
      else month.onTrack += 1;
      buckets.set(bucket.key, month);
    });

    return [...buckets.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-12)
      .map(([, value]) => value);
  }, [actuals, kpisById]);

  const exposureTrendData = React.useMemo(() => {
    const buckets = new Map<string, { period: string; exposureByKpi: Map<string, number> }>();

    actuals.forEach((actual) => {
      const value = asNumber(actual?.value);
      const timestamp = actualTimestamp(actual);
      const kpi = kpisById.get(actual?.kpi_id);
      if (value == null || !timestamp || !kpi || !isActualBreach(kpi, value)) return;
      const bucket = monthBucket(timestamp);
      if (!bucket) return;
      const month = buckets.get(bucket.key) || { period: bucket.label, exposureByKpi: new Map<string, number>() };
      const exposure = asNumber(kpi.consequence_value) || 0;
      if (exposure > 0) {
        month.exposureByKpi.set(actual.kpi_id, Math.max(month.exposureByKpi.get(actual.kpi_id) || 0, exposure));
      }
      buckets.set(bucket.key, month);
    });

    let cumulative = 0;
    const derived = [...buckets.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-12)
      .map(([, month]) => {
        const exposure = [...month.exposureByKpi.values()].reduce((sum, amount) => sum + amount, 0);
        cumulative += exposure;
        return { date: month.period, exposure, cumulative };
      });

    return derived.length > 1 ? derived : penaltyAccrualData;
  }, [actuals, kpisById, penaltyAccrualData]);

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-blue-100 bg-white px-4 py-3 shadow-sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-wide text-blue-600">Next Best Action</p>
            <p className="mt-1 truncate text-sm font-bold text-slate-900">
              {nextAction ? nextActionKpi?.name || nextAction.kpi_id : "No open breach"}
            </p>
            <p className="mt-1 line-clamp-2 text-[11px] leading-snug text-slate-500">
              {nextAction?.remediation || nextActionKpi?.remediation || "Monitoring is currently clear."}
            </p>
          </div>
          {nextAction && (
            <div className="flex shrink-0 flex-wrap gap-2">
              {nextActionKpi?.party && (
                <span className="rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-[10px] font-semibold text-blue-700">
                  Owner: {nextActionKpi.party}
                </span>
              )}
              {(nextAction.sla || nextActionKpi?.remediation_sla) && (
                <span className="rounded-full border border-amber-100 bg-amber-50 px-3 py-1 text-[10px] font-semibold text-amber-700">
                  SLA: {nextAction.sla || nextActionKpi?.remediation_sla}
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Row 1: Overview ─────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* 1. Severity Distribution Donut */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
          <div className="px-5 py-3 border-b border-gray-100 flex justify-between items-center">
            <div>
              <h3 className="text-sm font-semibold text-gray-800">Flag Distribution</h3>
              <p className="text-[10px] text-gray-400 mt-0.5">Severity breakdown across monitored KPIs</p>
            </div>
            <span className="text-lg font-bold text-gray-700">{activeBreaches.length} Flags</span>
          </div>
          <div className="px-4 py-3 h-[200px] flex flex-col items-center">
            <ResponsiveContainer width="100%" height={120}>
              <PieChart>
                <Pie
                  data={[
                    { name: "Critical", value: sevCounts.CRITICAL, color: "#ef4444" },
                    { name: "High", value: sevCounts.HIGH, color: "#f97316" },
                    { name: "Medium", value: sevCounts.MEDIUM, color: "#f59e0b" },
                    { name: "OK", value: Math.max(0, kpis.length - activeBreaches.length), color: "#22c55e" },
                  ].filter((d) => d.value > 0)}
                  cx="50%"
                  cy="50%"
                  innerRadius={35}
                  outerRadius={55}
                  paddingAngle={4}
                  dataKey="value"
                >
                  {[
                    { color: "#ef4444" },
                    { color: "#f97316" },
                    { color: "#f59e0b" },
                    { color: "#22c55e" },
                  ]
                    .filter(
                      (_, i) =>
                        [
                          sevCounts.CRITICAL,
                          sevCounts.HIGH,
                          sevCounts.MEDIUM,
                          Math.max(0, kpis.length - activeBreaches.length),
                        ][i] > 0
                    )
                    .map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                </Pie>
                <Tooltip
                  formatter={(value: any) => [value, "Flags"]}
                  contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "12px" }}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="grid grid-cols-2 gap-x-5 gap-y-1 w-full px-2 mt-2">
              {[
                { name: "Critical", value: sevCounts.CRITICAL, color: "#ef4444" },
                { name: "High", value: sevCounts.HIGH, color: "#f97316" },
                { name: "Medium", value: sevCounts.MEDIUM, color: "#f59e0b" },
                { name: "OK", value: Math.max(0, kpis.length - activeBreaches.length), color: "#22c55e" },
              ].map((item) => (
                <div key={item.name} className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: item.color }} />
                  <span className="text-[10px] text-gray-500 font-medium">
                    {item.name} ({item.value})
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 2. KPI Coverage by Type */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
          <div className="px-5 py-3 border-b border-gray-100">
            <h3 className="text-sm font-semibold text-gray-800">KPI Coverage by Type</h3>
            <p className="text-[10px] text-gray-400 mt-0.5">Distribution of monitoring dimensions</p>
          </div>
          <div className="px-2 py-3 h-[200px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={kpiTypeCounts.length ? kpiTypeCounts : [{ name: "No KPIs", value: 0 }]}
                layout="vertical"
                margin={{ left: 5, right: 20, top: 5, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                <XAxis type="number" axisLine={false} tickLine={false} fontSize={9} tick={{ fill: "#94a3b8" }} />
                <YAxis
                  type="category"
                  dataKey="name"
                  axisLine={false}
                  tickLine={false}
                  fontSize={10}
                  tick={{ fill: "#64748b" }}
                  width={65}
                />
                <Tooltip contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px", padding: "8px" }} />
                <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={14}>
                  {kpiTypeCounts.map((entry, i) => (
                    <Cell key={i} fill={TYPE_COLORS[entry.name] || "#94a3b8"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 3. Penalty Exposure by Party */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
          <div className="px-5 py-3 border-b border-gray-100">
            <h3 className="text-sm font-semibold text-gray-800">Penalty Exposure by Party</h3>
            <p className="text-[10px] text-gray-400 mt-0.5">Current open exposure by responsible party</p>
          </div>
          <div className="px-4 py-3 h-[200px] flex flex-col items-center">
            {penaltyByParty.length > 0 ? (
              <>
                <ResponsiveContainer width="100%" height={120}>
                  <PieChart>
                    <Pie data={penaltyByParty} cx="50%" cy="50%" innerRadius={35} outerRadius={55} paddingAngle={4} dataKey="value">
                      {penaltyByParty.map((_, i) => (
                        <Cell key={i} fill={PARTY_COLORS[i % PARTY_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value: any) => [`$${value.toLocaleString()}`, "Exposure"]}
                      contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "12px" }}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 w-full px-2 mt-2">
                  {penaltyByParty.map((p, i) => (
                    <div key={p.name} className="flex items-center gap-1.5">
                      <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: PARTY_COLORS[i % PARTY_COLORS.length] }} />
                      <span className="text-[10px] text-gray-500 font-medium truncate">{p.name}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="flex items-center justify-center h-full text-xs text-gray-400">No penalty data extracted</div>
            )}
          </div>
        </div>
      </div>

      {oneYearTrendData.rows.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
          <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-gray-800">One-Year KPI Target Attainment</h3>
              <p className="text-[10px] text-gray-400 mt-0.5">Monthly actuals normalized against contract targets. 100% is the required level.</p>
            </div>
            <span className="rounded-full border border-blue-100 bg-blue-50 px-2.5 py-1 text-[11px] font-semibold text-[#0084C7]">
              {actuals.length.toLocaleString()} actuals
            </span>
          </div>
          <div className="px-3 py-3 h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={oneYearTrendData.rows} margin={{ left: -8, right: 18, top: 34, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eef2f7" />
                <XAxis dataKey="period" axisLine={false} tickLine={false} fontSize={10} tick={{ fill: "#94a3b8" }} />
                <YAxis
                  domain={oneYearTrendData.domain}
                  axisLine={false}
                  tickLine={false}
                  fontSize={10}
                  tick={{ fill: "#94a3b8" }}
                  tickFormatter={(v: number) => `${v}%`}
                />
                <ReferenceLine
                  y={100}
                  stroke="#0f172a"
                  strokeDasharray="4 4"
                  strokeOpacity={0.45}
                  label={{ value: "Target", position: "insideTopRight", fill: "#64748b", fontSize: 10 }}
                />
                <Tooltip
                  formatter={(value: any) => [`${Number(value).toFixed(1)}%`, "Target attainment"]}
                  contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px", padding: "8px" }}
                />
                <Legend verticalAlign="top" align="center" wrapperStyle={{ fontSize: 11, paddingBottom: 8 }} />
                {oneYearTrendData.labels.map((label, index) => (
                  <Line
                    key={label}
                    type="monotone"
                    dataKey={label}
                    stroke={TREND_COLORS[index % TREND_COLORS.length]}
                    strokeWidth={2.5}
                    dot={false}
                    activeDot={{ r: 4 }}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ── Row 2: Financial & Operational ──────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* 4. Actual vs Threshold */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
          <div className="px-5 py-3 border-b border-gray-100">
            <h3 className="text-sm font-semibold text-gray-800">Actual vs Threshold</h3>
            <p className="text-[10px] text-gray-400 mt-0.5">Latest actuals compared with contracted targets</p>
          </div>
          <div className="px-2 py-3 h-[200px]">
            {thresholdComparisonData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={thresholdComparisonData} layout="vertical" margin={{ left: 5, right: 20, top: 5, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                  <XAxis
                    type="number"
                    domain={[0, 110]}
                    axisLine={false}
                    tickLine={false}
                    fontSize={9}
                    tick={{ fill: "#94a3b8" }}
                    tickFormatter={(v: number) => `${v}%`}
                  />
                  <YAxis
                    type="category"
                    dataKey="name"
                    axisLine={false}
                    tickLine={false}
                    fontSize={9}
                    tick={{ fill: "#64748b" }}
                    width={100}
                  />
                  <Legend wrapperStyle={{ fontSize: 10 }} />
                  <Tooltip
                    formatter={(value: any, name: any, item: any) => [
                      `${Number(value).toLocaleString()}${item?.payload?.unit ? ` ${item.payload.unit}` : ""}`,
                      name === "actual" ? "Actual" : "Target",
                    ]}
                    contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px", padding: "8px" }}
                  />
                  <Bar dataKey="actual" name="Actual" fill="#f97316" radius={[0, 4, 4, 0]} barSize={8}>
                    {thresholdComparisonData.map((entry, i) => (
                      <Cell key={i} fill={entry.breach ? "#f97316" : "#22c55e"} />
                    ))}
                  </Bar>
                  <Bar dataKey="threshold" name="Target" fill="#cbd5e1" radius={[0, 4, 4, 0]} barSize={8} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-xs text-gray-400">
                No evaluations yet — upload actuals to begin
              </div>
            )}
          </div>
        </div>

        {/* 5. Penalty Impact by KPI */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
          <div className="px-5 py-3 border-b border-gray-100">
            <h3 className="text-sm font-semibold text-gray-800">Penalty Impact by KPI</h3>
            <p className="text-[10px] text-gray-400 mt-0.5">Current open exposure by KPI ($)</p>
          </div>
          <div className="px-2 py-3 h-[200px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={flags
                  .filter((f) => f.is_breach && f.penalty_amount > 0)
                  .map((f) => ({
                    name: (f.kpi?.name || f.kpi_id || "").split(":")[0].trim().substring(0, 18),
                    amount: f.penalty_amount,
                  }))}
                layout="vertical"
                margin={{ left: 10, right: 20, top: 0, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                <XAxis
                  type="number"
                  axisLine={false}
                  tickLine={false}
                  fontSize={9}
                  tick={{ fill: "#94a3b8" }}
                  tickFormatter={(v: number) => `$${v > 1000 ? v / 1000 + "k" : v}`}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  axisLine={false}
                  tickLine={false}
                  fontSize={9}
                  tick={{ fill: "#64748b" }}
                  width={100}
                />
                <Tooltip
                  formatter={(value: any) => [`$${value.toLocaleString()}`, "Penalty"]}
                  contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px", padding: "8px" }}
                />
                <Bar dataKey="amount" radius={[0, 4, 4, 0]} barSize={12}>
                  {flags
                    .filter((f) => f.is_breach && f.penalty_amount > 0)
                    .map((f, i) => (
                      <Cell
                        key={i}
                        fill={f.severity === "CRITICAL" ? "#ef4444" : f.severity === "HIGH" ? "#f97316" : "#f59e0b"}
                      />
                    ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 6. Breach Trend */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
          <div className="px-5 py-3 border-b border-gray-100">
            <h3 className="text-sm font-semibold text-gray-800">Breach Trend</h3>
            <p className="text-[10px] text-gray-400 mt-0.5">Monthly flagged KPI signals from actuals</p>
          </div>
          <div className="px-2 py-3 h-[200px]">
            {monthlyBreachTrend.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={monthlyBreachTrend} margin={{ left: -8, right: 12, top: 8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="period" axisLine={false} tickLine={false} fontSize={9} tick={{ fill: "#94a3b8" }} />
                  <YAxis axisLine={false} tickLine={false} fontSize={9} tick={{ fill: "#94a3b8" }} />
                  <Tooltip
                    contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px", padding: "8px" }}
                    formatter={(value: any, name: any) => [value, name === "flagged" ? "Flagged" : "On Track"]}
                  />
                  <Legend wrapperStyle={{ fontSize: 10 }} />
                  <Bar dataKey="flagged" name="Flagged" stackId="a" fill="#f97316" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="onTrack" name="On Track" stackId="a" fill="#22c55e" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-xs text-gray-400">No actuals loaded</div>
            )}
          </div>
        </div>
      </div>

      {/* ── Row 3: Detail Analytics ─────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* 7. Penalty Accumulation Timeline */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
          <div className="px-5 py-3 border-b border-gray-100 flex justify-between items-center">
            <div>
              <h3 className="text-sm font-semibold text-gray-800">Rolling 12-Month Exposure Projection</h3>
              <p className="text-[10px] text-gray-400 mt-0.5">Projected accrual from recurring actual breaches. Current open exposure is shown in the top card.</p>
            </div>
            <span className="text-lg font-bold text-red-600">
              $
              {exposureTrendData.length > 0
                ? exposureTrendData[exposureTrendData.length - 1].cumulative.toLocaleString()
                : 0}
            </span>
          </div>
          <div className="px-2 py-3 h-[200px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={exposureTrendData.length ? exposureTrendData : [{ date: "—", cumulative: 0 }]}
                margin={{ left: -5, right: 10, top: 10, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="colorPenAccrual" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="date" axisLine={false} tickLine={false} fontSize={9} tick={{ fill: "#94a3b8" }} />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  fontSize={9}
                  tick={{ fill: "#94a3b8" }}
                  tickFormatter={(v: number) => `$${v > 1000 ? (v / 1000).toFixed(0) + "k" : v}`}
                />
                <Tooltip
                  contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px", padding: "8px" }}
                  formatter={(v: any, name: any) => [
                    `$${Number(v).toLocaleString()}`,
                    name === "exposure" ? "Monthly Projected Accrual" : "Rolling 12-Month Projection",
                  ]}
                />
                <Area
                  type="monotone"
                  dataKey="exposure"
                  stroke="#f97316"
                  strokeWidth={1.5}
                  fillOpacity={0.18}
                  fill="#f97316"
                />
                <Area
                  type="monotone"
                  dataKey="cumulative"
                  stroke="#ef4444"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorPenAccrual)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 8. Severity × Status Heatmap */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
          <div className="px-5 py-3 border-b border-gray-100">
            <h3 className="text-sm font-semibold text-gray-800">Severity × Status Matrix</h3>
            <p className="text-[10px] text-gray-400 mt-0.5">Cross-tabulated breach heatmap</p>
          </div>
          <div className="px-4 py-4 h-[200px] flex flex-col justify-center">
            <div className="overflow-auto">
              <table className="w-full text-[10px]">
                <thead>
                  <tr>
                    <th className="text-left text-gray-500 font-medium pb-2 pr-2"></th>
                    {["Open", "In Progress", "Resolved", "Waived"].map((s) => (
                      <th key={s} className="text-center text-gray-500 font-medium pb-2 px-1">
                        {s}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const).map((sev) => {
                    const sevColor =
                      sev === "CRITICAL"
                        ? "#ef4444"
                        : sev === "HIGH"
                        ? "#f97316"
                        : sev === "MEDIUM"
                        ? "#f59e0b"
                        : "#94a3b8";
                    return (
                      <tr key={sev}>
                        <td className="pr-2 py-1.5 font-semibold" style={{ color: sevColor }}>
                          {sev}
                        </td>
                        {["Open", "In Progress", "Resolved", "Waived"].map((st) => {
                          const count = severityStatusMatrix[sev]?.[st] || 0;
                          const opacity = count === 0 ? 0.05 : Math.min(0.15 + count * 0.2, 0.9);
                          return (
                            <td key={st} className="text-center py-1.5 px-1">
                              <div
                                className="rounded-md py-1.5 font-bold text-xs"
                                style={{
                                  backgroundColor:
                                    count > 0
                                      ? `${sevColor}${Math.round(opacity * 255)
                                          .toString(16)
                                          .padStart(2, "0")}`
                                      : "#f8fafc",
                                  color: count > 0 ? sevColor : "#cbd5e1",
                                }}
                              >
                                {count}
                              </div>
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* 9. Remediation SLA Status */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
          <div className="px-5 py-3 border-b border-gray-100">
            <h3 className="text-sm font-semibold text-gray-800">Remediation SLA Status</h3>
            <p className="text-[10px] text-gray-400 mt-0.5">Open breaches with SLA deadlines</p>
          </div>
          <div className="px-4 py-3 h-[200px] overflow-y-auto">
            {activeBreaches.filter((b) => b.status !== "Resolved" && b.status !== "Waived").length > 0 ? (
              <div className="space-y-2">
                {activeBreaches
                  .filter((b) => b.status !== "Resolved" && b.status !== "Waived")
                  .slice(0, 6)
                  .map((b, i) => {
                    const kpi = kpis.find((k) => k.kpi_id === b.kpi_id);
                    const sla = b.remediation_sla || kpi?.remediation_sla || "—";
                    const sev = classifySeverity(b);
                    const sevColor =
                      sev === "CRITICAL"
                        ? "#ef4444"
                        : sev === "HIGH"
                        ? "#f97316"
                        : sev === "MEDIUM"
                        ? "#f59e0b"
                        : "#94a3b8";
                    return (
                      <div key={i} className="flex items-start gap-2 p-2 rounded-lg border border-gray-100 bg-gray-50/50">
                        <div
                          className="w-1.5 h-full min-h-[32px] rounded-full shrink-0 mt-0.5"
                          style={{ backgroundColor: sevColor }}
                        />
                        <div className="flex-1 min-w-0">
                          <p className="text-[11px] font-medium text-gray-700 truncate">{kpi?.name || b.kpi_id}</p>
                          <div className="flex items-center gap-3 mt-0.5">
                            <span className="text-[10px] text-gray-400">
                              SLA: <strong className="text-gray-600">{sla}</strong>
                            </span>
                            <span
                              className="text-[10px] px-1.5 py-0.5 rounded font-medium"
                              style={{ backgroundColor: `${sevColor}15`, color: sevColor }}
                            >
                              {sev}
                            </span>
                          </div>
                        </div>
                        <span className="text-[10px] text-gray-400 shrink-0">
                          ${(b.penalty_amount || 0).toLocaleString()}
                        </span>
                      </div>
                    );
                  })}
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-xs text-gray-400">
                No open remediation items
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
