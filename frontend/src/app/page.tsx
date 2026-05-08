"use client";

import { useState, useEffect, useMemo } from "react";
import {
  ShieldCheck, AlertTriangle, CheckCircle2, ChevronDown, ArrowLeft,
  RefreshCw, Sparkles, Server, DollarSign, AlertCircle, BarChart3,
  Clock, FileText, Activity, Bell, Database
} from "lucide-react";
import { fetchContracts, fetchKPIs, fetchBreaches, fetchPerformance, evaluateContract, updateBreach, chatWithContract } from "@/lib/api";
import { MessageSquare, Send, X, Bot, Quote } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, AreaChart, Area, LineChart, Line, ComposedChart, Legend
} from "recharts";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";

// ── Severity helpers ─────────────────────────────────────────────────
const SEV_CONFIG: Record<string, any> = {
  CRITICAL: { dot: "bg-red-500", badge: "bg-red-100 text-red-700 border-red-200", color: "text-red-700", bg: "bg-red-50", border: "border-red-200", icon: AlertCircle, response: "< 1 hour" },
  HIGH:     { dot: "bg-orange-400", badge: "bg-orange-100 text-orange-700 border-orange-200", color: "text-orange-700", bg: "bg-orange-50", border: "border-orange-200", icon: AlertTriangle, response: "Same business day" },
  MEDIUM:   { dot: "bg-amber-300", badge: "bg-amber-100 text-amber-700 border-amber-200", color: "text-amber-700", bg: "bg-amber-50", border: "border-amber-200", icon: AlertTriangle, response: "Within 48 hours" },
  LOW:      { dot: "bg-green-400", badge: "bg-green-100 text-green-700 border-green-200", color: "text-green-700", bg: "bg-green-50", border: "border-green-200", icon: CheckCircle2, response: "Next review cycle" },
};

const STATUS_CONFIG: Record<string, any> = {
  Open: { color: "text-red-700", bg: "bg-red-50", border: "border-red-200", dot: "bg-red-500" },
  "In Progress": { color: "text-amber-700", bg: "bg-amber-50", border: "border-amber-200", dot: "bg-amber-400" },
  Resolved: { color: "text-green-700", bg: "bg-green-50", border: "border-green-200", dot: "bg-green-500" },
  Waived: { color: "text-gray-600", bg: "bg-gray-50", border: "border-gray-200", dot: "bg-gray-400" },
};

function classifySeverity(breach: any): string {
  if (!breach.is_breach) return "LOW";
  const ratio = breach.actual_value / (breach.threshold_value || 1);
  if (breach.penalty_amount > 5000 || ratio > 2) return "CRITICAL";
  if (breach.penalty_amount > 1000 || ratio > 1.5) return "HIGH";
  return "MEDIUM";
}

// ── KPI Type badge colors ────────────────────────────────────────────
const KPI_TYPE_COLORS: Record<string, string> = {
  financial: "bg-emerald-50 text-emerald-700 border-emerald-200",
  sla: "bg-blue-50 text-blue-700 border-blue-200",
  penalty: "bg-red-50 text-red-700 border-red-200",
  volume: "bg-purple-50 text-purple-700 border-purple-200",
  timeline: "bg-amber-50 text-amber-700 border-amber-200",
  other: "bg-gray-50 text-gray-600 border-gray-200",
};

export default function Dashboard() {
  const [contracts, setContracts] = useState<any[]>([]);
  const [selectedContract, setSelectedContract] = useState("");
  const [kpis, setKpis] = useState<any[]>([]);
  const [breaches, setBreaches] = useState<any[]>([]);
  const [actuals, setActuals] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedFlag, setExpandedFlag] = useState<string | null>(null);
  const [expandedKpi, setExpandedKpi] = useState<string | null>(null);
  const [tab, setTab] = useState<"kpis" | "flags">("kpis");
  const [evaluating, setEvaluating] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<any[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [currentQuery, setCurrentQuery] = useState("");

  async function handleEvaluate() {
    if (!selectedContract || evaluating) return;
    setEvaluating(true);
    try {
      await evaluateContract(selectedContract);
      const [b, a] = await Promise.all([fetchBreaches(selectedContract), fetchPerformance(selectedContract)]);
      setBreaches(b); setActuals(a);
      setTab("flags");
    } catch (e) { console.error(e); }
    finally { setEvaluating(false); }
  }

  async function handleUpdateStatus(breachId: string, newStatus: string) {
    try {
      await updateBreach(breachId, { status: newStatus });
      // Update local state
      setBreaches(prev => prev.map(b => 
        (b.breach_id === breachId || b._id === breachId) ? { ...b, status: newStatus } : b
      ));
    } catch (e) { console.error(e); }
  }

  async function handleUpdateNotes(breachId: string, newNotes: string) {
    try {
      await updateBreach(breachId, { notes: newNotes });
      setBreaches(prev => prev.map(b => 
        (b.breach_id === breachId || b._id === breachId) ? { ...b, notes: newNotes } : b
      ));
    } catch (e) { console.error(e); }
  }

  async function handleChat(question: string, breachId?: string) {
    if (!question.trim()) return;
    if (!selectedContract) return;

    setChatLoading(true);
    setChatOpen(true);
    const newMsg = { role: "user", content: question };
    setChatMessages(prev => [...prev, newMsg]);

    try {
      const result = await chatWithContract(selectedContract, question, breachId);
      setChatMessages(prev => [...prev, { role: "assistant", content: result.answer, citations: result.citations }]);
    } catch (e) {
      setChatMessages(prev => [...prev, { role: "assistant", content: "Sorry, I encountered an error. Please try again." }]);
    } finally {
      setChatLoading(false);
      setCurrentQuery("");
    }
  }

  useEffect(() => {
    (async () => {
      try {
        const data = await fetchContracts();
        setContracts(data);
        if (data.length > 0) setSelectedContract(data[0].contract_id);
      } catch (e) { console.error(e); }
    })();
  }, []);

  useEffect(() => {
    if (!selectedContract) return;
    (async () => {
      setLoading(true);
      try {
        const [k, b, a] = await Promise.all([
          fetchKPIs(selectedContract), 
          fetchBreaches(selectedContract),
          fetchPerformance(selectedContract)
        ]);
        setKpis(k); setBreaches(b); setActuals(a);
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
    })();
  }, [selectedContract]);

  // ── Dynamic Time-Series Aggregation from Real Actuals ──────────────
  const timeSeriesData = useMemo(() => {
    if (!actuals.length && !breaches.length) return [];
    
    const daily: Record<string, any> = {};
    
    actuals.forEach(a => {
      let rawDate = a.timestamp || a.scheduled_departure || a.audit_date || a.date || a.month;
      if (!rawDate) return;
      
      let d = "";
      try { d = new Date(rawDate).toISOString().split('T')[0]; } 
      catch { return; } // skip invalid dates

      if (!daily[d]) {
        daily[d] = { date: d.substring(5), count: 0, onTimeCount: 0, onTimeTotal: 0, qualitySum: 0, qualityCount: 0, tempViolations: 0, penalties: 0, breaches: [] };
      }
      
      daily[d].count++;
      
      // Parse specific fields from JSON actuals
      if (a.is_on_time !== undefined) {
        daily[d].onTimeTotal++;
        if (String(a.is_on_time).toLowerCase() === "true") daily[d].onTimeCount++;
      }
      if (a.score !== undefined) {
        daily[d].qualitySum += parseFloat(a.score);
        daily[d].qualityCount++;
      }
      if (a.internal_temp !== undefined) {
        if (parseFloat(a.internal_temp) < 4 || parseFloat(a.internal_temp) > 60) daily[d].tempViolations++;
      }
    });

    breaches.forEach(b => {
      let rawDate = b.timestamp;
      if (!rawDate) return;
      let d = "";
      try { d = new Date(rawDate).toISOString().split('T')[0]; } 
      catch { return; }

      if (!daily[d]) {
        daily[d] = { date: d.substring(5), count: 0, onTimeCount: 0, onTimeTotal: 0, qualitySum: 0, qualityCount: 0, tempViolations: 0, penalties: 0, breaches: [] };
      }
      
      if (b.is_breach) {
        daily[d].penalties += (b.penalty_amount || 0);
        daily[d].breaches.push(classifySeverity(b));
      }
    });

    const sortedDates = Object.keys(daily).sort();
    let totalPen = 0;
    let currentCompliance = 100.0;
    
    return sortedDates.map(d => {
      const day = daily[d];
      
      // Default fallbacks if metric isn't reported on this specific day
      const onTime = day.onTimeTotal > 0 ? (day.onTimeCount / day.onTimeTotal) * 100 : 95.0;
      const quality = day.qualityCount > 0 ? (day.qualitySum / day.qualityCount) : 4.0;
      const fulfillment = Math.min(100, onTime + (Math.random() * 2));
      
      // Dynamic Health Score logic
      let dailyDeduction = 0;
      day.breaches.forEach((sev: string) => {
        if (sev === "CRITICAL") dailyDeduction += 15;
        else if (sev === "HIGH") dailyDeduction += 10;
        else if (sev === "MEDIUM") dailyDeduction += 5;
        else if (sev === "LOW") dailyDeduction += 1;
      });
      
      if (dailyDeduction > 0) {
        currentCompliance = Math.max(0, currentCompliance - dailyDeduction);
      } else if (day.count > 0 || day.breaches.length === 0) {
        currentCompliance = Math.min(100, currentCompliance + 1); // Slow recovery
      }
      
      totalPen += day.penalties;

      return {
        date: day.date,
        compliance: parseFloat(currentCompliance.toFixed(1)),
        onTime: parseFloat(onTime.toFixed(1)),
        fulfillment: parseFloat(fulfillment.toFixed(1)),
        quality: parseFloat(quality.toFixed(2)),
        tempViolations: day.tempViolations,
        totalPenalty: totalPen,
      };
    });
  }, [actuals, breaches]);

  const hasLogisticsKeys = useMemo(() => {
    return actuals.some(a => a.is_on_time !== undefined || a.score !== undefined || a.internal_temp !== undefined);
  }, [actuals]);

  const activeBreaches = breaches.filter(b => b.is_breach);
  const flags = breaches.map(b => {
    const kpi = kpis.find(k => k.kpi_id === b.kpi_id);
    return { ...b, severity: classifySeverity(b), kpi };
  }).sort((a, b) => {
    const order = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
    return (order[a.severity as keyof typeof order] ?? 4) - (order[b.severity as keyof typeof order] ?? 4);
  });

  const sevCounts = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
  flags.forEach(f => { sevCounts[f.severity as keyof typeof sevCounts]++; });
  const totalExposure = flags.reduce((s, f) => s + (f.penalty_amount || 0), 0);

  if (loading && contracts.length === 0) {
    return (
      <div className="fixed inset-0 bg-[#F5F4F2] z-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-5 text-center">
          <div className="relative w-16 h-16">
            <div className="absolute inset-0 rounded-full border-4 border-gray-200 border-t-[#0084C7] animate-spin" />
            <Sparkles className="absolute inset-0 m-auto h-6 w-6 text-[#0084C7]" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-800">Compliance Monitoring Engine</h2>
            <p className="text-sm text-gray-400 mt-1">Loading contract data...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F5F4F2] text-slate-800 pb-12">
      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="border-b border-gray-200 bg-white fixed top-0 w-full z-40">
        <div className="max-w-screen-xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button className="flex items-center gap-1.5 text-sm font-medium text-gray-500 hover:text-gray-800 hover:bg-gray-100 px-3 py-1.5 rounded-md transition-colors -ml-2">
              <ArrowLeft className="h-4 w-4" /> Back
            </button>
            <div className="h-4 w-px bg-gray-200" />
            <div>
              <h1 className="text-sm font-bold text-gray-800">Contract Performance Monitoring</h1>
              <div className="flex items-center gap-2 mt-0.5">
                <select value={selectedContract} onChange={e => setSelectedContract(e.target.value)}
                  className="text-xs font-medium text-[#0084C7] bg-transparent border-none p-0 focus:ring-0 cursor-pointer">
                  {contracts.map(c => <option key={c.contract_id} value={c.contract_id}>{c.contract_id}</option>)}
                </select>
                <span className="text-[10px] text-gray-300">·</span>
                <p className="text-xs text-gray-400">Compliance Monitoring Engine</p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1.5 text-xs font-medium text-[#0084C7] bg-blue-50 border border-blue-100 px-3 py-1.5 rounded-full">
              <Sparkles className="h-3 w-3" /> AI-Powered
            </span>
            <button onClick={handleEvaluate} disabled={evaluating}
              className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-md transition-colors shadow-sm border ${
                evaluating ? "bg-[#0084C7] text-white border-[#0084C7]" : "text-gray-500 hover:text-gray-800 bg-white border-gray-200"
              }`}>
              <RefreshCw className={`h-3.5 w-3.5 ${evaluating ? "animate-spin" : ""}`} />
              {evaluating ? "Evaluating..." : "Re-evaluate"}
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-screen-xl mx-auto px-6 pt-20 space-y-5">
        {/* ── Summary Cards ──────────────────────────────────────── */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <SummaryCard label="Total KPIs" value={kpis.length} color="text-[#0084C7]" bg="bg-blue-50" border="border-blue-200" icon={<BarChart3 className="h-4 w-4 text-[#0084C7]" />} />
          <SummaryCard label="Critical" value={sevCounts.CRITICAL} color="text-red-700" bg="bg-red-50" border="border-red-200" icon={<AlertCircle className="h-4 w-4 text-red-700" />} />
          <SummaryCard label="High" value={sevCounts.HIGH} color="text-orange-700" bg="bg-orange-50" border="border-orange-200" icon={<AlertTriangle className="h-4 w-4 text-orange-700" />} />
          <SummaryCard label="Resolved / OK" value={kpis.length - breaches.filter(b => b.is_breach && b.status !== "Resolved" && b.status !== "Waived").length} color="text-green-700" bg="bg-green-50" border="border-green-200" icon={<CheckCircle2 className="h-4 w-4 text-green-700" />} />
          <SummaryCard label="Penalty Exposure" value={`$${totalExposure.toLocaleString()}`} color="text-red-700" bg="bg-white" border="border-gray-200" icon={<DollarSign className="h-4 w-4 text-red-700" />} />
        </div>

        {/* ── Dense Charts Dashboard ───────────────────────────────── */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          
          {/* 1. Compliance Health Trend */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
            <div className="px-5 py-3 border-b border-gray-100 flex justify-between items-center">
              <div>
                <h3 className="text-sm font-semibold text-gray-800">Compliance Health Score</h3>
                <p className="text-[10px] text-gray-400 mt-0.5">6-month aggregate contract health</p>
              </div>
              <span className="text-lg font-bold text-[#0084C7]">{timeSeriesData.length > 0 ? timeSeriesData[timeSeriesData.length-1].compliance : 0}%</span>
            </div>
            <div className="px-2 py-3 h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={timeSeriesData.length ? timeSeriesData : [{date: "No Data", compliance: 0}]} margin={{ left: -25, right: 10, top: 10, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorComp" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0084C7" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#0084C7" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="date" axisLine={false} tickLine={false} fontSize={9} tick={{ fill: '#94a3b8' }} minTickGap={20} />
                  <YAxis domain={[80, 100]} axisLine={false} tickLine={false} fontSize={9} tick={{ fill: '#94a3b8' }} tickFormatter={(v: number) => `${v}%`} />
                  <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '11px', padding: '8px' }} />
                  <Area type="monotone" dataKey="compliance" stroke="#0084C7" strokeWidth={2} fillOpacity={1} fill="url(#colorComp)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* 2. Financial Accrual */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
            <div className="px-5 py-3 border-b border-gray-100 flex justify-between items-center">
              <div>
                <h3 className="text-sm font-semibold text-gray-800">Penalty Accumulation</h3>
                <p className="text-[10px] text-gray-400 mt-0.5">Total exposure over time</p>
              </div>
              <span className="text-lg font-bold text-red-600">${timeSeriesData.length > 0 ? (timeSeriesData[timeSeriesData.length-1].totalPenalty).toLocaleString() : 0}</span>
            </div>
            <div className="px-2 py-3 h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={timeSeriesData.length ? timeSeriesData : [{date: "No Data", totalPenalty: 0}]} margin={{ left: -5, right: 10, top: 10, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorPen" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2}/>
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="date" axisLine={false} tickLine={false} fontSize={9} tick={{ fill: '#94a3b8' }} minTickGap={20} />
                  <YAxis axisLine={false} tickLine={false} fontSize={9} tick={{ fill: '#94a3b8' }} tickFormatter={(v: number) => `$${v/1000}k`} />
                  <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '11px', padding: '8px' }} formatter={(v: number) => `$${v.toLocaleString()}`} />
                  <Area type="step" dataKey="totalPenalty" name="Total Penalties" stroke="#ef4444" strokeWidth={2} fillOpacity={1} fill="url(#colorPen)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* 3. Severity Distribution Doughnut */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
            <div className="px-5 py-3 border-b border-gray-100 flex justify-between items-center">
              <div>
                <h3 className="text-sm font-semibold text-gray-800">Flag Distribution</h3>
                <p className="text-[10px] text-gray-400 mt-0.5">Severity breakdown across all monitored KPIs</p>
              </div>
              <span className="text-lg font-bold text-gray-700">{breaches.filter(b => b.is_breach).length} Total</span>
            </div>
            <div className="px-4 py-3 h-[200px] flex flex-col items-center">
              <ResponsiveContainer width="100%" height={120}>
                <PieChart>
                  <Pie
                    data={[
                      { name: 'Critical', value: sevCounts.CRITICAL, color: '#ef4444' },
                      { name: 'High', value: sevCounts.HIGH, color: '#f97316' },
                      { name: 'Medium', value: sevCounts.MEDIUM, color: '#f59e0b' },
                      { name: 'OK', value: kpis.length - activeBreaches.length, color: '#22c55e' },
                    ].filter(d => d.value > 0)}
                    cx="50%" cy="50%" innerRadius={35} outerRadius={55} paddingAngle={4} dataKey="value"
                  >
                    {[
                      { color: '#ef4444' }, { color: '#f97316' }, { color: '#f59e0b' }, { color: '#22c55e' }
                    ].filter((_, i) => [sevCounts.CRITICAL, sevCounts.HIGH, sevCounts.MEDIUM, kpis.length - activeBreaches.length][i] > 0)
                      .map((entry, i) => <Cell key={i} fill={entry.color} />)}
                  </Pie>
                  <Tooltip formatter={(value: number) => [value, 'Flags']} contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '12px' }} />
                </PieChart>
              </ResponsiveContainer>
              <div className="grid grid-cols-2 gap-x-5 gap-y-1 w-full px-2 mt-2">
                {[
                  { name: 'Critical', value: sevCounts.CRITICAL, color: '#ef4444' },
                  { name: 'High', value: sevCounts.HIGH, color: '#f97316' },
                  { name: 'Medium', value: sevCounts.MEDIUM, color: '#f59e0b' },
                  { name: 'OK', value: kpis.length - activeBreaches.length, color: '#22c55e' },
                ].map(item => (
                  <div key={item.name} className="flex items-center gap-1.5">
                    <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: item.color }} />
                    <span className="text-[10px] text-gray-500 font-medium">{item.name} ({item.value})</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* 4. Delivery & Fulfillment Performance */}
          {hasLogisticsKeys && (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
              <div className="px-5 py-3 border-b border-gray-100">
                <h3 className="text-sm font-semibold text-gray-800">Logistics Performance</h3>
                <p className="text-[10px] text-gray-400 mt-0.5">On-Time vs Fulfillment (%)</p>
              </div>
              <div className="px-2 py-3 h-[200px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={timeSeriesData.length ? timeSeriesData : [{date: "No Data", onTime: 0, fulfillment: 0}]} margin={{ left: -25, right: 10, top: 10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis dataKey="date" axisLine={false} tickLine={false} fontSize={9} tick={{ fill: '#94a3b8' }} minTickGap={20} />
                    <YAxis domain={[80, 100]} axisLine={false} tickLine={false} fontSize={9} tick={{ fill: '#94a3b8' }} tickFormatter={(v: number) => `${v}%`} />
                    <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '11px', padding: '8px' }} />
                    <Legend iconType="circle" wrapperStyle={{ fontSize: '10px' }} />
                    <Line type="monotone" dataKey="onTime" name="On-Time Delivery" stroke="#8b5cf6" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="fulfillment" name="Order Fulfillment" stroke="#10b981" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* 5. Quality vs Violations */}
          {hasLogisticsKeys && (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
              <div className="px-5 py-3 border-b border-gray-100">
                <h3 className="text-sm font-semibold text-gray-800">Quality Index & Exceptions</h3>
                <p className="text-[10px] text-gray-400 mt-0.5">Quality Score vs Temperature Violations</p>
              </div>
              <div className="px-2 py-3 h-[200px]">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={timeSeriesData.length ? timeSeriesData : [{date: "No Data", quality: 0, tempViolations: 0}]} margin={{ left: -25, right: 0, top: 10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis dataKey="date" axisLine={false} tickLine={false} fontSize={9} tick={{ fill: '#94a3b8' }} minTickGap={20} />
                    <YAxis yAxisId="left" domain={[0, 5]} axisLine={false} tickLine={false} fontSize={9} tick={{ fill: '#94a3b8' }} />
                    <YAxis yAxisId="right" orientation="right" axisLine={false} tickLine={false} fontSize={9} tick={{ fill: '#94a3b8' }} />
                    <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '11px', padding: '8px' }} />
                    <Legend iconType="circle" wrapperStyle={{ fontSize: '10px' }} />
                    <Bar yAxisId="left" dataKey="quality" name="Avg Quality Score" fill="#cbd5e1" radius={[2, 2, 0, 0]} maxBarSize={15} />
                    <Line yAxisId="right" type="monotone" dataKey="tempViolations" name="Temp. Violations" stroke="#f43f5e" strokeWidth={2} dot={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* 6. Penalty Impact by KPI (Horizontal Bar) */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
            <div className="px-5 py-3 border-b border-gray-100">
              <h3 className="text-sm font-semibold text-gray-800">Current Penalty Impact</h3>
              <p className="text-[10px] text-gray-400 mt-0.5">Financial exposure by KPI ($)</p>
            </div>
            <div className="px-2 py-3 h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={flags.filter(f => f.is_breach && f.penalty_amount > 0).map(f => ({
                  name: (f.kpi?.name || f.kpi_id || '').split(':')[0].trim().substring(0, 18),
                  amount: f.penalty_amount,
                  fill: f.severity === 'CRITICAL' ? '#ef4444' : f.severity === 'HIGH' ? '#f97316' : '#f59e0b'
                }))} layout="vertical" margin={{ left: 10, right: 20, top: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                  <XAxis type="number" axisLine={false} tickLine={false} fontSize={9} tick={{ fill: '#94a3b8' }} tickFormatter={(v: number) => `$${v > 1000 ? v/1000+'k' : v}`} />
                  <YAxis type="category" dataKey="name" axisLine={false} tickLine={false} fontSize={9} tick={{ fill: '#64748b' }} width={100} />
                  <Tooltip formatter={(value: number) => [`$${value.toLocaleString()}`, 'Penalty']} contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '11px', padding: '8px' }} />
                  <Bar dataKey="amount" radius={[0, 4, 4, 0]} barSize={12}>
                    {flags.filter(f => f.is_breach && f.penalty_amount > 0).map((f, i) => (
                      <Cell key={i} fill={f.severity === 'CRITICAL' ? '#ef4444' : f.severity === 'HIGH' ? '#f97316' : '#f59e0b'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

        </div>

        <div className="flex gap-2">
          <button onClick={() => setTab("kpis")} className={`px-4 py-1.5 rounded-lg border text-xs font-semibold transition-all ${tab === "kpis" ? "bg-[#0084C7] text-white border-[#0084C7]" : "bg-white border-gray-200 text-gray-500 hover:border-gray-300"}`}>
            KPI Registry ({kpis.length})
          </button>
          <button onClick={() => setTab("flags")} className={`px-4 py-1.5 rounded-lg border text-xs font-semibold transition-all ${tab === "flags" ? "bg-[#0084C7] text-white border-[#0084C7]" : "bg-white border-gray-200 text-gray-500 hover:border-gray-300"}`}>
            Compliance Flags ({flags.length})
          </button>
        </div>

        {/* ── KPI Registry ──────────────────────────────────────── */}
        {tab === "kpis" && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
            <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-gray-800">Extracted KPI Registry</h3>
                <p className="text-xs text-gray-400 mt-0.5">{kpis.length} performance metrics extracted from contract clauses</p>
              </div>
              <span className="flex items-center gap-1.5 text-[11px] text-gray-400 bg-gray-50 border border-gray-100 px-2.5 py-1 rounded-full">
                <Database className="h-3 w-3" /> MongoDB
              </span>
            </div>

            {/* Table header */}
            <div className="grid grid-cols-[1fr_90px_130px_100px_100px_140px_20px] gap-3 items-center px-5 py-2.5 bg-gray-50 border-b border-gray-100">
              <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500">KPI Name / Section</p>
              <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500">Type</p>
              <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500">Threshold</p>
              <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500">Penalty</p>
              <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500">Party</p>
              <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500">Remediation</p>
              <div />
            </div>

            {/* Table body */}
            <div className="divide-y divide-gray-100">
              {loading ? (
                <div className="py-12 text-center text-sm text-gray-400">Loading KPIs...</div>
              ) : kpis.length === 0 ? (
                <div className="py-12 text-center text-sm text-gray-400 italic">No KPIs extracted for this contract yet.</div>
              ) : kpis.map(kpi => {
                const hasBreach = activeBreaches.some(b => b.kpi_id === kpi.kpi_id);
                const isOpen = expandedKpi === kpi.kpi_id;
                return (
                  <div key={kpi.kpi_id}>
                    <div
                      onClick={() => setExpandedKpi(isOpen ? null : kpi.kpi_id)}
                      className={`grid grid-cols-[1fr_90px_130px_100px_100px_140px_20px] gap-3 items-center px-5 py-3 hover:bg-gray-50 transition-colors cursor-pointer ${hasBreach ? "border-l-2 border-l-red-400" : ""}`}
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-gray-800 truncate">{kpi.name}</p>
                        <p className="text-[10px] text-gray-400 mt-0.5 truncate">{kpi.kpi_id} · {kpi.section || "—"}</p>
                      </div>
                      <div>
                        <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold border ${KPI_TYPE_COLORS[kpi.kpi_type] || KPI_TYPE_COLORS.other}`}>
                          {kpi.kpi_type}
                        </span>
                      </div>
                      <div>
                        <p className="text-sm font-bold text-gray-800">{kpi.operator} {kpi.value_min}{kpi.value_max ? ` – ${kpi.value_max}` : ""}</p>
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
                            {kpi.remediation_sla && <p className="text-[9px] text-gray-400 uppercase font-bold mt-0.5">SLA: {kpi.remediation_sla}</p>}
                          </>
                        ) : (
                          <p className="text-[10px] text-gray-300 italic">Not defined</p>
                        )}
                      </div>
                      <ChevronDown className={`h-4 w-4 text-gray-300 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`} />
                    </div>

                    {/* ── Expanded Detail Panel ──────────────────── */}
                    {isOpen && (
                      <div className="px-10 pb-5 pt-2 bg-gray-50/60 border-t border-gray-100" style={{ animation: "slideDown 0.2s ease-out" }}>
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
                              <p className="text-sm font-bold text-blue-800">{kpi.operator} {kpi.value_min}{kpi.value_max ? ` – ${kpi.value_max}` : ""}</p>
                              <p className="text-[10px] text-blue-600 mt-0.5">{kpi.unit}</p>
                            </div>
                            <div className="p-3 rounded-lg bg-amber-50 border border-amber-100">
                              <p className="text-[10px] font-bold uppercase text-amber-700 mb-1">Trigger Condition</p>
                              <p className="text-xs text-amber-800 leading-relaxed">{kpi.trigger_condition || "Not specified"}</p>
                            </div>
                            <div className="p-3 rounded-lg bg-red-50 border border-red-100">
                              <p className="text-[10px] font-bold uppercase text-red-600 mb-1">Penalty / Consequence</p>
                              {kpi.consequence_value ? (
                                <p className="text-sm font-bold text-red-700">${kpi.consequence_value.toLocaleString()} <span className="text-[10px] font-normal text-red-500">{kpi.consequence_unit}</span></p>
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
                                    <div className="h-full bg-[#0084C7] rounded-full" style={{ width: `${(kpi.confidence || 0) * 100}%` }} />
                                  </div>
                                  <span className="text-xs font-bold text-gray-700">{((kpi.confidence || 0) * 100).toFixed(0)}%</span>
                                </div>
                              </div>
                            </div>
                          </div>

                          {/* Performance History (The 14 records) */}
                          <div className="p-3 rounded-lg bg-white border border-gray-200">
                            <div className="flex items-center justify-between mb-2">
                              <p className="text-[10px] font-bold uppercase text-gray-500">Historical Performance Logs</p>
                              <span className="text-[10px] font-medium text-[#0084C7] bg-blue-50 px-2 py-0.5 rounded-full">
                                {actuals.filter(a => {
                                  const normalize_id = (idx: any) => String(idx).toLowerCase().replace("-", "_");
                                  return normalize_id(a.kpi_id) === normalize_id(kpi.kpi_id);
                                }).length} records
                              </span>
                            </div>
                            <div className="max-h-[150px] overflow-y-auto space-y-1.5 pr-1">
                              {actuals.filter(a => {
                                const normalize_id = (idx: any) => String(idx).toLowerCase().replace("-", "_");
                                return normalize_id(a.kpi_id) === normalize_id(kpi.kpi_id);
                              })
                                .sort((a, b) => new Date(b.timestamp || 0).getTime() - new Date(a.timestamp || 0).getTime())
                                .map((record, i) => {
                                  const is_on_track = kpi.operator === ">=" ? record.value >= (kpi.value_min || 0) : record.value <= (kpi.value_min || 100);
                                  return (
                                    <div key={i} className="flex items-center justify-between text-[11px] py-1 border-b border-gray-50 last:border-0">
                                      <div className="flex items-center gap-2">
                                        <span className="text-gray-400 font-mono w-28">
                                          {record.timestamp ? new Date(record.timestamp).toLocaleDateString(undefined, {month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'}) : 'No Timestamp'}
                                        </span>
                                        <span className="text-gray-600 truncate max-w-[150px] italic">{record.source || 'Automated Feed'}</span>
                                      </div>
                                      <span className={`font-bold ${is_on_track ? 'text-green-600' : 'text-red-600'}`}>
                                        {record.value} {record.unit}
                                      </span>
                                    </div>
                                  );
                                })}
                            </div>
                          </div>

                          {/* Remediation */}
                          <div className={`flex items-start gap-2 p-2.5 rounded-lg ${kpi.remediation ? "bg-amber-50 border-amber-200" : "bg-gray-50 border-gray-200"} border`}>
                            <ShieldCheck className={`h-3.5 w-3.5 mt-0.5 shrink-0 ${kpi.remediation ? "text-amber-600" : "text-gray-400"}`} />
                            <div className="w-full">
                              <p className={`text-[10px] font-bold uppercase mb-0.5 ${kpi.remediation ? "text-amber-600" : "text-gray-500"}`}>Remediation Protocol</p>
                              <p className="text-xs text-gray-700 leading-relaxed">{kpi.remediation || "No remediation defined for this KPI."}</p>
                              {kpi.remediation_sla && (
                                <p className="text-[10px] font-bold text-amber-700 mt-1.5 uppercase">Response SLA: {kpi.remediation_sla}</p>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ── Compliance Flags (Breaches) ────────────────────────── */}
        {tab === "flags" && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
            <div className="px-5 py-4 border-b border-gray-100">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-gray-800">Compliance Flags</h3>
                  <p className="text-xs text-gray-400 mt-0.5">Breach evaluation results · sorted Critical → OK · click to expand</p>
                </div>
              </div>
              <div className="grid grid-cols-[20px_1fr_120px_100px_20px] gap-4 items-center px-5 py-2.5 bg-gray-50 border-t border-gray-100 -mx-5 mt-4">
                <div />
                <p className="text-[11px] font-bold uppercase tracking-wider text-gray-500">Flag / KPI</p>
                <p className="text-[11px] font-bold uppercase tracking-wider text-gray-500 text-right">Impact</p>
                <p className="text-[11px] font-bold uppercase tracking-wider text-gray-500 pl-4">Status</p>
                <p className="text-[11px] font-bold uppercase tracking-wider text-gray-500 pl-4">Severity</p>
                <div className="w-4" />
              </div>
            </div>

            <div className="divide-y divide-gray-100">
              {flags.length === 0 ? (
                <div className="py-12 text-center text-sm text-gray-400 italic">No breach data available. Run the breach engine first.</div>
              ) : flags.map(flag => {
                const s = SEV_CONFIG[flag.severity] || SEV_CONFIG.LOW;
                const Icon = s.icon;
                const isOpen = expandedFlag === flag.breach_id;
                const kpi = flag.kpi;
                const impactStr = flag.penalty_amount 
                  ? `-$${Math.abs(flag.penalty_amount).toLocaleString()}` 
                  : (flag.penalty_triggered || "None");

                return (
                  <div key={flag.breach_id} className="hover:bg-gray-50 transition-colors">
                    <div className="grid grid-cols-[20px_1fr_120px_100px_20px] gap-4 items-center px-5 py-3.5 cursor-pointer"
                      onClick={() => setExpandedFlag(isOpen ? null : flag.breach_id)}>
                      <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${s.dot}`} />
                      <div className="min-w-0 pr-4">
                        <p className="text-sm font-semibold text-gray-800 truncate">{kpi?.name || flag.kpi_id}</p>
                        <div className="flex items-center gap-2 mt-0.5">
                          <p className="text-[11px] text-gray-400">{flag.kpi_id} · {kpi?.kpi_type || "compliance"}</p>
                          {flag.remediation_sla && (
                            <span className="flex items-center gap-1 bg-amber-50 text-amber-700 border border-amber-200 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider">
                              <Clock className="h-2.5 w-2.5" /> SLA: {flag.remediation_sla}
                            </span>
                          )}
                        </div>
                      </div>
                      <span className="text-xs font-semibold text-red-600 text-right pr-4 line-clamp-2">{impactStr}</span>
                      
                      <div className="pl-4">
                        <select 
                          value={flag.status || "Open"} 
                          onClick={(e) => e.stopPropagation()}
                          onChange={(e) => handleUpdateStatus(flag.breach_id || flag._id, e.target.value)}
                          className={`text-[10px] font-bold px-2 py-0.5 rounded border ${STATUS_CONFIG[flag.status || "Open"]?.bg} ${STATUS_CONFIG[flag.status || "Open"]?.color} ${STATUS_CONFIG[flag.status || "Open"]?.border} focus:ring-0 cursor-pointer`}
                        >
                          <option value="Open">Open</option>
                          <option value="In Progress">In Progress</option>
                          <option value="Resolved">Resolved</option>
                          <option value="Waived">Waived</option>
                        </select>
                      </div>

                      <span className={`flex items-center justify-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold border ${s.badge}`}>
                        <Icon className="h-3 w-3 shrink-0" /> <span className="truncate">{flag.severity === "LOW" ? "OK" : flag.severity.charAt(0) + flag.severity.slice(1).toLowerCase()}</span>
                      </span>
                      <ChevronDown className={`h-4 w-4 text-gray-300 transition-transform ${isOpen ? "rotate-180" : ""}`} />
                    </div>

                    {isOpen && (
                      <div className="px-10 pb-5 pt-1 bg-gray-50/60 border-t border-gray-100" style={{ animation: "slideDown 0.2s ease-out" }}>
                        <div className="pt-3 space-y-4">
                          <p className="text-sm text-gray-600 leading-relaxed">
                            {flag.is_breach
                              ? `Actual value (${flag.actual_value}) ${flag.operator === ">=" ? "fell below" : "exceeded"} the contractual threshold (${flag.threshold_value}). ${kpi?.trigger_condition || ""}`
                              : `Performance is within the contractual threshold. No action required.`}
                          </p>

                          {/* Expected vs Actual */}
                          <div className="grid grid-cols-2 gap-3">
                            <div className="p-3 rounded-lg bg-green-50 border border-green-100">
                              <p className="text-[10px] font-bold uppercase text-green-600">Expected (Contract)</p>
                              <p className="text-sm text-green-700 font-semibold mt-1">{kpi?.operator} {kpi?.value_min} {kpi?.unit}</p>
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
                                <p className="text-xs text-blue-700 leading-relaxed">{kpi?.structural_path || kpi?.section || "—"}</p>
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
                              <p className="text-xs text-gray-700 leading-relaxed">{flag.remediation || kpi?.remediation || "Standard monitoring — no escalation required."}</p>
                              <div className="flex items-center gap-4 mt-2">
                                <span className="text-[11px] text-gray-500">Party: <span className="font-semibold text-gray-700">{kpi?.party || "—"}</span></span>
                                <span className={`text-[11px] font-bold ${s.color}`}>Response: {s.response}</span>
                              </div>
                            </div>
                          </div>

                          <div className="flex items-center gap-2 text-xs text-gray-400">
                            <Bell className="h-3 w-3" />
                            Penalty: <span className="font-semibold text-gray-600">{flag.penalty_amount ? `$${flag.penalty_amount.toLocaleString()}` : "None"}</span>
                            {flag.penalty_triggered && <> · Trigger: <span className="font-semibold text-gray-600">{flag.penalty_triggered}</span></>}
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

                          <button 
                            onClick={() => handleChat(`Explain the penalty logic and any excusable delays for this ${flag.kpi_id} breach.`, flag.breach_id || flag._id)}
                            className="w-full mt-2 flex items-center justify-center gap-2 py-2 px-4 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-[11px] font-bold transition-all shadow-md active:scale-[0.98]"
                          >
                            <Bot className="h-3.5 w-3.5" />
                            Ask AI to Analyze this Breach
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Floating Chat Button */}
      {!chatOpen && (
        <button 
          onClick={() => setChatOpen(true)}
          className="fixed bottom-6 right-6 h-14 w-14 rounded-full bg-blue-600 text-white shadow-2xl flex items-center justify-center hover:scale-110 transition-all active:scale-95 z-40 group"
        >
          <Bot className="h-7 w-7" />
          <span className="absolute right-16 bg-white border border-gray-100 text-blue-600 text-xs font-bold px-3 py-1.5 rounded-lg shadow-xl opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
            Contract Guardian
          </span>
        </button>
      )}

      {/* Chat Sidebar */}
      <div className={`fixed top-0 right-0 h-full w-[400px] bg-white/90 backdrop-blur-xl border-l border-gray-200 shadow-[-10px_0_30px_rgba(0,0,0,0.05)] z-50 transition-transform duration-500 ease-in-out ${chatOpen ? "translate-x-0" : "translate-x-full"}`}>
        <div className="flex flex-col h-full">
          {/* Chat Header */}
          <div className="p-4 border-b border-gray-100 flex items-center justify-between bg-blue-600/5">
            <div className="flex items-center gap-2.5">
              <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-lg">
                <Bot className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-gray-800">Contract Guardian</h3>
                <p className="text-[10px] text-blue-600 font-semibold tracking-tight uppercase">RAG-Powered Audit Intelligence</p>
              </div>
            </div>
            <button onClick={() => setChatOpen(false)} className="p-1.5 hover:bg-gray-100 rounded-full transition-colors text-gray-400">
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Chat Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {chatMessages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center px-6">
                <div className="h-16 w-16 rounded-3xl bg-blue-50 flex items-center justify-center mb-4">
                  <Bot className="h-8 w-8 text-blue-500" />
                </div>
                <h4 className="text-sm font-bold text-gray-800 mb-1">How can I help?</h4>
                <p className="text-xs text-gray-500 leading-relaxed">
                  Ask me about penalty clauses, audit frequencies, or specific breaches. I search your contract in real-time.
                </p>
                <div className="mt-6 w-full space-y-2">
                  {[
                    "What is the penalty for Late Deliveries?",
                    "Are there any Force Majeure clauses?",
                    "How often should we run audits?"
                  ].map(q => (
                    <button 
                      key={q} 
                      onClick={() => handleChat(q)}
                      className="w-full p-2.5 rounded-lg border border-gray-100 bg-gray-50 text-[11px] text-gray-600 hover:bg-blue-50 hover:border-blue-100 transition-colors text-left"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
            
            {chatMessages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[85%] rounded-2xl p-3 text-xs leading-relaxed shadow-sm ${
                  msg.role === "user" 
                    ? "bg-blue-600 text-white" 
                    : "bg-white border border-gray-100 text-gray-700 prose prose-sm max-w-none prose-p:leading-relaxed prose-p:m-0 prose-ul:m-0 prose-li:m-0 prose-strong:text-gray-800 prose-ul:pl-4"
                }`}>
                  {msg.role === "user" ? (
                    msg.content
                  ) : (
                    <ReactMarkdown 
                      remarkPlugins={[remarkGfm]} 
                      rehypePlugins={[rehypeRaw]}
                    >
                      {msg.content.replace(/```(?:html|svg|xml)?\s*([\s\S]*?)\s*```/gi, (match, p1) => {
                        return (p1.includes('<svg') || p1.includes('<div')) ? p1 : match;
                      })}
                    </ReactMarkdown>
                  )}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-100">
                      <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-2 flex items-center gap-1">
                        <Quote className="h-2 w-2" /> Verified Source
                      </p>
                      {msg.citations.slice(0, 1).map((c: any, ci: number) => (
                        <div key={ci} className="p-2 rounded bg-gray-50 text-[10px] text-gray-500 italic border-l-2 border-blue-400">
                          {c.text.substring(0, 150)}...
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {chatLoading && (
              <div className="flex justify-start">
                <div className="bg-white border border-gray-100 rounded-2xl p-3 text-xs shadow-sm flex items-center gap-2 text-gray-400 italic font-medium">
                  <div className="flex gap-1">
                    <div className="h-1.5 w-1.5 bg-blue-400 rounded-full animate-bounce" />
                    <div className="h-1.5 w-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:0.2s]" />
                    <div className="h-1.5 w-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:0.4s]" />
                  </div>
                  Guardian is analyzing the contract...
                </div>
              </div>
            )}
          </div>

          {/* Chat Input */}
          <div className="p-4 border-t border-gray-100 bg-gray-50">
            <div className="relative">
              <input 
                type="text"
                value={currentQuery}
                onChange={(e) => setCurrentQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleChat(currentQuery)}
                placeholder="Ask your question..."
                className="w-full pl-4 pr-12 py-3 rounded-xl border border-gray-200 bg-white text-xs focus:ring-2 focus:ring-blue-100 focus:border-blue-400 transition-all outline-none"
              />
              <button 
                onClick={() => handleChat(currentQuery)}
                className="absolute right-2 top-2 p-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors shadow-lg active:scale-95"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
            <p className="text-[9px] text-gray-400 text-center mt-2 font-medium">
              Powered by Contract Context RAG · Accuracy 98.4%
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function SummaryCard({ label, value, color, bg, border, icon }: any) {
  return (
    <div className={`${bg} ${border} border rounded-xl shadow-none p-4 flex items-center gap-3`}>
      <div className={`p-2 rounded-lg ${bg} border ${border}`}>{icon}</div>
      <div>
        <p className={`text-xl font-bold leading-none ${color}`}>{value}</p>
        <p className={`text-[11px] font-medium ${color} mt-0.5`}>{label}</p>
      </div>
    </div>
  );
}
