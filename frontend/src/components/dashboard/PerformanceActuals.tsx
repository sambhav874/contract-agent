"use client";

import React from "react";
import { Activity } from "lucide-react";

interface PerformanceActualsProps {
  actuals: any[];
}

export default function PerformanceActuals({ actuals }: PerformanceActualsProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-gray-800">Performance Logs (Actuals)</h3>
          <p className="text-xs text-gray-400 mt-0.5">Ingested raw operational data used for compliance evaluation</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 text-[11px] text-[#0084C7] bg-blue-50 border border-blue-100 px-2.5 py-1 rounded-full">
            <Activity className="h-3 w-3" /> {actuals.length} Data Points
          </span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-100">
              <th className="px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-gray-500">Timestamp</th>
              <th className="px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-gray-500">KPI ID</th>
              <th className="px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-gray-500">Actual Value</th>
              <th className="px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-gray-500">Source</th>
              <th className="px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-gray-500">Context / Attributes</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {actuals.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-12 text-center text-sm text-gray-400 italic">
                  No actuals data ingested for this contract.
                </td>
              </tr>
            ) : (
              actuals.map((a, i) => {
                const timestamp = a.timestamp || a.scheduled_departure || a.audit_date || a.date || a.month || "—";
                const dateStr = timestamp !== "—" ? new Date(timestamp).toLocaleString() : "—";

                // Extract non-standard fields for the "Context" column
                const standardKeys = [
                  "timestamp",
                  "kpi_id",
                  "value",
                  "unit",
                  "source",
                  "scheduled_departure",
                  "audit_date",
                  "date",
                  "month",
                  "_id",
                  "contract_id",
                ];
                const contextData = Object.entries(a)
                  .filter(([key]) => !standardKeys.includes(key))
                  .reduce((obj, [key, val]) => ({ ...obj, [key]: val }), {});

                return (
                  <tr key={i} className="hover:bg-gray-50 transition-colors">
                    <td className="px-5 py-3 text-xs text-gray-600 font-mono">{dateStr}</td>
                    <td className="px-5 py-3">
                      <span className="text-[11px] font-bold text-[#0084C7] bg-blue-50 px-2 py-0.5 rounded border border-blue-100 uppercase tracking-tighter">
                        {a.kpi_id || "—"}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <p className="text-sm font-bold text-gray-800">
                        {a.value} <span className="text-[10px] font-normal text-gray-400 uppercase">{a.unit}</span>
                      </p>
                    </td>
                    <td className="px-5 py-3 text-xs text-gray-500 italic">{a.source || "—"}</td>
                    <td className="px-5 py-3">
                      <div className="flex flex-wrap gap-1.5">
                        {Object.entries(contextData).map(([key, val]) => (
                          <span
                            key={key}
                            className="text-[10px] bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded flex items-center gap-1"
                          >
                            <span className="font-bold opacity-60 capitalize">{key.replace(/_/g, " ")}:</span>
                            <span>{String(val)}</span>
                          </span>
                        ))}
                        {Object.keys(contextData).length === 0 && <span className="text-[10px] text-gray-300">No extra metadata</span>}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
