"use client";

import React from "react";
import { FileText, Activity, AlertTriangle, DollarSign } from "lucide-react";
import SummaryCard from "../shared/SummaryCard";

interface PortfolioViewProps {
  portfolioData: {
    total_contracts: number;
    total_kpis: number;
    total_breaches: number;
    total_exposure: number;
    supplier_scores: Array<{
      contract_id: string;
      total_kpis: number;
      health_score: number;
      exposure: number;
    }>;
  };
}

export default function PortfolioView({ portfolioData }: PortfolioViewProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <SummaryCard
          label="Total Contracts"
          value={portfolioData.total_contracts}
          color="text-[#0084C7]"
          bg="bg-blue-50"
          border="border-blue-200"
          icon={<FileText className="h-4 w-4 text-[#0084C7]" />}
        />
        <SummaryCard
          label="Total KPIs Tracked"
          value={portfolioData.total_kpis}
          color="text-indigo-700"
          bg="bg-indigo-50"
          border="border-indigo-200"
          icon={<Activity className="h-4 w-4 text-indigo-700" />}
        />
        <SummaryCard
          label="Active Breaches"
          value={portfolioData.total_breaches}
          color="text-red-700"
          bg="bg-red-50"
          border="border-red-200"
          icon={<AlertTriangle className="h-4 w-4 text-red-700" />}
        />
        <SummaryCard
          label="Total Exposure"
          value={`$${(portfolioData.total_exposure || 0).toLocaleString()}`}
          color="text-red-700"
          bg="bg-white"
          border="border-gray-200"
          icon={<DollarSign className="h-4 w-4 text-red-700" />}
        />
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
        <div className="px-5 py-4 border-b border-gray-100">
          <h3 className="text-sm font-semibold text-gray-800">Supplier Health Scoring</h3>
          <p className="text-xs text-gray-400 mt-0.5">Contract performance benchmarking across the portfolio</p>
        </div>
        <div className="divide-y divide-gray-100">
          {portfolioData.supplier_scores.map((s, i) => (
            <div key={i} className="flex items-center justify-between px-5 py-3.5 hover:bg-gray-50">
              <div>
                <p className="text-sm font-semibold text-gray-800">{s.contract_id}</p>
                <p className="text-[10px] text-gray-400">Score based on {s.total_kpis} tracked KPIs</p>
              </div>
              <div className="flex items-center gap-6">
                <div className="text-right">
                  <p className="text-[10px] font-bold text-gray-500 uppercase">Health Score</p>
                  <p
                    className={`text-lg font-black ${
                      (s.health_score || 0) > 90
                        ? "text-green-600"
                        : (s.health_score || 0) > 70
                        ? "text-amber-500"
                        : "text-red-600"
                    }`}
                  >
                    {(s.health_score || 0).toFixed(1)}/100
                  </p>
                </div>
                <div className="text-right min-w-[80px]">
                  <p className="text-[10px] font-bold text-gray-500 uppercase">Exposure</p>
                  <p className="text-sm font-bold text-red-600">${(s.exposure || 0).toLocaleString()}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
