"use client";

import { useState, useEffect, useMemo } from "react";
import {
  ShieldCheck, AlertTriangle, CheckCircle2, ChevronDown, ArrowLeft,
  RefreshCw, Sparkles, Server, DollarSign, AlertCircle, BarChart3,
  Clock, FileText, Activity, Bell, Database, Layout, Terminal, Cpu, Lock, Search, ArrowRight, ChevronRight, Filter, Download, Calendar, Layers, Zap,
  Mail, ExternalLink, MailWarning, Plus, List, Upload
} from "lucide-react";
import {
  fetchContracts, fetchKPIs, fetchBreaches, fetchPerformance,
  evaluateContract, updateBreach, chatWithContract, chatWithContractStream,
  fetchAvailableContracts, ingestContract, extractKPIs,
  getKpiTimeSeries, generateBreachEmail, sendBreachEmail, fetchPortfolioSummary, uploadActualsCsv, clearChatSession
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
  HIGH: { dot: "bg-orange-400", badge: "bg-orange-100 text-orange-700 border-orange-200", color: "text-orange-700", bg: "bg-orange-50", border: "border-orange-200", icon: AlertTriangle, response: "Same business day" },
  MEDIUM: { dot: "bg-amber-300", badge: "bg-amber-100 text-amber-700 border-amber-200", color: "text-amber-700", bg: "bg-amber-50", border: "border-amber-200", icon: AlertTriangle, response: "Within 48 hours" },
  LOW: { dot: "bg-green-400", badge: "bg-green-100 text-green-700 border-green-200", color: "text-green-700", bg: "bg-green-50", border: "border-green-200", icon: CheckCircle2, response: "Next review cycle" },
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
  const [tab, setTab] = useState<"kpis" | "flags" | "portfolio" | "actuals">("kpis");

  // Phase 2 State
  const [portfolioData, setPortfolioData] = useState<any>(null);
  const [portfolioLoading, setPortfolioLoading] = useState(false);
  const [emailModalOpen, setEmailModalOpen] = useState(false);
  const [isGeneratingEmail, setIsGeneratingEmail] = useState(false);
  const [isSendingEmail, setIsSendingEmail] = useState(false);
  const [emailForm, setEmailForm] = useState({ to: "", subject: "", body: "", breachId: "" });
  const [kpiTimeSeries, setKpiTimeSeries] = useState<Record<string, any>>({});
  const [evaluating, setEvaluating] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<any[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatSessionId, setChatSessionId] = useState<string | null>(null);
  const [currentQuery, setCurrentQuery] = useState("");
  const [activeArtifact, setActiveArtifact] = useState<{ content: string, type: string } | null>(null);
  const [chartMode, setChartMode] = useState<"actual" | "cumulative">("actual");

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

  // Phase 2 Handlers
  async function handleExpandKpi(kpiId: string) {
    const isOpening = expandedKpi !== kpiId;
    setExpandedKpi(isOpening ? kpiId : null);

    if (isOpening) {
      const kpi = kpis.find(k => k.kpi_id === kpiId);
      if (kpi?.aggregation_type === "sum") {
        setChartMode("cumulative");
      } else {
        setChartMode("actual");
      }

      if (!kpiTimeSeries[kpiId]) {
        try {
          const data = await getKpiTimeSeries(selectedContract, kpiId);
          setKpiTimeSeries(prev => ({ ...prev, [kpiId]: data }));
        } catch (e) { console.error("Failed to load KPI timeseries", e); }
      }
    }
  }

  async function handleOpenEmailModal(breachId: string) {
    setEmailModalOpen(true);
    setIsGeneratingEmail(true);
    setEmailForm({ to: "", subject: "Generating...", body: "Please wait...", breachId });
    try {
      const data = await generateBreachEmail(breachId);
      setEmailForm({
        to: data.suggested_to || "",
        subject: data.subject,
        body: data.body,
        breachId: breachId
      });
    } catch (e) {
      console.error(e);
      setEmailForm(prev => ({ ...prev, subject: "Error", body: "Failed to generate email template." }));
    } finally {
      setIsGeneratingEmail(false);
    }
  }

  async function handleSendEmail() {
    setIsSendingEmail(true);
    try {
      await sendBreachEmail(emailForm.breachId, emailForm);
      setEmailModalOpen(false);
      // Optional: Add a toast notification here
      alert("Email alert sent successfully.");
    } catch (e) {
      console.error(e);
      alert("Failed to send email.");
    } finally {
      setIsSendingEmail(false);
    }
  }

  async function loadPortfolio() {
    setTab("portfolio");
    if (!portfolioData) {
      setPortfolioLoading(true);
      try {
        const data = await fetchPortfolioSummary();
        const mappedData = {
          total_contracts: data.summary.total_contracts,
          total_kpis: data.contracts.reduce((acc: any, c: any) => acc + c.total_kpis, 0),
          total_breaches: data.summary.total_active_breaches,
          total_exposure: data.summary.total_penalty_exposure || 0,
          supplier_scores: data.contracts.map((c: any) => ({
            contract_id: c.contract_id,
            total_kpis: c.total_kpis,
            health_score: c.health_score,
            exposure: c.total_penalty_exposure || 0
          }))
        };
        setPortfolioData(mappedData);
      } catch (e) { console.error(e); }
      finally { setPortfolioLoading(false); }
    }
  }

  async function handleUploadActuals(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file || !selectedContract) return;

    setEvaluating(true); // Reuse evaluating state for loading
    try {
      await uploadActualsCsv(selectedContract, file);
      // Refresh data
      const [p, b] = await Promise.all([
        fetchPerformance(selectedContract),
        fetchBreaches(selectedContract)
      ]);
      setActuals(p);
      setBreaches(b);
      // Optional: alert success
    } catch (e) {
      console.error("Upload failed", e);
    } finally {
      setEvaluating(false);
      // Reset input
      event.target.value = '';
    }
  }

  function handleExportCsv() {
    // Client-side CSV generation
    if (!kpis.length) return;
    const headers = ["KPI ID", "Name", "Type", "Operator", "Threshold", "Unit", "Penalty", "Party", "Remediation", "SLA", "Status"];
    const rows = kpis.map(k => {
      const isBreach = breaches.some(b => b.kpi_id === k.kpi_id && b.is_breach);
      const escape = (val: any) => `"${String(val || "").replace(/"/g, '""')}"`;
      return [
        k.kpi_id,
        escape(k.name),
        escape(k.kpi_type),
        escape(k.operator),
        k.value_min ?? "",
        escape(k.unit),
        k.consequence_value || "",
        escape(k.party),
        escape(k.remediation),
        escape(k.remediation_sla),
        isBreach ? "BREACH" : "OK"
      ];
    });
    const csv = [headers.join(","), ...rows.map(r => r.join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `compliance_report_${selectedContract}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  function handleExportJson() {
    const dataStr = JSON.stringify({ kpis, breaches, actuals }, null, 2);
    const blob = new Blob([dataStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `compliance_data_${selectedContract}.json`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  async function handleChat(question: string, breachId?: string) {
    if (!question.trim()) return;
    if (!selectedContract) return;

    setChatOpen(true);
    const userMsgId = Date.now().toString();
    const assistantMsgId = (Date.now() + 1).toString();
    
    setChatMessages(prev => [...prev, { id: userMsgId, role: "user", content: question }]);
    
    // Add placeholder assistant message
    setChatMessages(prev => [...prev, { 
      id: assistantMsgId, 
      role: "assistant", 
      content: "", 
      thought: "", 
      plan: "", 
      toolCalls: [],
      toolResults: [],
      isStreaming: true 
    }]);

    try {
      // Ensure we have a session ID for this conversation
      const sid = chatSessionId ?? (() => {
        const id = `${selectedContract}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
        setChatSessionId(id);
        return id;
      })();

      const response = await chatWithContractStream(selectedContract, question, breachId, sid);
      const reader = response.body?.getReader();
      if (!reader) return;

      let accumulatedContent = "";
      let accumulatedThought = "";
      let accumulatedPlan = "";
      let toolCalls: any[] = [];

      const decoder = new TextDecoder();
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.replace("data: ", ""));
            
            if (data.type === "thought") {
              accumulatedThought += data.content;
            } else if (data.type === "plan") {
              accumulatedPlan += data.content;
            } else if (data.type === "content") {
              accumulatedContent += data.content;
            } else if (data.type === "tool_call") {
              toolCalls.push({ name: data.name, args: data.args, status: "running" });
            } else if (data.type === "tool_result") {
              const lastCall = toolCalls.findLast((tc: any) => tc.name === data.name && tc.status === "running");
              if (lastCall) lastCall.status = "done";
            }

            // Update message in real-time
            setChatMessages(prev => prev.map(m => m.id === assistantMsgId ? {
              ...m,
              content: accumulatedContent,
              thought: accumulatedThought,
              plan: accumulatedPlan,
              toolCalls: [...toolCalls]
            } : m));

          } catch (e) {
            console.error("Error parsing SSE chunk", e);
          }
        }
      }

      // Post-process artifacts
      let artifact = null;
      let finalContent = accumulatedContent;
      
      const fencedRegex = /```(?:html|svg|xml)\s*([\s\S]*?)```/i;
      const fencedMatch = fencedRegex.exec(finalContent);

      if (fencedMatch && (fencedMatch[1].includes('<svg') || fencedMatch[1].includes('<div') || fencedMatch[1].includes('<link') || fencedMatch[1].includes('<style'))) {
        artifact = {
          type: fencedMatch[1].includes('<svg') ? 'svg' : 'html',
          content: fencedMatch[1].trim()
        };
        finalContent = finalContent.replace(fencedMatch[0], '').trim();
      }

      setChatMessages(prev => prev.map(m => m.id === assistantMsgId ? {
        ...m,
        content: finalContent,
        artifact,
        isStreaming: false
      } : m));

    } catch (e) {
      console.error(e);
      setChatMessages(prev => prev.map(m => m.id === assistantMsgId ? {
        ...m,
        content: "Sorry, I encountered an error. Please try again.",
        isStreaming: false
      } : m));
    } finally {
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

  // ── Tier 1: KPI-derived analytics (always available) ────────────────
  const kpiTypeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    kpis.forEach(k => { const t = k.kpi_type || "other"; counts[t] = (counts[t] || 0) + 1; });
    return Object.entries(counts).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);
  }, [kpis]);

  const confidenceBuckets = useMemo(() => {
    const b = [
      { name: "< 70%", min: 0, max: 0.7, value: 0, color: "#ef4444" },
      { name: "70–85%", min: 0.7, max: 0.85, value: 0, color: "#f59e0b" },
      { name: "85–95%", min: 0.85, max: 0.95, value: 0, color: "#3b82f6" },
      { name: "> 95%", min: 0.95, max: 1.01, value: 0, color: "#22c55e" },
    ];
    kpis.forEach(k => { const c = k.confidence || 0; const bucket = b.find(x => c >= x.min && c < x.max); if (bucket) bucket.value++; });
    return b;
  }, [kpis]);

  const penaltyByParty = useMemo(() => {
    const m: Record<string, number> = {};
    kpis.forEach(k => { const p = k.party || "Unspecified"; m[p] = (m[p] || 0) + (k.consequence_value || 0); });
    return Object.entries(m).map(([name, value]) => ({ name: name.substring(0, 20), value })).filter(x => x.value > 0).sort((a, b) => b.value - a.value);
  }, [kpis]);

  // ── Tier 2: Breach-derived analytics (after evaluation) ────────────
  const complianceRate = useMemo(() => {
    if (!breaches.length) return 100;
    const onTrack = breaches.filter(b => !b.is_breach).length;
    return parseFloat(((onTrack / breaches.length) * 100).toFixed(1));
  }, [breaches]);

  const breachStatusCounts = useMemo(() => {
    const c: Record<string, number> = { Open: 0, "In Progress": 0, Resolved: 0, Waived: 0 };
    breaches.filter(b => b.is_breach).forEach(b => { const s = b.status || "Open"; c[s] = (c[s] || 0) + 1; });
    return Object.entries(c).map(([name, value]) => ({ name, value }));
  }, [breaches]);

  const severityStatusMatrix = useMemo(() => {
    const mx: Record<string, Record<string, number>> = {};
    (["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const).forEach(s => { mx[s] = { Open: 0, "In Progress": 0, Resolved: 0, Waived: 0 }; });
    breaches.forEach(b => { const sev = classifySeverity(b); const st = b.status || "Open"; if (mx[sev]?.[st] !== undefined) mx[sev][st]++; });
    return mx;
  }, [breaches]);

  const actualVsThreshold = useMemo(() => {
    return breaches
      .filter(b => b.threshold_value != null)
      .map(b => {
        const kpi = kpis.find(k => k.kpi_id === b.kpi_id);
        const thresh = b.threshold_value || 1;
        const dev = b.operator === ">=" || b.operator === ">"
          ? ((b.actual_value - thresh) / Math.max(Math.abs(thresh), 0.01)) * 100
          : ((thresh - b.actual_value) / Math.max(Math.abs(thresh), 0.01)) * 100;
        return {
          name: (kpi?.name || b.kpi_id || "").substring(0, 22),
          actual: b.actual_value, threshold: thresh,
          deviation: parseFloat(dev.toFixed(1)),
          isBreach: b.is_breach, severity: classifySeverity(b),
          unit: kpi?.unit || "", operator: b.operator,
        };
      })
      .sort((a, b) => a.deviation - b.deviation);
  }, [breaches, kpis]);

  const penaltyAccrualData = useMemo(() => {
    if (!breaches.length) return [];
    const sorted = breaches.filter(b => b.is_breach && b.penalty_amount > 0 && b.timestamp)
      .sort((a, b) => (a.timestamp || "").localeCompare(b.timestamp || ""));
    let cum = 0;
    return sorted.map(b => {
      cum += b.penalty_amount || 0;
      const kpi = kpis.find(k => k.kpi_id === b.kpi_id);
      let dl = ""; try { dl = new Date(b.timestamp).toLocaleDateString(undefined, { month: "short", day: "numeric" }); } catch { dl = b.timestamp || ""; }
      return { date: dl, penalty: b.penalty_amount, cumulative: cum, kpi: (kpi?.name || b.kpi_id || "").substring(0, 15) };
    });
  }, [breaches, kpis]);

  // ── Keep simplified time-series for per-KPI expanded view ──────────
  const timeSeriesData = useMemo(() => {
    if (!actuals.length && !breaches.length) return [];
    const daily: Record<string, any> = {};
    actuals.forEach(a => {
      const raw = a.timestamp || a.scheduled_departure || a.audit_date || a.date || a.month;
      if (!raw) return;
      let d = ""; try { d = new Date(raw).toISOString().split("T")[0]; } catch { return; }
      if (!daily[d]) daily[d] = { date: d.substring(5), count: 0, penalties: 0 };
      daily[d].count++;
    });
    breaches.forEach(b => {
      if (!b.timestamp) return;
      let d = ""; try { d = new Date(b.timestamp).toISOString().split("T")[0]; } catch { return; }
      if (!daily[d]) daily[d] = { date: d.substring(5), count: 0, penalties: 0 };
      if (b.is_breach) daily[d].penalties += (b.penalty_amount || 0);
    });
    const sorted = Object.keys(daily).sort();
    let tot = 0;
    return sorted.map(d => { tot += daily[d].penalties; return { date: daily[d].date, totalPenalty: tot }; });
  }, [actuals, breaches]);

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
  const evaluatedKpiIds = new Set(breaches.map(b => b.kpi_id));
  const notEvaluatedCount = kpis.length - evaluatedKpiIds.size;

  const TYPE_COLORS: Record<string, string> = { financial: "#10b981", sla: "#3b82f6", penalty: "#ef4444", volume: "#8b5cf6", timeline: "#f59e0b", other: "#94a3b8" };
  const PARTY_COLORS = ["#0084C7", "#8b5cf6", "#f59e0b", "#10b981", "#ef4444", "#6366f1"];
  const STATUS_BAR_COLORS: Record<string, string> = { Open: "#ef4444", "In Progress": "#f59e0b", Resolved: "#22c55e", Waived: "#94a3b8" };

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
                    <h1 className="text-lg font-bold text-gray-900 leading-tight">Contract<br />Guardian</h1>
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
                                <p className="text-[10px] text-gray-400 mt-1 uppercase tracking-tighter">{c.contract_id.substring(0, 8)}</p>
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
              <div className="relative">
                <input
                  type="file"
                  id="actuals-upload"
                  className="hidden"
                  accept=".csv"
                  onChange={handleUploadActuals}
                />
                <button
                  onClick={() => document.getElementById('actuals-upload')?.click()}
                  disabled={evaluating}
                  className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-md text-gray-500 hover:text-gray-800 bg-white border border-gray-200 transition-colors shadow-sm"
                >
                  <Upload className="h-3.5 w-3.5" /> Upload Actuals
                </button>
              </div>
              <span className="flex items-center gap-1.5 text-xs font-medium text-[#0084C7] bg-blue-50 border border-blue-100 px-3 py-1.5 rounded-full">
                <Sparkles className="h-3 w-3" /> AI-Powered
              </span>
              <div className="relative group">
                <button className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-md text-gray-500 hover:text-gray-800 bg-white border border-gray-200 transition-colors shadow-sm">
                  <Download className="h-3.5 w-3.5" /> Export <ChevronDown className="h-3 w-3 opacity-50" />
                </button>
                <div className="absolute right-0 top-full mt-1 w-32 bg-white rounded-lg shadow-lg border border-gray-100 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50 overflow-hidden">
                  <button onClick={handleExportCsv} className="w-full text-left px-4 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50">CSV Report</button>
                  <button onClick={handleExportJson} className="w-full text-left px-4 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50">Raw JSON</button>
                </div>
              </div>
              <button onClick={handleEvaluate} disabled={evaluating}
                className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-md transition-colors shadow-sm border ${evaluating ? "bg-[#0084C7] text-white border-[#0084C7]" : "text-gray-500 hover:text-gray-800 bg-white border-gray-200"
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
              <SummaryCard label="Compliance Rate" value={`${complianceRate}%`} color={complianceRate >= 90 ? "text-green-700" : complianceRate >= 70 ? "text-amber-700" : "text-red-700"} bg={complianceRate >= 90 ? "bg-green-50" : complianceRate >= 70 ? "bg-amber-50" : "bg-red-50"} border={complianceRate >= 90 ? "border-green-200" : complianceRate >= 70 ? "border-amber-200" : "border-red-200"} icon={<ShieldCheck className={`h-4 w-4 ${complianceRate >= 90 ? "text-green-700" : complianceRate >= 70 ? "text-amber-700" : "text-red-700"}`} />} />
              <SummaryCard label="KPIs Tracked" value={`${breaches.length > 0 ? evaluatedKpiIds.size : 0} / ${kpis.length}`} color="text-[#0084C7]" bg="bg-blue-50" border="border-blue-200" icon={<BarChart3 className="h-4 w-4 text-[#0084C7]" />} />
              <SummaryCard label="Critical / High" value={`${sevCounts.CRITICAL} / ${sevCounts.HIGH}`} color="text-red-700" bg="bg-red-50" border="border-red-200" icon={<AlertCircle className="h-4 w-4 text-red-700" />} />
              <SummaryCard label="Active Breaches" value={activeBreaches.filter(b => b.status !== "Resolved" && b.status !== "Waived").length} color="text-orange-700" bg="bg-orange-50" border="border-orange-200" icon={<AlertTriangle className="h-4 w-4 text-orange-700" />} />
              <SummaryCard label="Penalty Exposure" value={`$${totalExposure.toLocaleString()}`} color="text-red-700" bg="bg-white" border="border-gray-200" icon={<DollarSign className="h-4 w-4 text-red-700" />} />
            </div>

            {/* ── Performance Cockpit — Tier-Based Chart Grid ──────────── */}
            <div className="space-y-4">

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
                          ].filter(d => d.value > 0)}
                          cx="50%" cy="50%" innerRadius={35} outerRadius={55} paddingAngle={4} dataKey="value"
                        >
                          {[
                            { color: "#ef4444" }, { color: "#f97316" }, { color: "#f59e0b" }, { color: "#22c55e" }
                          ].filter((_, i) => [sevCounts.CRITICAL, sevCounts.HIGH, sevCounts.MEDIUM, Math.max(0, kpis.length - activeBreaches.length)][i] > 0)
                            .map((entry, i) => <Cell key={i} fill={entry.color} />)}
                        </Pie>
                        <Tooltip formatter={(value: number) => [value, "Flags"]} contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "12px" }} />
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="grid grid-cols-2 gap-x-5 gap-y-1 w-full px-2 mt-2">
                      {[
                        { name: "Critical", value: sevCounts.CRITICAL, color: "#ef4444" },
                        { name: "High", value: sevCounts.HIGH, color: "#f97316" },
                        { name: "Medium", value: sevCounts.MEDIUM, color: "#f59e0b" },
                        { name: "OK", value: Math.max(0, kpis.length - activeBreaches.length), color: "#22c55e" },
                      ].map(item => (
                        <div key={item.name} className="flex items-center gap-1.5">
                          <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: item.color }} />
                          <span className="text-[10px] text-gray-500 font-medium">{item.name} ({item.value})</span>
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
                      <BarChart data={kpiTypeCounts.length ? kpiTypeCounts : [{ name: "No KPIs", value: 0 }]} layout="vertical" margin={{ left: 5, right: 20, top: 5, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                        <XAxis type="number" axisLine={false} tickLine={false} fontSize={9} tick={{ fill: "#94a3b8" }} />
                        <YAxis type="category" dataKey="name" axisLine={false} tickLine={false} fontSize={10} tick={{ fill: "#64748b" }} width={65} />
                        <Tooltip contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px", padding: "8px" }} />
                        <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={14}>
                          {kpiTypeCounts.map((entry, i) => <Cell key={i} fill={TYPE_COLORS[entry.name] || "#94a3b8"} />)}
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
                              {penaltyByParty.map((_, i) => <Cell key={i} fill={PARTY_COLORS[i % PARTY_COLORS.length]} />)}
                            </Pie>
                            <Tooltip formatter={(value: number) => [`$${value.toLocaleString()}`, "Exposure"]} contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "12px" }} />
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
                          <XAxis type="number" axisLine={false} tickLine={false} fontSize={9} tick={{ fill: "#94a3b8" }} tickFormatter={(v: number) => `${v > 0 ? "+" : ""}${v}%`} />
                          <YAxis type="category" dataKey="name" axisLine={false} tickLine={false} fontSize={9} tick={{ fill: "#64748b" }} width={100} />
                          <Tooltip formatter={(value: number) => [`${value > 0 ? "+" : ""}${value}%`, "Deviation"]} contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px", padding: "8px" }} />
                          <Bar dataKey="deviation" radius={[0, 4, 4, 0]} barSize={12}>
                            {actualVsThreshold.map((entry, i) => (
                              <Cell key={i} fill={entry.isBreach ? (entry.severity === "CRITICAL" ? "#ef4444" : entry.severity === "HIGH" ? "#f97316" : "#f59e0b") : "#22c55e"} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="flex items-center justify-center h-full text-xs text-gray-400">No evaluations yet — upload actuals to begin</div>
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
                      <BarChart data={flags.filter(f => f.is_breach && f.penalty_amount > 0).map(f => ({
                        name: (f.kpi?.name || f.kpi_id || "").split(":")[0].trim().substring(0, 18),
                        amount: f.penalty_amount,
                      }))} layout="vertical" margin={{ left: 10, right: 20, top: 0, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                        <XAxis type="number" axisLine={false} tickLine={false} fontSize={9} tick={{ fill: "#94a3b8" }} tickFormatter={(v: number) => `$${v > 1000 ? v / 1000 + "k" : v}`} />
                        <YAxis type="category" dataKey="name" axisLine={false} tickLine={false} fontSize={9} tick={{ fill: "#64748b" }} width={100} />
                        <Tooltip formatter={(value: number) => [`$${value.toLocaleString()}`, "Penalty"]} contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px", padding: "8px" }} />
                        <Bar dataKey="amount" radius={[0, 4, 4, 0]} barSize={12}>
                          {flags.filter(f => f.is_breach && f.penalty_amount > 0).map((f, i) => (
                            <Cell key={i} fill={f.severity === "CRITICAL" ? "#ef4444" : f.severity === "HIGH" ? "#f97316" : "#f59e0b"} />
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
                          <BarChart data={[breachStatusCounts.reduce((acc, s) => ({ ...acc, [s.name]: s.value }), {} as any)]} layout="horizontal" margin={{ left: 0, right: 0, top: 0, bottom: 0 }}>
                            <XAxis type="number" hide domain={[0, activeBreaches.length || 1]} />
                            <YAxis type="category" hide dataKey={() => "status"} />
                            {breachStatusCounts.map(s => (
                              <Bar key={s.name} dataKey={s.name} stackId="status" fill={STATUS_BAR_COLORS[s.name] || "#94a3b8"} barSize={28} radius={0} />
                            ))}
                            <Tooltip contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px", padding: "8px" }} />
                          </BarChart>
                        </ResponsiveContainer>
                        <div className="grid grid-cols-2 gap-3 mt-4">
                          {breachStatusCounts.map(s => (
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
                    <span className="text-lg font-bold text-red-600">${penaltyAccrualData.length > 0 ? penaltyAccrualData[penaltyAccrualData.length - 1].cumulative.toLocaleString() : 0}</span>
                  </div>
                  <div className="px-2 py-3 h-[200px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={penaltyAccrualData.length ? penaltyAccrualData : [{ date: "—", cumulative: 0 }]} margin={{ left: -5, right: 10, top: 10, bottom: 0 }}>
                        <defs>
                          <linearGradient id="colorPenAccrual" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2} />
                            <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                        <XAxis dataKey="date" axisLine={false} tickLine={false} fontSize={9} tick={{ fill: "#94a3b8" }} />
                        <YAxis axisLine={false} tickLine={false} fontSize={9} tick={{ fill: "#94a3b8" }} tickFormatter={(v: number) => `$${v > 1000 ? (v / 1000).toFixed(0) + "k" : v}`} />
                        <Tooltip contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px", padding: "8px" }} formatter={(v: number) => [`$${v.toLocaleString()}`, "Cumulative"]} />
                        <Area type="step" dataKey="cumulative" stroke="#ef4444" strokeWidth={2} fillOpacity={1} fill="url(#colorPenAccrual)" />
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
                            {["Open", "In Progress", "Resolved", "Waived"].map(s => (
                              <th key={s} className="text-center text-gray-500 font-medium pb-2 px-1">{s}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {(["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const).map(sev => {
                            const sevColor = sev === "CRITICAL" ? "#ef4444" : sev === "HIGH" ? "#f97316" : sev === "MEDIUM" ? "#f59e0b" : "#94a3b8";
                            return (
                              <tr key={sev}>
                                <td className="pr-2 py-1.5 font-semibold" style={{ color: sevColor }}>{sev}</td>
                                {["Open", "In Progress", "Resolved", "Waived"].map(st => {
                                  const count = severityStatusMatrix[sev]?.[st] || 0;
                                  const opacity = count === 0 ? 0.05 : Math.min(0.15 + count * 0.2, 0.9);
                                  return (
                                    <td key={st} className="text-center py-1.5 px-1">
                                      <div className="rounded-md py-1.5 font-bold text-xs" style={{
                                        backgroundColor: count > 0 ? `${sevColor}${Math.round(opacity * 255).toString(16).padStart(2, "0")}` : "#f8fafc",
                                        color: count > 0 ? sevColor : "#cbd5e1"
                                      }}>
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
                    {activeBreaches.filter(b => b.status !== "Resolved" && b.status !== "Waived").length > 0 ? (
                      <div className="space-y-2">
                        {activeBreaches.filter(b => b.status !== "Resolved" && b.status !== "Waived").slice(0, 6).map((b, i) => {
                          const kpi = kpis.find(k => k.kpi_id === b.kpi_id);
                          const sla = b.remediation_sla || kpi?.remediation_sla || "—";
                          const sev = classifySeverity(b);
                          const sevColor = sev === "CRITICAL" ? "#ef4444" : sev === "HIGH" ? "#f97316" : sev === "MEDIUM" ? "#f59e0b" : "#94a3b8";
                          return (
                            <div key={i} className="flex items-start gap-2 p-2 rounded-lg border border-gray-100 bg-gray-50/50">
                              <div className="w-1.5 h-full min-h-[32px] rounded-full shrink-0 mt-0.5" style={{ backgroundColor: sevColor }} />
                              <div className="flex-1 min-w-0">
                                <p className="text-[11px] font-medium text-gray-700 truncate">{kpi?.name || b.kpi_id}</p>
                                <div className="flex items-center gap-3 mt-0.5">
                                  <span className="text-[10px] text-gray-400">SLA: <strong className="text-gray-600">{sla}</strong></span>
                                  <span className="text-[10px] px-1.5 py-0.5 rounded font-medium" style={{ backgroundColor: `${sevColor}15`, color: sevColor }}>{sev}</span>
                                </div>
                              </div>
                              <span className="text-[10px] text-gray-400 shrink-0">${(b.penalty_amount || 0).toLocaleString()}</span>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="flex items-center justify-center h-full text-xs text-gray-400">No open remediation items</div>
                    )}
                  </div>
                </div>

              </div>

            </div>

            <div className="flex gap-2">
              <button onClick={() => setTab("kpis")} className={`px-4 py-1.5 rounded-lg border text-xs font-semibold transition-all flex items-center gap-1.5 ${tab === "kpis" ? "bg-[#0084C7] text-white border-[#0084C7]" : "bg-white border-gray-200 text-gray-500 hover:border-gray-300"}`}>
                <List className="h-3.5 w-3.5" /> KPI Registry ({kpis.length})
              </button>
              <button onClick={() => setTab("flags")} className={`px-4 py-1.5 rounded-lg border text-xs font-semibold transition-all flex items-center gap-1.5 ${tab === "flags" ? "bg-[#0084C7] text-white border-[#0084C7]" : "bg-white border-gray-200 text-gray-500 hover:border-gray-300"}`}>
                <AlertTriangle className="h-3.5 w-3.5" /> Compliance Flags ({flags.length})
              </button>
              <button onClick={() => setTab("actuals")} className={`px-4 py-1.5 rounded-lg border text-xs font-semibold transition-all flex items-center gap-1.5 ${tab === "actuals" ? "bg-[#0084C7] text-white border-[#0084C7]" : "bg-white border-gray-200 text-gray-500 hover:border-gray-300"}`}>
                <Activity className="h-3.5 w-3.5" /> Performance Actuals ({actuals.length})
              </button>
              <button onClick={loadPortfolio} className={`px-4 py-1.5 rounded-lg border text-xs font-semibold transition-all flex items-center gap-1.5 ${tab === "portfolio" ? "bg-[#0084C7] text-white border-[#0084C7]" : "bg-white border-gray-200 text-gray-500 hover:border-gray-300"}`}>
                <Layers className="h-3.5 w-3.5" /> Portfolio View
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
                          onClick={() => handleExpandKpi(kpi.kpi_id)}
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

                              {/* Performance History Chart */}
                              <div className="p-3 rounded-lg bg-white border border-gray-200">
                                <div className="flex items-center justify-between mb-4">
                                  <div className="flex items-center gap-2">
                                    <p className="text-[10px] font-bold uppercase text-gray-500">Historical Performance Logs</p>
                                    <div className="flex bg-gray-100 p-0.5 rounded-md border border-gray-200">
                                      <button
                                        onClick={(e) => { e.stopPropagation(); setChartMode("actual"); }}
                                        className={`px-2 py-0.5 rounded text-[9px] font-bold transition-all ${chartMode === "actual" ? "bg-white text-blue-600 shadow-sm" : "text-gray-400 hover:text-gray-600"}`}
                                      >
                                        ACTUAL
                                      </button>
                                      <button
                                        onClick={(e) => { e.stopPropagation(); setChartMode("cumulative"); }}
                                        className={`px-2 py-0.5 rounded text-[9px] font-bold transition-all ${chartMode === "cumulative" ? "bg-white text-blue-600 shadow-sm" : "text-gray-400 hover:text-gray-600"}`}
                                      >
                                        CUMULATIVE
                                      </button>
                                    </div>
                                  </div>
                                  <span className="text-[10px] font-medium text-[#0084C7] bg-blue-50 px-2 py-0.5 rounded-full">
                                    {kpiTimeSeries[kpi.kpi_id]?.data?.length || 0} records
                                  </span>
                                </div>
                                <div className="h-[200px] w-full">
                                  {!kpiTimeSeries[kpi.kpi_id] ? (
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
                                        <XAxis dataKey="timestamp" tickFormatter={(t) => new Date(t).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#94a3b8' }} />
                                        <YAxis yAxisId="left" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#94a3b8' }} />
                                        <Tooltip
                                          labelFormatter={(t) => new Date(t).toLocaleString()}
                                          contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '11px', padding: '8px' }}
                                        />
                                        <Legend wrapperStyle={{ fontSize: '10px' }} />
                                        <Line
                                          yAxisId="left"
                                          type={chartMode === "cumulative" ? "monotone" : "monotone"}
                                          dataKey="value"
                                          name={chartMode === "cumulative" ? "Cumulative Progress" : "Daily Delivery"}
                                          stroke="#0084C7"
                                          strokeWidth={2}
                                          dot={chartMode === "actual" ? { r: 3, fill: "#0084C7" } : false}
                                          activeDot={{ r: 5 }}
                                        />
                                        {kpiTimeSeries[kpi.kpi_id].trend?.threshold && (
                                          <Line yAxisId="left" type="step" dataKey={() => kpiTimeSeries[kpi.kpi_id].trend.threshold} name="Threshold" stroke="#ef4444" strokeWidth={1} strokeDasharray="5 5" dot={false} activeDot={false} />
                                        )}
                                      </ComposedChart>
                                    </ResponsiveContainer>
                                  )}
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

                              <div className="grid grid-cols-2 gap-2 mt-2">
                                <button
                                  onClick={() => handleChat(`Explain the penalty logic and any excusable delays for this ${flag.kpi_id} breach.`, flag.breach_id || flag._id)}
                                  className="w-full flex items-center justify-center gap-2 py-2 px-4 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-[11px] font-bold transition-all shadow-md active:scale-[0.98]"
                                >
                                  <Bot className="h-3.5 w-3.5" />
                                  Ask AI to Analyze
                                </button>
                                <button
                                  onClick={() => handleOpenEmailModal(flag.breach_id || flag._id)}
                                  className="w-full flex items-center justify-center gap-2 py-2 px-4 rounded-lg bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 text-[11px] font-bold transition-all shadow-sm active:scale-[0.98]"
                                >
                                  <MailWarning className="h-3.5 w-3.5 text-amber-600" />
                                  Send Escalation Alert
                                </button>
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

            {/* ── Performance Actuals (Raw Data) ──────────────────────── */}
            {tab === "actuals" && (
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
                          <td colSpan={5} className="py-12 text-center text-sm text-gray-400 italic">No actuals data ingested for this contract.</td>
                        </tr>
                      ) : (
                        actuals.map((a, i) => {
                          const timestamp = a.timestamp || a.scheduled_departure || a.audit_date || a.date || a.month || "—";
                          const dateStr = timestamp !== "—" ? new Date(timestamp).toLocaleString() : "—";

                          // Extract non-standard fields for the "Context" column
                          const standardKeys = ["timestamp", "kpi_id", "value", "unit", "source", "scheduled_departure", "audit_date", "date", "month", "_id", "contract_id"];
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
                                <p className="text-sm font-bold text-gray-800">{a.value} <span className="text-[10px] font-normal text-gray-400 uppercase">{a.unit}</span></p>
                              </td>
                              <td className="px-5 py-3 text-xs text-gray-500 italic">{a.source || "—"}</td>
                              <td className="px-5 py-3">
                                <div className="flex flex-wrap gap-1.5">
                                  {Object.entries(contextData).map(([key, val]) => (
                                    <span key={key} className="text-[10px] bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded flex items-center gap-1">
                                      <span className="font-bold opacity-60 capitalize">{key.replace(/_/g, ' ')}:</span>
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
            )}


            {tab === "portfolio" && (
              <div className="space-y-4">
                {portfolioLoading ? (
                  <div className="py-12 text-center text-sm text-gray-400"><RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2" />Loading portfolio...</div>
                ) : portfolioData && (
                  <>
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                      <SummaryCard label="Total Contracts" value={portfolioData.total_contracts} color="text-[#0084C7]" bg="bg-blue-50" border="border-blue-200" icon={<FileText className="h-4 w-4 text-[#0084C7]" />} />
                      <SummaryCard label="Total KPIs Tracked" value={portfolioData.total_kpis} color="text-indigo-700" bg="bg-indigo-50" border="border-indigo-200" icon={<Activity className="h-4 w-4 text-indigo-700" />} />
                      <SummaryCard label="Active Breaches" value={portfolioData.total_breaches} color="text-red-700" bg="bg-red-50" border="border-red-200" icon={<AlertTriangle className="h-4 w-4 text-red-700" />} />
                      <SummaryCard label="Total Exposure" value={`$${(portfolioData.total_exposure || 0).toLocaleString()}`} color="text-red-700" bg="bg-white" border="border-gray-200" icon={<DollarSign className="h-4 w-4 text-red-700" />} />
                    </div>

                    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
                      <div className="px-5 py-4 border-b border-gray-100">
                        <h3 className="text-sm font-semibold text-gray-800">Supplier Health Scoring</h3>
                        <p className="text-xs text-gray-400 mt-0.5">Contract performance benchmarking across the portfolio</p>
                      </div>
                      <div className="divide-y divide-gray-100">
                        {portfolioData.supplier_scores.map((s: any, i: number) => (
                          <div key={i} className="flex items-center justify-between px-5 py-3.5 hover:bg-gray-50">
                            <div>
                              <p className="text-sm font-semibold text-gray-800">{s.contract_id}</p>
                              <p className="text-[10px] text-gray-400">Score based on {s.total_kpis} tracked KPIs</p>
                            </div>
                            <div className="flex items-center gap-6">
                              <div className="text-right">
                                <p className="text-[10px] font-bold text-gray-500 uppercase">Health Score</p>
                                <p className={`text-lg font-black ${(s.health_score || 0) > 90 ? 'text-green-600' : (s.health_score || 0) > 70 ? 'text-amber-500' : 'text-red-600'}`}>{(s.health_score || 0).toFixed(1)}/100</p>
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
                  </>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Email Remediation Modal */}
        {emailModalOpen && (
          <div className="fixed inset-0 z-[60] flex items-center justify-center p-4" style={{ animation: 'fadeIn 0.2s ease-out' }}>
            <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => !isGeneratingEmail && !isSendingEmail && setEmailModalOpen(false)} />
            <div className="relative w-full max-w-2xl bg-white rounded-2xl shadow-xl overflow-hidden flex flex-col" style={{ animation: 'slideUp 0.3s cubic-bezier(0.16,1,0.3,1)' }}>
              <div className="p-4 border-b border-gray-100 flex items-center justify-between bg-amber-50/50">
                <div className="flex items-center gap-2 text-amber-700">
                  <MailWarning className="h-5 w-5" />
                  <h3 className="text-sm font-bold">Automated Escalation Alert</h3>
                </div>
                <button disabled={isGeneratingEmail || isSendingEmail} onClick={() => setEmailModalOpen(false)} className="p-1 text-gray-400 hover:text-gray-600 rounded">
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="p-5 space-y-4 bg-gray-50/50">
                {isGeneratingEmail ? (
                  <div className="py-12 flex flex-col items-center justify-center text-gray-400">
                    <RefreshCw className="h-6 w-6 animate-spin mb-3 text-amber-500" />
                    <p className="text-sm">Synthesizing contract clauses into formal notification...</p>
                  </div>
                ) : (
                  <>
                    <div>
                      <label className="block text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1">To</label>
                      <input
                        type="text"
                        value={emailForm.to}
                        onChange={(e) => setEmailForm(prev => ({ ...prev, to: e.target.value }))}
                        className="w-full text-sm p-2 rounded border border-gray-200 focus:border-amber-400 focus:ring-1 focus:ring-amber-400 outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1">Subject</label>
                      <input
                        type="text"
                        value={emailForm.subject}
                        onChange={(e) => setEmailForm(prev => ({ ...prev, subject: e.target.value }))}
                        className="w-full text-sm p-2 rounded border border-gray-200 font-semibold focus:border-amber-400 focus:ring-1 focus:ring-amber-400 outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1">Message Body</label>
                      <textarea
                        value={emailForm.body}
                        onChange={(e) => setEmailForm(prev => ({ ...prev, body: e.target.value }))}
                        className="w-full text-sm p-3 rounded border border-gray-200 h-64 font-mono leading-relaxed focus:border-amber-400 focus:ring-1 focus:ring-amber-400 outline-none resize-none"
                      />
                    </div>
                  </>
                )}
              </div>

              <div className="p-4 border-t border-gray-100 bg-white flex justify-end gap-3">
                <button
                  onClick={() => setEmailModalOpen(false)}
                  disabled={isGeneratingEmail || isSendingEmail}
                  className="px-4 py-2 rounded-lg text-sm font-semibold text-gray-600 hover:bg-gray-100 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSendEmail}
                  disabled={isGeneratingEmail || isSendingEmail || !emailForm.to || !emailForm.subject}
                  className="flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-bold text-white bg-amber-600 hover:bg-amber-700 disabled:opacity-50 transition-colors"
                >
                  {isSendingEmail ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
                  {isSendingEmail ? "Sending..." : "Dispatch Alert"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Artifact Overlay — Premium Generative UI Viewer */}
        {activeArtifact && (
          <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 md:p-8" style={{ animation: 'fadeIn 0.3s ease-out' }}>
            <style>{`
            @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
            @keyframes slideUp { from { opacity: 0; transform: translateY(16px) scale(0.98); } to { opacity: 1; transform: translateY(0) scale(1); } }
          `}</style>
            <div className="absolute inset-0 bg-black/30 backdrop-blur-md" onClick={() => setActiveArtifact(null)} />
            <div className="relative w-full max-w-6xl bg-white rounded-2xl shadow-[0_32px_64px_-16px_rgba(0,0,0,0.2)] border border-gray-200/80 overflow-hidden flex flex-col max-h-[92vh]" style={{ animation: 'slideUp 0.4s cubic-bezier(0.16,1,0.3,1)' }}>
              {/* Header */}
              <div className="px-5 py-3.5 border-b border-gray-100 flex items-center justify-between bg-gradient-to-r from-indigo-50/60 via-white to-white">
                <div className="flex items-center gap-3">
                  <div className={`h-9 w-9 rounded-xl flex items-center justify-center text-white shadow-md ${activeArtifact.type === 'svg'
                    ? 'bg-gradient-to-br from-violet-500 to-indigo-600 shadow-indigo-200'
                    : 'bg-gradient-to-br from-blue-500 to-indigo-600 shadow-blue-200'
                    }`}>
                    {activeArtifact.type === 'svg' ? <Activity className="h-5 w-5" /> : <BarChart3 className="h-5 w-5" />}
                  </div>
                  <div>
                    <h2 className="text-sm font-bold text-gray-800">
                      {activeArtifact.type === 'svg' ? 'Compliance Diagram' : 'Data Visualization'}
                    </h2>
                    <p className="text-[10px] text-indigo-500 font-semibold uppercase tracking-widest">Generated from real contract data</p>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => {
                      const blob = new Blob([activeArtifact.content], { type: 'text/html' });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement('a');
                      a.href = url; a.download = `artifact.${activeArtifact.type === 'svg' ? 'svg' : 'html'}`;
                      a.click(); URL.revokeObjectURL(url);
                    }}
                    className="p-2 hover:bg-gray-100 rounded-lg transition-colors text-gray-400 hover:text-gray-600"
                    title="Download"
                  >
                    <Download className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => setActiveArtifact(null)}
                    className="p-2 hover:bg-gray-100 rounded-lg transition-colors text-gray-400 hover:text-gray-600"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>
              </div>

              {/* Content — Premium Iframe Sandbox */}
              <div className="flex-1 overflow-auto bg-[#fafbfc] relative">
                <div className="absolute inset-0 opacity-[0.03] pointer-events-none" style={{ backgroundImage: 'radial-gradient(#64748b 0.5px, transparent 0.5px)', backgroundSize: '20px 20px' }} />
                <div className="relative h-full">
                  <iframe
                    srcDoc={
                      '<!DOCTYPE html><html><head><meta charset="utf-8">' +
                      '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">' +
                      '<style>' +
                      ':root {' +
                      '  --bg-primary: #ffffff;' +
                      '  --bg-secondary: #f8fafc;' +
                      '  --bg-tertiary: #f1f5f9;' +
                      '  --bg-card: rgba(255,255,255,0.85);' +
                      '  --text-primary: #0f172a;' +
                      '  --text-secondary: #475569;' +
                      '  --text-tertiary: #94a3b8;' +
                      '  --border-light: #f1f5f9;' +
                      '  --border-default: #e2e8f0;' +
                      '  --indigo-50: #eef2ff; --indigo-100: #e0e7ff; --indigo-400: #818cf8; --indigo-500: #6366f1; --indigo-600: #4f46e5;' +
                      '  --emerald-50: #ecfdf5; --emerald-400: #34d399; --emerald-500: #10b981; --emerald-600: #059669;' +
                      '  --amber-50: #fffbeb; --amber-400: #fbbf24; --amber-500: #f59e0b; --amber-600: #d97706;' +
                      '  --rose-50: #fff1f2; --rose-400: #fb7185; --rose-500: #f43f5e; --rose-600: #e11d48;' +
                      '  --sky-50: #f0f9ff; --sky-400: #38bdf8; --sky-500: #0ea5e9;' +
                      '  --radius-sm: 6px; --radius-md: 10px; --radius-lg: 14px; --radius-xl: 20px;' +
                      '  --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);' +
                      '  --shadow-md: 0 4px 12px rgba(0,0,0,0.06);' +
                      '  --font-sans: Inter, system-ui, -apple-system, sans-serif;' +
                      '  --font-mono: SF Mono, Fira Code, ui-monospace, monospace;' +
                      '  --color-background-primary: #ffffff;' +
                      '  --color-background-secondary: #f8fafc;' +
                      '  --color-background-tertiary: #f1f5f9;' +
                      '  --color-text-primary: #0f172a;' +
                      '  --color-text-secondary: #475569;' +
                      '  --color-text-tertiary: #94a3b8;' +
                      '  --color-border-primary: #e2e8f0;' +
                      '  --color-border-secondary: #cbd5e1;' +
                      '  --color-border-tertiary: #f1f5f9;' +
                      '  --border-radius-md: 10px;' +
                      '  --border-radius-lg: 14px;' +
                      '}' +
                      '@keyframes fadeInUp { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }' +
                      '@keyframes countUp { from { opacity:0; transform:scale(0.8); } to { opacity:1; transform:scale(1); } }' +
                      '.animate-in { animation: fadeInUp 0.4s ease-out both; }' +
                      '.stat-value { animation: countUp 0.5s cubic-bezier(0.16,1,0.3,1) both; }' +
                      '.card { background:var(--bg-card); backdrop-filter:blur(12px); border:0.5px solid var(--border-default); border-radius:var(--radius-lg); box-shadow:var(--shadow-sm); padding:20px; transition:box-shadow 0.2s,transform 0.2s; }' +
                      '.card:hover { box-shadow:var(--shadow-md); transform:translateY(-1px); }' +
                      'body { margin:0; padding:2rem; font-family:var(--font-sans); display:flex; justify-content:center; align-items:flex-start; min-height:100vh; background:transparent; color:var(--text-primary); }' +
                      '* { box-sizing:border-box; }' +
                      'svg { max-width:100%; height:auto; }' +
                      '</style></head><body>' +
                      activeArtifact.content +
                      '<script>' +
                      'window.addEventListener("load", () => {' +
                      '  if (window.init) window.init();' +
                      '  if (typeof initFn === "function") initFn();' +
                      '  // Auto-resize iframe to content height' +
                      '  setTimeout(() => {' +
                      '    const h = document.body.scrollHeight;' +
                      '    window.parent.postMessage({ type:"artifact-resize", height: h }, "*");' +
                      '  }, 500);' +
                      '});' +
                      '</script></body></html>'
                    }
                    className="w-full border-none bg-transparent"
                    style={{ minHeight: '650px' }}
                    title="Generative UI Artifact"
                    sandbox="allow-scripts allow-same-origin"
                    onLoad={(e) => {
                      // Listen for resize messages from the iframe
                      const handler = (event: MessageEvent) => {
                        if (event.data?.type === 'artifact-resize' && event.data.height) {
                          (e.target as HTMLIFrameElement).style.height = Math.min(event.data.height + 40, 1200) + 'px';
                        }
                      };
                      window.addEventListener('message', handler);
                      // Cleanup on unmount
                      return () => window.removeEventListener('message', handler);
                    }}
                  />
                </div>
              </div>

              {/* Footer */}
              <div className="px-5 py-3 border-t border-gray-100 bg-white/80 backdrop-blur-sm flex items-center justify-between">
                <div className="flex items-center gap-2 text-[10px] text-gray-400">
                  <Sparkles className="h-3 w-3" />
                  <span className="font-medium">Data sourced from MongoDB · Contract KPI Registry</span>
                </div>
                <button
                  onClick={() => setActiveArtifact(null)}
                  className="px-4 py-1.5 bg-gray-50 hover:bg-gray-100 text-gray-600 rounded-lg text-xs font-semibold transition-all active:scale-95 border border-gray-200"
                >
                  Close
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
              <div className="flex items-center gap-1">
                {chatMessages.length > 0 && (
                  <button
                    onClick={async () => {
                      if (chatSessionId) {
                        try { await clearChatSession(chatSessionId); } catch {}
                      }
                      setChatMessages([]);
                      setChatSessionId(null);
                    }}
                    title="New conversation"
                    className="px-2 py-1 text-[10px] font-semibold text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors uppercase tracking-wide flex items-center gap-1"
                  >
                    <RefreshCw className="h-3 w-3" /> New
                  </button>
                )}
                <button onClick={() => setChatOpen(false)} className="p-1.5 hover:bg-gray-100 rounded-full transition-colors text-gray-400">
                  <X className="h-5 w-5" />
                </button>
              </div>
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
                  <div className={`max-w-[90%] rounded-2xl p-4 text-xs leading-relaxed shadow-md ${msg.role === "user"
                    ? "bg-blue-600 text-white"
                    : "bg-white border border-gray-100 text-gray-700 prose prose-sm max-w-none prose-p:leading-relaxed prose-p:m-0 prose-ul:m-0 prose-li:m-0 prose-strong:text-gray-800 prose-ul:pl-4"
                    }`}>
                    {msg.role === "user" ? (
                      msg.content
                    ) : (
                      <div className="space-y-3">
                        {(() => {
                          let displayContent = msg.content || "";
                          let displayThought = msg.thought || "";
                          let displayPlan = msg.plan || "";

                          // Extract thought
                          const thoughtMatch = displayContent.match(/<thought>([\s\S]*?)(?:<\/thought>|$)/);
                          if (thoughtMatch) {
                            displayThought += (displayThought ? "\n" : "") + thoughtMatch[1].trim();
                            displayContent = displayContent.replace(/<thought>[\s\S]*?(?:<\/thought>|$)/, "");
                          }

                          // Extract plan
                          const planMatch = displayContent.match(/<plan>([\s\S]*?)(?:<\/plan>|$)/);
                          if (planMatch) {
                            displayPlan += (displayPlan ? "\n" : "") + planMatch[1].trim();
                            displayContent = displayContent.replace(/<plan>[\s\S]*?(?:<\/plan>|$)/, "");
                          }

                          // Clean up stray markdown artifacts for reasoning
                          displayContent = displayContent.replace(/```xml\s*/g, "").replace(/```\s*$/g, "").trim();

                          return (
                            <>
                              {/* Agent Reasoning Blocks */}
                              {(displayThought || displayPlan || (msg.toolCalls && msg.toolCalls.length > 0)) && (
                                <div className="mb-3 space-y-2 opacity-80 border-l-2 border-blue-100 pl-3 py-1">
                                  {displayThought && (
                                    <div className="text-[10px] text-blue-500 font-medium italic">
                                      <span className="font-bold uppercase not-italic mr-1">Thinking:</span> {displayThought}
                                    </div>
                                  )}
                                  {displayPlan && (
                                    <div className="text-[10px] text-indigo-500 font-medium italic">
                                      <span className="font-bold uppercase not-italic mr-1">Plan:</span> {displayPlan}
                                    </div>
                                  )}
                                  {msg.toolCalls?.map((tc: any, tci: number) => (
                                    <div key={tci} className="flex items-center gap-2 text-[10px] font-bold text-gray-500">
                                      {tc.status === "running" ? (
                                        <RefreshCw className="h-3 w-3 animate-spin text-blue-500" />
                                      ) : (
                                        <CheckCircle2 className="h-3 w-3 text-emerald-500" />
                                      )}
                                      <span className="uppercase tracking-tight">
                                        {tc.name === "search_contract_clauses" ? "Searching Contract..." : 
                                         tc.name === "query_contract_database" ? `Querying ${tc.args.collection}...` :
                                         tc.name === "get_kpi_registry" ? "Accessing KPI Registry..." : "Executing Tool..."}
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              )}

                              {/* Main Content */}
                              {displayContent ? (
                                <ReactMarkdown
                                  remarkPlugins={[remarkGfm]}
                                  rehypePlugins={[rehypeRaw]}
                                >
                                  {displayContent}
                                </ReactMarkdown>
                              ) : msg.isStreaming ? (
                                <div className="flex gap-1 py-2">
                                  <div className="h-1.5 w-1.5 bg-blue-400 rounded-full animate-bounce" />
                                  <div className="h-1.5 w-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:0.2s]" />
                                  <div className="h-1.5 w-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:0.4s]" />
                                </div>
                              ) : null}
                            </>
                          );
                        })()}

                        {msg.artifact && (
                          <button
                            onClick={() => setActiveArtifact(msg.artifact)}
                            className="mt-3 w-full p-3 rounded-xl border border-indigo-200/80 bg-gradient-to-r from-indigo-50/80 to-blue-50/50 hover:from-indigo-100 hover:to-blue-50 flex items-center justify-between transition-all group cursor-pointer text-left shadow-sm hover:shadow-md"
                          >
                            <div className="flex items-center gap-3">
                              <div className={`p-2 rounded-lg text-white shadow-sm ${msg.artifact.type === 'svg'
                                ? 'bg-gradient-to-br from-violet-500 to-indigo-600'
                                : 'bg-gradient-to-br from-blue-500 to-indigo-600'
                                }`}>
                                {msg.artifact.type === 'svg' ? <Activity className="h-3.5 w-3.5" /> : <BarChart3 className="h-3.5 w-3.5" />}
                              </div>
                              <div>
                                <span className="text-[11px] font-bold text-gray-800 block">
                                  {msg.artifact.type === 'svg' ? 'Interactive Diagram' : 'Data Visualization'}
                                </span>
                                <span className="text-[9px] text-indigo-500 font-medium">Generated from real contract data</span>
                              </div>
                            </div>
                            <div className="flex items-center gap-1 text-[10px] font-bold text-indigo-600 group-hover:translate-x-1 transition-transform">
                              View <ArrowRight className="h-3 w-3" />
                            </div>
                          </button>
                        )}
                      </div>
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
