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
  XAxis,
  YAxis,
  CartesianGrid,
  AreaChart,
  Area,
} from "recharts";
import {
  TYPE_COLORS,
  PARTY_COLORS,
  STATUS_BAR_COLORS,
  classifySeverity,
} from "@/lib/utils";

interface PerformanceCockpitProps {
  kpis: any[];
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

export default function PerformanceCockpit({
  kpis,
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
  const highestExposure = [...flags]
    .filter((f) => f.is_breach)
    .sort((a, b) => (b.penalty_amount || 0) - (a.penalty_amount || 0))[0];
  const nextAction = openBreaches[0];
  const nextActionKpi = kpis.find((k) => k.kpi_id === nextAction?.kpi_id);
  const totalExposure = flags.reduce((sum, f) => sum + (f.penalty_amount || 0), 0);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 rounded-lg border border-slate-200 bg-white p-3 shadow-sm md:grid-cols-4">
        <div className="border-b border-slate-100 pb-3 md:border-b-0 md:border-r md:pb-0 md:pr-3">
          <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">Exposure at Risk</p>
          <p className="mt-1 text-2xl font-bold tracking-normal text-red-600">${totalExposure.toLocaleString()}</p>
          <p className="mt-1 truncate text-[11px] text-slate-500">
            {highestExposure ? `${highestExposure.kpi_id} is the largest driver` : "No financial exposure recorded"}
          </p>
        </div>
        <div className="border-b border-slate-100 pb-3 md:border-b-0 md:border-r md:pb-0 md:pr-3">
          <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">Open Critical / High</p>
          <p className="mt-1 text-2xl font-bold tracking-normal text-slate-900">
            {sevCounts.CRITICAL + sevCounts.HIGH}
          </p>
          <p className="mt-1 text-[11px] text-slate-500">
            {sevCounts.CRITICAL} critical · {sevCounts.HIGH} high
          </p>
        </div>
        <div className="border-b border-slate-100 pb-3 md:border-b-0 md:border-r md:pb-0 md:pr-3">
          <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">Remediation Queue</p>
          <p className="mt-1 text-2xl font-bold tracking-normal text-amber-700">{openBreaches.length}</p>
          <p className="mt-1 truncate text-[11px] text-slate-500">
            {nextActionKpi?.party ? `${nextActionKpi.party} owns next action` : "No owner assigned"}
          </p>
        </div>
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">Next Best Action</p>
          <p className="mt-1 truncate text-sm font-bold text-slate-900">
            {nextAction ? nextActionKpi?.name || nextAction.kpi_id : "No open breach"}
          </p>
          <p className="mt-1 line-clamp-2 text-[11px] leading-snug text-slate-500">
            {nextAction?.remediation || nextActionKpi?.remediation || "Monitoring is currently clear."}
          </p>
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
            <p className="text-[10px] text-gray-400 mt-0.5">Contractual consequence by responsible party</p>
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

      {/* ── Row 2: Financial & Operational ──────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* 4. Actual vs Threshold Deviation */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
          <div className="px-5 py-3 border-b border-gray-100">
            <h3 className="text-sm font-semibold text-gray-800">Actual vs Threshold</h3>
            <p className="text-[10px] text-gray-400 mt-0.5">% deviation from target (negative = breach)</p>
          </div>
          <div className="px-2 py-3 h-[200px]">
            {actualVsThreshold.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={actualVsThreshold} layout="vertical" margin={{ left: 5, right: 20, top: 5, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                  <XAxis
                    type="number"
                    axisLine={false}
                    tickLine={false}
                    fontSize={9}
                    tick={{ fill: "#94a3b8" }}
                    tickFormatter={(v: number) => `${v > 0 ? "+" : ""}${v}%`}
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
                    formatter={(value: any) => [`${value > 0 ? "+" : ""}${value}%`, "Deviation"]}
                    contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px", padding: "8px" }}
                  />
                  <Bar dataKey="deviation" radius={[0, 4, 4, 0]} barSize={12}>
                    {actualVsThreshold.map((entry, i) => (
                      <Cell
                        key={i}
                        fill={
                          entry.isBreach
                            ? entry.severity === "CRITICAL"
                              ? "#ef4444"
                              : entry.severity === "HIGH"
                              ? "#f97316"
                              : "#f59e0b"
                            : "#22c55e"
                        }
                      />
                    ))}
                  </Bar>
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
            <p className="text-[10px] text-gray-400 mt-0.5">Financial exposure by KPI ($)</p>
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

        {/* 6. Breach Status Pipeline */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
          <div className="px-5 py-3 border-b border-gray-100">
            <h3 className="text-sm font-semibold text-gray-800">Breach Lifecycle</h3>
            <p className="text-[10px] text-gray-400 mt-0.5">Remediation pipeline status</p>
          </div>
          <div className="px-4 py-3 h-[200px] flex flex-col justify-center">
            {activeBreaches.length > 0 ? (
              <>
                <ResponsiveContainer width="100%" height={50}>
                  <BarChart
                    data={[breachStatusCounts.reduce((acc, s) => ({ ...acc, [s.name]: s.value }), {} as any)]}
                    layout="horizontal"
                    margin={{ left: 0, right: 0, top: 0, bottom: 0 }}
                  >
                    <XAxis type="number" hide domain={[0, activeBreaches.length || 1]} />
                    <YAxis type="category" hide dataKey={() => "status"} />
                    {breachStatusCounts.map((s) => (
                      <Bar
                        key={s.name}
                        dataKey={s.name}
                        stackId="status"
                        fill={STATUS_BAR_COLORS[s.name] || "#94a3b8"}
                        barSize={28}
                        radius={0}
                      />
                    ))}
                    <Tooltip contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px", padding: "8px" }} />
                  </BarChart>
                </ResponsiveContainer>
                <div className="grid grid-cols-2 gap-3 mt-4">
                  {breachStatusCounts.map((s) => (
                    <div key={s.name} className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded" style={{ backgroundColor: STATUS_BAR_COLORS[s.name] || "#94a3b8" }} />
                      <div>
                        <span className="text-xs font-semibold text-gray-700">{s.value}</span>
                        <span className="text-[10px] text-gray-400 ml-1">{s.name}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="flex items-center justify-center h-full text-xs text-gray-400">No active breaches</div>
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
              <h3 className="text-sm font-semibold text-gray-800">Penalty Accrual</h3>
              <p className="text-[10px] text-gray-400 mt-0.5">Cumulative financial exposure</p>
            </div>
            <span className="text-lg font-bold text-red-600">
              $
              {penaltyAccrualData.length > 0
                ? penaltyAccrualData[penaltyAccrualData.length - 1].cumulative.toLocaleString()
                : 0}
            </span>
          </div>
          <div className="px-2 py-3 h-[200px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={penaltyAccrualData.length ? penaltyAccrualData : [{ date: "—", cumulative: 0 }]}
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
                  formatter={(v: any) => [`$${v.toLocaleString()}`, "Cumulative"]}
                />
                <Area
                  type="step"
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
