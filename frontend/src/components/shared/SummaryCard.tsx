"use client";

import React from "react";

interface SummaryCardProps {
  label: string;
  value: string | number;
  color: string;
  bg: string;
  border: string;
  icon: React.ReactNode;
}

export default function SummaryCard({ label, value, color, bg, border, icon }: SummaryCardProps) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 shadow-sm">
      <div className="flex items-center gap-2">
        <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md ${bg} ${border} border`}>
          {icon}
        </div>
        <div className="min-w-0">
          <p className={`text-lg font-bold leading-none ${color}`}>{value}</p>
          <p className="mt-0.5 truncate text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
        </div>
      </div>
    </div>
  );
}
