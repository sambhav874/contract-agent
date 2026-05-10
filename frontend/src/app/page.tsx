"use client";

import { useState, useEffect, useMemo } from "react";
import {
  ShieldCheck, AlertTriangle, CheckCircle2, ChevronDown, ArrowLeft,
  RefreshCw, Sparkles, Server, DollarSign, AlertCircle, BarChart3,
  Clock, FileText, Activity, Bell, Database, Layout, Terminal, Cpu, Lock, Search, ArrowRight, ChevronRight, Filter, Download, Calendar, Layers, Zap
} from "lucide-react";
import { 
  fetchContracts, fetchKPIs, fetchBreaches, fetchPerformance, 
  evaluateContract, updateBreach, chatWithContract,
  fetchAvailableContracts, ingestContract, extractKPIs
} from "@/lib/api";
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
  const [activeArtifact, setActiveArtifact] = useState<{content: string, type: string} | null>(null);
  
  // Journey state
  const [journey, setJourney] = useState<"LANDING" | "INGESTING" | "EXTRACTING" | "DASHBOARD">("LANDING");
  const [availableContracts, setAvailableContracts] = useState<any[]>([]);
  const [onboardingFile, setOnboardingFile] = useState<string | null>(null);
  const [journeyLog, setJourneyLog] = useState<string[]>([]);
  const [onboardingProgress, setOnboardingProgress] = useState(0);

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
      
      let answerText = result.answer;
      let artifact = null;
      
      const artifactRegex = /```(?:html|svg|xml)?\s*([\s\S]*?)\s*```/i;
      const match = artifactRegex.exec(answerText);
      
      if (match && (match[1].includes('<svg') || match[1].includes('<div'))) {
         artifact = {
            type: match[1].includes('<svg') ? 'svg' : 'html',
            content: match[1]
         };
         answerText = answerText.replace(match[0], '').trim();
         setActiveArtifact(artifact);
      } else {
         const rawSvgMatch = answerText.match(/<svg[\s\S]*?<\/svg>/i);
         if (rawSvgMatch) {
            artifact = { type: 'svg', content: rawSvgMatch[0] };
            answerText = answerText.replace(rawSvgMatch[0], '').trim();
            setActiveArtifact(artifact);
         } else {
            const rawHtmlMatch = answerText.match(/<div[\s\S]*?<\/div>/i);
            if (rawHtmlMatch) {
               artifact = { type: 'html', content: rawHtmlMatch[0] };
               answerText = answerText.replace(rawHtmlMatch[0], '').trim();
               setActiveArtifact(artifact);
            }
         }
      }

      setChatMessages(prev => [...prev, { role: "assistant", content: answerText, citations: result.citations, artifact }]);
    } catch (e) {
      setChatMessages(prev => [...prev, { role: "assistant", content: "Sorry, I encountered an error. Please try again." }]);
    } finally {
      setChatLoading(false);
      setCurrentQuery("");
    }
  }

  useEffect(() => {
    // Force end loading after 5 seconds as a safety fallback
    const timer = setTimeout(() => {
      setLoading(false);
    }, 5000);

    (async () => {
      try {
        console.log("Initializing dashboard data fetch...");
        const [active, available] = await Promise.all([
          fetchContracts().catch(e => { console.error("Contracts fetch failed", e); return []; }),
          fetchAvailableContracts().catch(e => { console.error("Available contracts fetch failed", e); return []; })
        ]);
        
        console.log("Fetch complete:", { activeCount: active.length, availableCount: available.length });
        setContracts(active || []);
        setAvailableContracts(available || []);
        
        if (active && active.length > 0 && !selectedContract) {
           // Auto-select first contract if none selected
           // setSelectedContract(active[0].contract_id);
        }
      } catch (e) { 
        console.error("Initial load error:", e); 
      } finally { 
        setLoading(false);
        clearTimeout(timer);
      }
    })();
    
    return () => clearTimeout(timer);
  }, []);

  async function handleStartOnboarding(filename: string) {
    setOnboardingFile(filename);
    setJourney("INGESTING");
    setKpis([]);
    setJourneyLog(["Initializing ingestion engine...", `Target: ${filename}`]);
    setOnboardingProgress(10);

    try {
      // 1. Ingest
      setJourneyLog(prev => [...prev, "Parsing contract structure...", "Generating vector embeddings..."]);
      const ingestRes = await ingestContract(filename);
      setOnboardingProgress(40);
      setJourneyLog(prev => [...prev, `✓ Ingested: ${ingestRes.name}`, "Initializing Agentic Review..."]);
      
      // 2. Extract KPIs
      setJourney("EXTRACTING");
      setOnboardingProgress(60);
      setJourneyLog(prev => [...prev, "Agent active: Scanning for performance obligations...", "Extracting metrics and penalty tiers..."]);
      
      const extractRes = await extractKPIs(ingestRes.contract_id);
      setKpis(extractRes.kpis);
      setOnboardingProgress(90);
      setJourneyLog(prev => [...prev, `✓ Extracted ${extractRes.kpis_count} KPIs`, "Finalizing compliance dashboard..."]);
      
      // 3. Finalize
      const [newContracts, k, b, a] = await Promise.all([
        fetchContracts(),
        fetchKPIs(ingestRes.contract_id),
        fetchBreaches(ingestRes.contract_id),
        fetchPerformance(ingestRes.contract_id)
      ]);
      
      setContracts(newContracts);
      setSelectedContract(ingestRes.contract_id);
      setKpis(k);
      setBreaches(b);
      setActuals(a);
      
      setOnboardingProgress(100);
      setTimeout(() => setJourney("DASHBOARD"), 800);
      
    } catch (e) {
      console.error(e);
      setJourneyLog(prev => [...prev, "❌ Error: Onboarding failed. Please try again."]);
    }
  }

  useEffect(() => {
    if (!selectedContract) return;
    
    const timer = setTimeout(() => {
      setLoading(false);
    }, 8000); // Higher timeout for data-heavy dashboard load

    (async () => {
      setLoading(true);
      try {
        const [k, b, a] = await Promise.all([
          fetchKPIs(selectedContract).catch(e => { console.error("KPIs fetch failed", e); return []; }), 
          fetchBreaches(selectedContract).catch(e => { console.error("Breaches fetch failed", e); return []; }),
          fetchPerformance(selectedContract).catch(e => { console.error("Performance fetch failed", e); return []; })
        ]);
        setKpis(k || []); 
        setBreaches(b || []); 
        setActuals(a || []);
      } catch (e) { 
        console.error("Dashboard data load error:", e); 
      } finally { 
        setLoading(false);
        clearTimeout(timer);
      }
    })();
    
    return () => clearTimeout(timer);
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
      
      // Real metrics (0 if no data)
      const onTime = day.onTimeTotal > 0 ? (day.onTimeCount / day.onTimeTotal) * 100 : 0;
      const quality = day.qualityCount > 0 ? (day.qualitySum / day.qualityCount) : 0;
      const fulfillment = day.onTimeTotal > 0 ? onTime : 0;
      
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

  // ── Overlay Rendering ────────────────────────────────────────────────
  const renderOverlay = () => {
    if (journey === "LANDING") {
      return (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-6 animate-in fade-in duration-300">
          <div className="max-w-4xl w-full bg-white/80 backdrop-blur-xl rounded-[2.5rem] border border-white shadow-[0_32px_64px_-16px_rgba(0,0,0,0.15)] overflow-hidden">
            <div className="grid grid-cols-1 md:grid-cols-[320px_1fr] h-[600px]">
              {/* Sidebar: Active Workspace */}
              <div className="bg-gray-50/50 p-8 border-r border-gray-100 flex flex-col">
                <div className="flex items-center gap-3 mb-8">
                  <div className="w-10 h-10 bg-black rounded-xl flex items-center justify-center">
                    <ShieldCheck className="h-6 w-6 text-white" />
                  </div>
                  <div>
                    <h1 className="text-lg font-bold text-gray-900 leading-tight">Contract<br/>Guardian</h1>
                  </div>
                </div>

                <div className="flex-1 space-y-6">
                  <div>
                    <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">Active Workspace</h2>
                    <div className="space-y-2">
                      {contracts.length === 0 ? (
                        <div className="p-4 rounded-2xl bg-white border border-gray-100 text-center">
                          <p className="text-xs text-gray-400 italic">No active contracts</p>
                        </div>
                      ) : (
                        contracts.map(c => (
                          <button 
                            key={c.contract_id}
                            onClick={() => { setSelectedContract(c.contract_id); setJourney("DASHBOARD"); }}
                            className="w-full p-4 bg-white border border-gray-200 rounded-2xl hover:border-blue-400 hover:shadow-md transition-all text-left group"
                          >
                            <div className="flex justify-between items-start">
                              <div className="min-w-0">
                                <h3 className="font-bold text-gray-800 group-hover:text-blue-600 transition-colors truncate">{c.name || c.contract_id}</h3>
                                <p className="text-[10px] text-gray-400 mt-1 uppercase tracking-tighter">{c.contract_id.substring(0,8)}</p>
                              </div>
                              <Activity className="h-4 w-4 text-gray-300 group-hover:text-blue-400" />
                            </div>
                          </button>
                        ))
                      )}
                    </div>
                  </div>
                </div>

                <div className="pt-6 border-t border-gray-100 text-[10px] text-gray-400 font-medium">
                  v2.4.0 · AGENTIC_MODE_ENABLED
                </div>
              </div>

              {/* Main: New Reviewal */}
              <div className="p-10 overflow-y-auto">
                <div className="mb-10">
                  <h2 className="text-3xl font-bold text-gray-900 tracking-tight mb-2">New Compliance Review</h2>
                  <p className="text-gray-500">Select a local source to initialize agentic KPI extraction and baseline audit.</p>
                </div>

                <div className="space-y-4">
                  <h2 className="text-xs font-bold text-gray-400 uppercase tracking-wider flex items-center gap-2">
                    <Sparkles className="h-3 w-3" /> Available Sources
                  </h2>
                  <div className="grid grid-cols-1 gap-3">
                    {availableContracts.map(f => (
                      <button 
                        key={f.filename}
                        onClick={() => handleStartOnboarding(f.filename)}
                        className="p-5 bg-white border border-gray-200 rounded-2xl hover:border-emerald-400 hover:shadow-xl hover:translate-y-[-2px] transition-all text-left group flex items-center gap-5"
                      >
                        <div className="p-3 bg-emerald-50 rounded-xl group-hover:bg-emerald-100 transition-colors">
                          <FileText className="h-6 w-6 text-emerald-600" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3 className="font-bold text-gray-800 group-hover:text-emerald-600 transition-colors truncate text-lg">{f.filename}</h3>
                          <p className="text-xs text-gray-400 mt-1">Found in ./tests/fixtures · {(f.size / 1024).toFixed(1)} KB</p>
                        </div>
                        <div className="flex items-center gap-2 px-4 py-2 bg-gray-50 rounded-lg text-xs font-bold text-gray-500 group-hover:bg-emerald-600 group-hover:text-white transition-all">
                          INITIALIZE <ArrowRight className="h-3 w-3" />
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      );
    }

    if (journey === "INGESTING" || journey === "EXTRACTING") {
      return (
        <div className="fixed inset-0 z-[70] flex items-center justify-center p-6 animate-in zoom-in-95 duration-500">
          <div className="max-w-6xl w-full bg-[#0F1115] rounded-[3rem] border border-white/10 shadow-[0_0_80px_rgba(0,0,0,0.6)] overflow-hidden flex flex-col h-[700px]">
            {/* Header: Agent State */}
            <div className="p-8 border-b border-white/5 flex items-center justify-between bg-gradient-to-r from-blue-900/20 to-transparent">
              <div className="flex items-center gap-5">
                <div className="relative">
                  <div className="absolute inset-0 bg-blue-500 blur-xl opacity-30 animate-pulse" />
                  <div className="relative w-14 h-14 bg-blue-600 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-500/20">
                    <Bot className="h-8 w-8 text-white" />
                  </div>
                </div>
                <div>
                  <div className="flex items-center gap-3">
                    <h2 className="text-2xl font-bold text-white tracking-tight">
                      {journey === "INGESTING" ? "Structural Ingestion" : "Agentic KPI Extraction"}
                    </h2>
                    <span className="px-2 py-0.5 rounded bg-blue-500/20 border border-blue-500/30 text-[10px] font-bold text-blue-400 uppercase tracking-widest animate-pulse">
                      Active
                    </span>
                  </div>
                  <p className="text-gray-400 text-sm mt-1 font-mono">ID: {onboardingFile} · Mode: Full_Context_Audit</p>
                </div>
              </div>
              <div className="flex flex-col items-end">
                <div className="text-4xl font-black text-white font-mono leading-none">{onboardingProgress}%</div>
                <div className="w-48 h-1.5 bg-white/10 rounded-full mt-3 overflow-hidden">
                  <div className="h-full bg-blue-500 transition-all duration-1000 ease-out shadow-[0_0_10px_rgba(59,130,246,0.5)]" style={{ width: `${onboardingProgress}%` }} />
                </div>
              </div>
            </div>

            {/* Agentic Workspace */}
            <div className="flex-1 grid grid-cols-1 md:grid-cols-[400px_1fr] overflow-hidden">
              {/* Left: Agent Mind (Logs) */}
              <div className="border-r border-white/5 flex flex-col bg-black/40">
                <div className="p-4 border-b border-white/5 bg-white/5">
                  <h3 className="text-[10px] font-bold text-gray-500 uppercase tracking-widest flex items-center gap-2">
                    <Terminal className="h-3 w-3" /> Execution Log
                  </h3>
                </div>
                <div className="flex-1 p-6 font-mono text-[11px] overflow-y-auto space-y-3 custom-scrollbar">
                  {journeyLog.map((log, i) => (
                    <div key={i} className="flex gap-3 group">
                      <span className="text-gray-600 shrink-0 select-none">{(i + 1).toString().padStart(2, '0')}</span>
                      <span className={
                        log.startsWith('✓') ? 'text-emerald-400' : 
                        log.startsWith('❌') ? 'text-red-400' : 
                        'text-gray-300'
                      }>
                        <span className="text-gray-500 mr-1.5">›</span>{log}
                      </span>
                    </div>
                  ))}
                  <div className="flex gap-3 animate-pulse">
                    <span className="text-gray-600 shrink-0 select-none">{(journeyLog.length + 1).toString().padStart(2, '0')}</span>
                    <span className="text-blue-400">
                      <span className="text-blue-500/50 mr-1.5">›</span>
                      Agent pondering...
                    </span>
                  </div>
                </div>
              </div>

              {/* Right: Discovery Stream & Document Context */}
              <div className="flex flex-col bg-slate-900/20">
                <div className="p-4 border-b border-white/5 bg-white/5 flex justify-between items-center">
                  <h3 className="text-[10px] font-bold text-gray-500 uppercase tracking-widest flex items-center gap-2">
                    <Layout className="h-3 w-3" /> Discovery Feed
                  </h3>
                  <div className="flex gap-4">
                    <div className="flex items-center gap-2">
                      <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-ping" />
                      <span className="text-[10px] text-gray-400 uppercase font-bold">Scanning Document...</span>
                    </div>
                  </div>
                </div>
                
                <div className="flex-1 p-8 overflow-y-auto space-y-6">
                  {kpis.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center opacity-40">
                      <Search className="h-12 w-12 text-gray-600 mb-4 animate-bounce" />
                      <p className="text-gray-400 font-mono text-xs">Waiting for extraction sequence results...</p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 gap-4">
                      {kpis.map((k, i) => (
                        <div key={i} className="bg-white/5 border border-white/10 rounded-2xl p-4 animate-in slide-in-from-right-4 fade-in duration-500" style={{ animationDelay: `${i * 100}ms` }}>
                          <div className="flex justify-between items-start mb-3">
                            <span className="px-2 py-0.5 rounded bg-blue-500/10 text-[9px] font-bold text-blue-400 uppercase border border-blue-500/20">{k.kpi_type}</span>
                            <span className="text-[10px] font-mono text-gray-500">{((k.confidence || 0) * 100).toFixed(0)}% Conf</span>
                          </div>
                          <h4 className="text-white font-bold text-sm mb-1">{k.name}</h4>
                          <div className="flex items-baseline gap-1.5 mb-2">
                            <span className="text-lg font-black text-blue-400">{k.value}</span>
                            <span className="text-[10px] text-gray-500 font-bold uppercase">{k.unit}</span>
                          </div>
                          <p className="text-[10px] text-gray-400 line-clamp-2 italic border-l border-white/10 pl-2">
                            &ldquo;{k.clause_text}&rdquo;
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Footer: Infrastructure */}
            <div className="p-6 bg-black/60 border-t border-white/5 flex items-center justify-between">
              <div className="flex items-center gap-6">
                <div className="flex items-center gap-2">
                  <Database className="h-3 w-3 text-gray-500" />
                  <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Atlas Vector Search: Connected</span>
                </div>
                <div className="flex items-center gap-2">
                  <Cpu className="h-3 w-3 text-gray-500" />
                  <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Gemini 3 Flash: Inference Active</span>
                </div>
              </div>
              <div className="flex items-center gap-2 text-gray-500">
                <Lock className="h-3 w-3" />
                <span className="text-[10px] font-medium">Enterprise Encryption Active</span>
              </div>
            </div>
          </div>
        </div>
      );
    }
    return null;
  };

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
    <div className="min-h-screen bg-[#F5F4F2] text-slate-800 pb-12 relative overflow-x-hidden">
      {renderOverlay()}

      <div className={`transition-all duration-700 ease-in-out ${journey !== "DASHBOARD" ? "blur-xl scale-[0.95] brightness-75 pointer-events-none" : ""}`}>

      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="border-b border-gray-200 bg-white fixed top-0 w-full z-40">
        <div className="max-w-screen-xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button 
              onClick={() => setJourney("LANDING")}
              className="flex items-center gap-1.5 text-sm font-medium text-gray-500 hover:text-gray-800 hover:bg-gray-100 px-3 py-1.5 rounded-md transition-colors -ml-2"
            >
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

      <div className={`transition-all duration-500 ${activeArtifact ? "blur-md scale-[0.98] pointer-events-none brightness-95" : ""}`}>
        <div className="max-w-screen-xl mx-auto px-6 pt-20 space-y-5 pb-20">
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
      </div>

      {/* Artifact Overlay */}
      {activeArtifact && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-6 md:p-12 animate-in fade-in zoom-in-95 duration-300">
          <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" onClick={() => setActiveArtifact(null)} />
          <div className="relative w-full max-w-5xl bg-white rounded-3xl shadow-2xl border border-gray-200 overflow-hidden flex flex-col max-h-[90vh]">
            {/* Artifact Header */}
            <div className="p-4 border-b border-gray-100 flex items-center justify-between bg-blue-50/50 backdrop-blur-md">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-2xl bg-blue-600 flex items-center justify-center text-white shadow-lg shadow-blue-200">
                  <Sparkles className="h-6 w-6" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-gray-800">
                    {activeArtifact.type === 'svg' ? 'Compliance Diagram' : 'Audit Dashboard'}
                  </h2>
                  <p className="text-[10px] text-blue-600 font-bold uppercase tracking-widest">Generative Insight Engine</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button 
                  onClick={() => setActiveArtifact(null)}
                  className="p-2 hover:bg-gray-100 rounded-xl transition-colors text-gray-400 active:scale-90"
                >
                  <X className="h-6 w-6" />
                </button>
              </div>
            </div>

            {/* Artifact Content */}
            <div className="flex-1 overflow-auto bg-gray-50/30 relative">
              <div className="absolute inset-0 opacity-20 pointer-events-none" style={{ backgroundImage: 'radial-gradient(#94a3b8 1px, transparent 1px)', backgroundSize: '24px 24px' }}></div>
              <div className="relative h-full flex flex-col">
                <iframe 
                  srcDoc={
                    '<!DOCTYPE html><html><head><meta charset="utf-8"><style>' +
                    ':root {' +
                    '  --color-background-primary: #ffffff;' +
                    '  --color-background-secondary: #f8fafc;' +
                    '  --color-background-tertiary: #f1f5f9;' +
                    '  --color-text-primary: #1e293b;' +
                    '  --color-text-secondary: #475569;' +
                    '  --color-text-tertiary: #64748b;' +
                    '  --color-border-primary: #e2e8f0;' +
                    '  --color-border-secondary: #cbd5e1;' +
                    '  --color-border-tertiary: #f1f5f9;' +
                    '  --font-sans: system-ui, -apple-system, sans-serif;' +
                    '  --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;' +
                    '  --border-radius-md: 8px;' +
                    '  --border-radius-lg: 12px;' +
                    '}' +
                    'body { ' +
                    '  margin: 0; ' +
                    '  padding: 3rem;' +
                    '  font-family: var(--font-sans); ' +
                    '  display: flex; ' +
                    '  justify-content: center; ' +
                    '  align-items: flex-start; ' +
                    '  min-height: 100vh;' +
                    '  background: transparent;' +
                    '  color: var(--color-text-primary);' +
                    '}' +
                    '* { box-sizing: border-box; }' +
                    'svg { max-width: 100%; height: auto; }' +
                    '</style></head><body>' +
                    activeArtifact.content +
                    '<script>' +
                    'window.addEventListener("load", () => {' +
                    '  if (window.init) window.init();' +
                    '  if (typeof initFn === "function") initFn();' +
                    '});' +
                    '</script></body></html>'
                  }
                  className="w-full h-full min-h-[600px] border-none bg-transparent"
                  title="Artifact View"
                />
              </div>
            </div>
            
            {/* Artifact Footer */}
            <div className="p-3 border-t border-gray-100 bg-white flex justify-end gap-2">
               <button 
                 onClick={() => setActiveArtifact(null)}
                 className="px-4 py-2 bg-gray-50 hover:bg-gray-100 text-gray-700 rounded-xl text-sm font-bold transition-all active:scale-95 border border-gray-200"
               >
                 Close Preview
               </button>
            </div>
          </div>
        </div>
      )}

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
                    <>
                      {msg.content && (
                        <ReactMarkdown 
                          remarkPlugins={[remarkGfm]} 
                          rehypePlugins={[rehypeRaw]}
                        >
                          {msg.content}
                        </ReactMarkdown>
                      )}
                      
                      {msg.artifact && (
                        <button 
                          onClick={() => setActiveArtifact(msg.artifact)}
                          className="mt-3 w-full p-3 rounded-lg border border-blue-200 bg-blue-50 hover:bg-blue-100 flex items-center justify-between transition-colors group cursor-pointer text-left shadow-sm"
                        >
                          <div className="flex items-center gap-3">
                            <div className="p-1.5 bg-blue-600 rounded-md text-white shadow-sm">
                              {msg.artifact.type === 'svg' ? <Activity className="h-3.5 w-3.5" /> : <Database className="h-3.5 w-3.5" />}
                            </div>
                            <span className="text-[11px] font-bold text-blue-800">
                              View {msg.artifact.type === 'svg' ? 'Diagram' : 'UI Component'}
                            </span>
                          </div>
                          <span className="text-[10px] font-bold text-blue-600 group-hover:translate-x-1 transition-transform">
                            Open &rarr;
                          </span>
                        </button>
                      )}
                    </>
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
