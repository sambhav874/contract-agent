"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import {
  ShieldCheck, AlertTriangle, CheckCircle2, ChevronDown, ArrowLeft,
  RefreshCw, Sparkles, DollarSign, AlertCircle, BarChart3,
  FileText, Activity, Database, Cpu, Lock, Download, Upload, Plus, ArrowRight, Bot
} from "lucide-react";
import {
  fetchContracts, fetchKPIs, fetchBreaches, fetchPerformance,
  evaluateContract, updateBreach, chatWithContractStream,
  fetchAvailableContracts, ingestContract, extractKPIs,
  getKpiTimeSeries, generateBreachEmail, sendBreachEmail, uploadActualsCsv, clearChatSession, uploadContract,
  saveQAPair, fetchSavedQA, deleteSavedQA, fetchSemanticMemory, fetchEpisodicMemory
} from "@/lib/api";

import SummaryCard from "@/components/shared/SummaryCard";
import EmailModal from "@/components/shared/EmailModal";
import ArtifactOverlay from "@/components/shared/ArtifactOverlay";
import LandingOverlay from "@/components/contract/LandingOverlay";
import PerformanceCockpit from "@/components/dashboard/PerformanceCockpit";
import KpiRegistry from "@/components/dashboard/KpiRegistry";
import ComplianceFlags from "@/components/dashboard/ComplianceFlags";
import PerformanceActuals from "@/components/dashboard/PerformanceActuals";
import QuestionLibrary from "@/components/dashboard/QuestionLibrary";
import ContractGuardianChat from "@/components/dashboard/ContractGuardianChat";
import { ChatPanel } from "@/components/chat/ChatPanel";
import AgentInspector from "@/components/agent/AgentInspector";
import { ErrorBoundary } from "@/components/shared/ErrorBoundary";

import { classifySeverity } from "@/lib/utils";

export default function Dashboard() {
  const [contracts, setContracts] = useState<any[]>([]);
  const [selectedContract, setSelectedContract] = useState("");
  const [kpis, setKpis] = useState<any[]>([]);
  const [breaches, setBreaches] = useState<any[]>([]);
  const [actuals, setActuals] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedFlag, setExpandedFlag] = useState<string | null>(null);
  const [expandedKpi, setExpandedKpi] = useState<string | null>(null);
  const [tab, setTab] = useState<"kpis" | "flags" | "actuals" | "qa">("kpis");

  // Phase 2 State
  const [emailModalOpen, setEmailModalOpen] = useState(false);
  const [isGeneratingEmail, setIsGeneratingEmail] = useState(false);
  const [isSendingEmail, setIsSendingEmail] = useState(false);
  const [emailForm, setEmailForm] = useState({ to: "", subject: "", body: "", breachId: "" });
  const [kpiTimeSeries, setKpiTimeSeries] = useState<Record<string, any>>({});
  const [evaluating, setEvaluating] = useState(false);
  const [extractingKpis, setExtractingKpis] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [embeddedChatOpen, setEmbeddedChatOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<any[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatSessionId, setChatSessionId] = useState<string | null>(null);
  const [currentQuery, setCurrentQuery] = useState("");
  const [activeArtifact, setActiveArtifact] = useState<{ content: string, type: "svg" | "html" } | null>(null);
  const [chartMode, setChartMode] = useState<"actual" | "cumulative">("actual");

  // Question Library State
  const [savedQA, setSavedQA] = useState<any[]>([]);
  // editable approval state: { categories: [{name, questions: string[]}] }
  const [qaApprovalState, setQaApprovalState] = useState<any>(null);

  // Agent Inspector Telemetry Memos & States
  const [facts, setFacts] = useState<any[]>([
    {
      key: "Supplier Name",
      value: "AeroSpace Logistics Inc.",
      source: "Notice Clause (p. 24)",
      confidence: 0.99,
      last_used: new Date().toISOString(),
    },
    {
      key: "Payment Terms",
      value: "Net 30 days upon invoice receipt",
      source: "Section 4.2 (p. 8)",
      confidence: 0.95,
      last_used: new Date().toISOString(),
    },
    {
      key: "Audit Frequency",
      value: "Quarterly or upon performance breach",
      source: "Section 7.1 (p. 14)",
      confidence: 0.98,
      last_used: new Date().toISOString(),
    },
    {
      key: "Liability Limit",
      value: "Capped at 150% of annual value",
      source: "Section 12.4 (p. 21)",
      confidence: 0.92,
      last_used: new Date().toISOString(),
    },
  ]);

  const refreshMemoryFacts = useCallback(async () => {
    try {
      const data = await fetchSemanticMemory();
      if (data && data.items && data.items.length > 0) {
        const mapped = data.items.map((item: any) => ({
          key: item.key || "Learned Fact",
          value: typeof item.value === "string" ? item.value : JSON.stringify(item.value),
          source: item.source || "qa_reflection",
          confidence: item.confidence !== undefined ? item.confidence : 0.95,
          last_used: item.timestamp || new Date().toISOString(),
        }));
        setFacts(mapped);
      }
    } catch (err) {
      console.error("Failed to load semantic memory facts:", err);
    }
  }, []);

  const [safetyStatus, setSafetyStatus] = useState({
    cost_tracker: 0.04,
    max_cost_usd: 5.0,
    max_iterations: 15,
    iterations_used: 1,
  });

  useEffect(() => {
    const userMessageCount = chatMessages.filter((m) => m.role === "user").length;
    const assistantMessageCount = chatMessages.filter((m) => m.role === "assistant").length;
    const totalIterations = Math.max(1, userMessageCount + assistantMessageCount);

    // Estimate cost: base $0.04 + $0.03 per message pair
    const estimatedCost = 0.04 + userMessageCount * 0.03;

    setSafetyStatus({
      cost_tracker: Number(estimatedCost.toFixed(4)),
      max_cost_usd: 5.0,
      max_iterations: 15,
      iterations_used: totalIterations,
    });
  }, [chatMessages]);

  const lastAssistantMessage = useMemo(() => {
    return chatMessages.findLast((m) => m.role === "assistant");
  }, [chatMessages]);

  const planSteps = useMemo(() => {
    if (!lastAssistantMessage?.plan) return [];
    const steps = lastAssistantMessage.plan.match(/\d+[).]\s+[\s\S]*?(?=(?:\d+[).]\s+|$))/g);
    if (!steps) {
      return [{ id: "1", text: lastAssistantMessage.plan.replace(/<plan>|<\/plan>/g, "").trim(), status: "done" as const }];
    }
    return steps.map((step: string, i: number) => {
      const text = step.replace(/^\d+[).]\s+/, "").trim();
      const isLastStreaming = lastAssistantMessage.isStreaming && i === steps.length - 1;
      return {
        id: String(i + 1),
        text,
        status: isLastStreaming ? ("running" as const) : ("done" as const),
      };
    });
  }, [lastAssistantMessage]);

  const thoughtsList = useMemo(() => {
    if (!lastAssistantMessage?.thought) return [];
    return [
      {
        id: "thought-1",
        content: lastAssistantMessage.thought.replace(/<thought>|<\/thought>/g, "").trim(),
        timestamp: Date.now(),
      },
    ];
  }, [lastAssistantMessage]);

  const workbenchToolCalls = useMemo(() => {
    if (!lastAssistantMessage?.toolCalls) return [];
    return lastAssistantMessage.toolCalls.map((tc: any, i: number) => ({
      id: String(i),
      name: tc.name,
      args: tc.args || {},
      status: tc.status === "running" ? ("running" as const) : ("done" as const),
      result: tc.status === "done" ? "Operation succeeded" : undefined,
    }));
  }, [lastAssistantMessage]);

  // Journey state
  const [journey, setJourney] = useState<"LANDING" | "DASHBOARD">("LANDING");
  const [availableContracts, setAvailableContracts] = useState<any[]>([]);
  const [guardianWorkflow, setGuardianWorkflow] = useState<{ active: boolean; label: string } | null>(null);

  async function handleEvaluate() {
    if (!selectedContract || evaluating) return;
    setEvaluating(true);
    try {
      await evaluateContract(selectedContract);
      const [b, a] = await Promise.all([fetchBreaches(selectedContract), fetchPerformance(selectedContract)]);
      setBreaches(b);
      setActuals(a);
      setTab("flags");
    } catch (e) {
      console.error(e);
    } finally {
      setEvaluating(false);
    }
  }

  async function handleUpdateStatus(breachId: string, newStatus: string) {
    try {
      await updateBreach(breachId, { status: newStatus });
      setBreaches(prev => prev.map(b =>
        (b.breach_id === breachId || b._id === breachId) ? { ...b, status: newStatus } : b
      ));
    } catch (e) {
      console.error(e);
    }
  }

  async function handleUpdateNotes(breachId: string, newNotes: string) {
    try {
      await updateBreach(breachId, { notes: newNotes });
      setBreaches(prev => prev.map(b =>
        (b.breach_id === breachId || b._id === breachId) ? { ...b, notes: newNotes } : b
      ));
    } catch (e) {
      console.error(e);
    }
  }

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
        } catch (e) {
          console.error("Failed to load KPI timeseries", e);
        }
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
      alert("Email alert sent successfully.");
    } catch (e) {
      console.error(e);
      alert("Failed to send email.");
    } finally {
      setIsSendingEmail(false);
    }
  }

  async function handleUploadActuals(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file || !selectedContract) return;

    setEvaluating(true);
    try {
      await uploadActualsCsv(selectedContract, file);
      const [p, b] = await Promise.all([
        fetchPerformance(selectedContract),
        fetchBreaches(selectedContract)
      ]);
      setActuals(p);
      setBreaches(b);
    } catch (e) {
      console.error("Upload failed", e);
    } finally {
      setEvaluating(false);
      event.target.value = '';
    }
  }

  async function handleUploadNewContract(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      const res = await uploadContract(file);
      await handleIngestContract(res.filename);
    } catch (e) {
      console.error("Upload failed", e);
      const message = e instanceof Error ? e.message : "Unknown error";
      alert(`Failed to upload contract: ${message}`);
    } finally {
      event.target.value = '';
    }
  }

  function handleExportCsv() {
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

  async function handleSaveQAPair(category: string, question: string, answer: string, sources: string[] = [], justification: string = "", exact_quotes: string[] = [], confidence: number = 0.9) {
    if (!selectedContract) return;
    try {
      await saveQAPair(selectedContract, { category, question, answer, sources, exact_quotes, justification, confidence });
      const res = await fetchSavedQA(selectedContract);
      setSavedQA(res.items || []);
    } catch (e) {
      console.error("Save QA failed", e);
    }
  }

  async function handleDeleteQAPair(qaId: string) {
    if (!selectedContract) return;
    try {
      await deleteSavedQA(selectedContract, qaId);
      setSavedQA(prev => prev.filter((q: any) => q.qa_id !== qaId));
    } catch (e) {
      console.error("Delete QA failed", e);
    }
  }

  async function handleApproveAndAnswer(categories: any[]) {
    const lines = categories.flatMap((cat: any, ci: number) =>
      cat.questions.map((q: string, qi: number) => `${ci * 10 + qi + 1}. [${cat.name}] ${q}`)
    ).join("\n");
    const prompt = `Please answer the following approved questions from the contract:\n${lines}`;
    setQaApprovalState(null);
    await handleChat(prompt);
  }

  async function handleChat(question: string, breachId?: string) {
    const submittedQuestion = question.trim();
    if (!submittedQuestion || chatLoading) return;
    if (!selectedContract) return;

    setChatOpen(true);
    setChatLoading(true);
    setCurrentQuery("");
    const userMsgId = Date.now().toString();
    const assistantMsgId = (Date.now() + 1).toString();

    setChatMessages(prev => [...prev, { id: userMsgId, role: "user", content: submittedQuestion }]);

    setChatMessages(prev => [...prev, {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      thought: "",
      geminiThought: "",
      plan: "",
      delegations: [],
      toolCalls: [],
      toolResults: [],
      isStreaming: true
    }]);

    try {
      const sid = chatSessionId ?? (() => {
        const id = `${selectedContract}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
        setChatSessionId(id);
        return id;
      })();

      const response = await chatWithContractStream(selectedContract, submittedQuestion, breachId, sid);
      const reader = response.body?.getReader();
      if (!reader) return;

      let accumulatedContent = "";
      let accumulatedThought = "";
      let accumulatedGeminiThought = "";
      let accumulatedPlan = "";
      type ChatToolCall = {
        name: string;
        args: Record<string, unknown>;
        status: "running" | "done";
      };
      type ChatDelegation = {
        key?: string;
        agent?: string;
        intent?: string;
        task?: string;
        status?: string;
        step_id?: string;
        reason?: string;
        error?: string;
        type?: string;
        content?: string;
        source?: string;
        name?: string;
        args?: Record<string, unknown>;
      };
      const toolCalls: ChatToolCall[] = [];
      const delegations: ChatDelegation[] = [];

      const upsertDelegation = (event: ChatDelegation) => {
        const key = `${event.step_id || "main"}:${event.agent || "agent"}:${event.intent || "intent"}`;
        const existingIndex = delegations.findIndex((item) => item.key === key);
        const next = { ...(existingIndex >= 0 ? delegations[existingIndex] : {}), ...event, key };
        if (existingIndex >= 0) delegations[existingIndex] = next;
        else delegations.push(next);
      };

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(trimmed.replace("data: ", "")) as ChatDelegation;

            if (data.type === "thought") {
              accumulatedThought += data.content || "";
              if (data.source === "gemini_thinking") {
                accumulatedGeminiThought += data.content || "";
              }
            } else if (data.type === "plan") {
              accumulatedPlan += data.content || "";
            } else if (data.type === "content") {
              accumulatedContent += data.content || "";
            } else if (data.type === "delegation") {
              upsertDelegation(data);
            } else if (data.type === "tool_call") {
              toolCalls.push({ name: data.name || "unknown_tool", args: data.args || {}, status: "running" });
            } else if (data.type === "tool_result") {
              const lastCall = toolCalls.findLast((tc) => tc.name === data.name && tc.status === "running");
              if (lastCall) lastCall.status = "done";
            }

            setChatMessages(prev => prev.map(m => m.id === assistantMsgId ? {
              ...m,
              content: accumulatedContent,
              thought: accumulatedThought,
              geminiThought: accumulatedGeminiThought,
              plan: accumulatedPlan,
              delegations: [...delegations],
              toolCalls: [...toolCalls]
            } : m));

          } catch (e) {
            console.error("Error parsing SSE chunk", e);
          }
        }
      }

      let artifact = null;
      let finalContent = accumulatedContent;

      const fencedRegex = /```(?:html|svg|xml)\s*([\s\S]*?)```/i;
      const fencedMatch = fencedRegex.exec(finalContent);

      if (fencedMatch && (fencedMatch[1].includes('<svg') || fencedMatch[1].includes('<div') || fencedMatch[1].includes('<link') || fencedMatch[1].includes('<style'))) {
        artifact = {
          type: (fencedMatch[1].includes('<svg') ? 'svg' : 'html') as "svg" | "html",
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

      refreshMemoryFacts().catch(e => console.error(e));

    } catch (e) {
      console.error(e);
      setChatMessages(prev => prev.map(m => m.id === assistantMsgId ? {
        ...m,
        content: "Sorry, I encountered an error. Please try again.",
        isStreaming: false
      } : m));
    } finally {
      setChatLoading(false);
    }
  }

  async function handleResetChat() {
    if (chatSessionId) {
      try {
        await clearChatSession(chatSessionId);
      } catch (e) {
        console.error("Failed to clear chat session", e);
      }
    }
    setChatMessages([]);
    setChatSessionId(null);
  }

	  useEffect(() => {
	    const timer = setTimeout(() => {
	      setLoading(false);
    }, 5000);

    (async () => {
      try {
        const [active, available] = await Promise.all([
          fetchContracts().catch(e => { console.error("Contracts fetch failed", e); return []; }),
          fetchAvailableContracts().catch(e => { console.error("Available contracts fetch failed", e); return []; })
        ]);

        setContracts(active || []);
        setAvailableContracts(available || []);
        refreshMemoryFacts().catch(e => console.error(e));
      } catch (e) {
        console.error("Initial load error:", e);
      } finally {
        setLoading(false);
        clearTimeout(timer);
      }
    })();

	    return () => clearTimeout(timer);
	  }, []);

  type WorkflowStepStatus = "done" | "running" | "pending" | "error";

  function workflowMarkdown(
    title: string,
    subject: string,
    steps: Array<{ label: string; status: WorkflowStepStatus }>,
    note?: string
  ) {
    const statusText = {
      done: "[x]",
      running: "[ ]",
      pending: "[ ]",
      error: "[ ]",
    };
    const lines = steps.map((step) => {
      const suffix =
        step.status === "running" ? " _running_" :
        step.status === "error" ? " _failed_" :
        step.status === "pending" ? " _queued_" :
        "";
      return `- ${statusText[step.status]} ${step.label}${suffix}`;
    });

    return [
      `**${title}**`,
      "",
      subject,
      "",
      ...lines,
      ...(note ? ["", note] : []),
    ].join("\n");
  }

  function upsertGuardianWorkflowMessage(
    messageId: string,
    content: string,
    workflowLabel: string,
    active: boolean
  ) {
    setChatOpen(true);
    setGuardianWorkflow(active ? { active: true, label: workflowLabel } : null);
    setChatMessages(prev => {
      const nextMessage = {
        id: messageId,
        role: "assistant",
        content,
        isStreaming: active,
        toolCalls: [{
          id: `${messageId}-workflow`,
          name: workflowLabel,
          status: active ? "running" : "done",
        }],
      };

      if (prev.some((message) => message.id === messageId)) {
        return prev.map((message) => message.id === messageId ? { ...message, ...nextMessage } : message);
      }
      return [...prev, nextMessage];
    });
  }

  async function handleIngestContract(filename: string) {
    const messageId = `workflow-ingest-${Date.now()}`;
    setJourney("DASHBOARD");
    setChatOpen(true);
    setKpis([]);
    setBreaches([]);
    setActuals([]);
    upsertGuardianWorkflowMessage(
      messageId,
      workflowMarkdown(
        "Contract ingestion started",
        `Source: \`${filename}\``,
        [
          { label: "Initialize ingestion engine", status: "done" },
          { label: "Parse contract structure", status: "running" },
          { label: "Generate vector embeddings", status: "pending" },
          { label: "Refresh dashboard", status: "pending" },
        ]
      ),
      "Ingesting contract...",
      true
    );

    try {
      const ingestRes = await ingestContract(filename);
      upsertGuardianWorkflowMessage(
        messageId,
        workflowMarkdown(
          "Contract ingestion running",
          `Source: \`${ingestRes.name}\``,
          [
            { label: "Initialize ingestion engine", status: "done" },
            { label: "Parse contract structure", status: "done" },
            { label: "Generate vector embeddings", status: "done" },
            { label: "Refresh dashboard", status: "running" },
          ]
        ),
        "Refreshing indexed contract...",
        true
      );

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

      upsertGuardianWorkflowMessage(
        messageId,
        workflowMarkdown(
          "Contract ingestion complete",
          `Indexed contract: \`${ingestRes.name}\``,
          [
            { label: "Initialize ingestion engine", status: "done" },
            { label: "Parse contract structure", status: "done" },
            { label: "Generate vector embeddings", status: "done" },
            { label: "Refresh dashboard", status: "done" },
          ],
          "KPI extraction is ready when you want to run it."
        ),
        "Contract ingestion complete",
        false
      );
      return true;

    } catch (e) {
      console.error(e);
      const message = e instanceof Error ? e.message : "Unknown error";
      upsertGuardianWorkflowMessage(
        messageId,
        workflowMarkdown(
          "Contract ingestion failed",
          `Source: \`${filename}\``,
          [
            { label: "Initialize ingestion engine", status: "done" },
            { label: "Parse/index contract", status: "error" },
          ],
          `Error: ${message}`
        ),
        "Contract ingestion failed",
        false
      );
      return false;
    }
  }

  async function handleExtractKpis() {
    if (!selectedContract || extractingKpis) return;

    const messageId = `workflow-kpi-${Date.now()}`;
    setExtractingKpis(true);
    setJourney("DASHBOARD");
    setChatOpen(true);
    upsertGuardianWorkflowMessage(
      messageId,
      workflowMarkdown(
        "KPI extraction started",
        `Contract: \`${selectedContract}\``,
        [
          { label: "Initialize KPI extraction", status: "done" },
          { label: "Scan indexed clauses", status: "running" },
          { label: "Extract thresholds, parties, penalties, and remediation terms", status: "pending" },
          { label: "Refresh KPI registry", status: "pending" },
        ]
      ),
      "Extracting KPIs...",
      true
    );

    try {
      const extractRes = await extractKPIs(selectedContract);
      setKpis(extractRes.kpis || []);
      const extractedCount = extractRes.kpis_count ?? (extractRes.kpis || []).length;
      upsertGuardianWorkflowMessage(
        messageId,
        workflowMarkdown(
          "KPI extraction running",
          `Contract: \`${selectedContract}\``,
          [
            { label: "Initialize KPI extraction", status: "done" },
            { label: "Scan indexed clauses", status: "done" },
            { label: `Extract ${extractedCount} KPI candidates`, status: "done" },
            { label: "Refresh KPI registry", status: "running" },
          ]
        ),
        "Refreshing KPI registry...",
        true
      );

      const [k, b, a] = await Promise.all([
        fetchKPIs(selectedContract),
        fetchBreaches(selectedContract),
        fetchPerformance(selectedContract)
      ]);
      setKpis(k || []);
      setBreaches(b || []);
      setActuals(a || []);
      setTab("kpis");
      upsertGuardianWorkflowMessage(
        messageId,
        workflowMarkdown(
          "KPI extraction complete",
          `Contract: \`${selectedContract}\``,
          [
            { label: "Initialize KPI extraction", status: "done" },
            { label: "Scan indexed clauses", status: "done" },
            { label: `Extract ${k?.length ?? extractedCount} KPI records`, status: "done" },
            { label: "Refresh KPI registry", status: "done" },
          ],
          "The KPI registry has been updated."
        ),
        "KPI extraction complete",
        false
      );
    } catch (e) {
      console.error(e);
      const message = e instanceof Error ? e.message : "Unknown error";
      upsertGuardianWorkflowMessage(
        messageId,
        workflowMarkdown(
          "KPI extraction failed",
          `Contract: \`${selectedContract}\``,
          [
            { label: "Initialize KPI extraction", status: "done" },
            { label: "Extract KPI registry", status: "error" },
          ],
          `Error: ${message}`
        ),
        "KPI extraction failed",
        false
      );
    } finally {
      setExtractingKpis(false);
    }
  }

  useEffect(() => {
    if (!selectedContract) return;

    const timer = setTimeout(() => {
      setLoading(false);
    }, 8000);

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
        refreshMemoryFacts().catch(e => console.error("Facts load error:", e));
      } catch (e) {
        console.error("Dashboard data load error:", e);
      } finally {
        setLoading(false);
        clearTimeout(timer);
      }
    })();

    return () => clearTimeout(timer);
  }, [selectedContract]);

  useEffect(() => {
    if (tab !== "qa" || !selectedContract) return;
    (async () => {
      try {
        const res = await fetchSavedQA(selectedContract);
        setSavedQA(res.items || []);
      } catch (e) {
        console.error("Failed to load saved QA", e);
      }
    })();
  }, [tab, selectedContract]);

  // Derived Analytics useMemos
  const kpiTypeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    kpis.forEach(k => { const t = k.kpi_type || "other"; counts[t] = (counts[t] || 0) + 1; });
    return Object.entries(counts).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);
  }, [kpis]);

  const penaltyByParty = useMemo(() => {
    const m: Record<string, number> = {};
    kpis.forEach(k => { const p = k.party || "Unspecified"; m[p] = (m[p] || 0) + (k.consequence_value || 0); });
    return Object.entries(m).map(([name, value]) => ({ name: name.substring(0, 20), value })).filter(x => x.value > 0).sort((a, b) => b.value - a.value);
  }, [kpis]);

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

  const activeBreaches = breaches.filter(b => b.is_breach);
  const flags = breaches.map(b => {
    const kpi = kpis.find(k => k.kpi_id === b.kpi_id);
    return { ...b, severity: classifySeverity(b), kpi };
  }).sort((a, b) => {
    const order = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
    return (order[a.severity as keyof typeof order] ?? 4) - (order[b.severity as keyof typeof order] ?? 4);
  });

  const sevCounts = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
  flags.forEach(f => { if (f.severity in sevCounts) sevCounts[f.severity as keyof typeof sevCounts]++; });
  const totalExposure = flags.reduce((s, f) => s + (f.penalty_amount || 0), 0);
  const evaluatedKpiIds = new Set(breaches.map(b => b.kpi_id));

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
    <ErrorBoundary>
      <div className="min-h-screen bg-[#F5F4F2] text-slate-800 pb-12 relative overflow-x-hidden">
        {/* Overlays / Modals */}
        <LandingOverlay
        isOpen={journey === "LANDING"}
        contracts={contracts}
        availableContracts={availableContracts}
        onSelectContract={(contractId) => {
          setSelectedContract(contractId);
          setJourney("DASHBOARD");
        }}
        onUploadNewContract={handleUploadNewContract}
        onIngestContract={handleIngestContract}
      />

      <EmailModal
        isOpen={emailModalOpen}
        onClose={() => setEmailModalOpen(false)}
        isGeneratingEmail={isGeneratingEmail}
        isSendingEmail={isSendingEmail}
        emailForm={emailForm}
        setEmailForm={setEmailForm as any}
        onSend={handleSendEmail}
      />

      <ArtifactOverlay
        activeArtifact={activeArtifact}
        onClose={() => setActiveArtifact(null)}
      />

      <div className={`transition-all duration-700 ease-in-out ${journey !== "DASHBOARD" ? "blur-xl scale-[0.95] brightness-75 pointer-events-none" : ""}`}>

        {/* Header */}
        <div className="border-b border-gray-200 bg-white fixed top-0 w-full z-40">
          <div className="max-w-[1800px] mx-auto px-6 py-3 flex items-center justify-between">
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
	                    {contracts.map((c, index) => <option key={`${c.contract_id}-${index}`} value={c.contract_id}>{c.contract_id}</option>)}
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
              <button
                onClick={handleExtractKpis}
                disabled={!selectedContract || extractingKpis}
                className={`flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium shadow-sm transition-colors ${
                  extractingKpis
                    ? "border-emerald-600 bg-emerald-600 text-white"
                    : "border-emerald-200 bg-emerald-50 text-emerald-700 hover:border-emerald-300 hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-50"
                }`}
              >
                <Sparkles className={`h-3.5 w-3.5 ${extractingKpis ? "animate-pulse" : ""}`} />
                {extractingKpis ? "Extracting..." : "Extract KPIs"}
              </button>
              <button
                onClick={() => setEmbeddedChatOpen(prev => !prev)}
                className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-md text-white bg-slate-800 hover:bg-slate-950 transition-colors shadow-sm active:scale-95"
              >
                <Bot className="h-3.5 w-3.5" /> Quick Chat
              </button>
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
                className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-md transition-colors shadow-sm border ${evaluating ? "bg-[#0084C7] text-white border-[#0084C7]" : "text-gray-500 hover:text-gray-800 bg-white border-gray-200"}`}>
                <RefreshCw className={`h-3.5 w-3.5 ${evaluating ? "animate-spin" : ""}`} />
                {evaluating ? "Evaluating..." : "Re-evaluate"}
              </button>
            </div>
          </div>
        </div>

        <div className={`transition-all duration-500 ${activeArtifact ? "blur-md scale-[0.98] pointer-events-none brightness-95" : ""}`}>
          <div className="max-w-[1800px] mx-auto px-6 pt-20 space-y-5 pb-20">
            {/* Summary Cards */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <SummaryCard label="Compliance Rate" value={`${complianceRate}%`} color={complianceRate >= 90 ? "text-green-700" : complianceRate >= 70 ? "text-amber-700" : "text-red-700"} bg={complianceRate >= 90 ? "bg-green-50" : complianceRate >= 70 ? "bg-amber-50" : "bg-red-50"} border={complianceRate >= 90 ? "border-green-200" : complianceRate >= 70 ? "border-amber-200" : "border-red-200"} icon={<ShieldCheck className={`h-4 w-4 ${complianceRate >= 90 ? "text-green-700" : complianceRate >= 70 ? "text-amber-700" : "text-red-700"}`} />} />
              <SummaryCard label="KPIs Tracked" value={`${breaches.length > 0 ? evaluatedKpiIds.size : 0} / ${kpis.length}`} color="text-[#0084C7]" bg="bg-blue-50" border="border-blue-200" icon={<BarChart3 className="h-4 w-4 text-[#0084C7]" />} />
              <SummaryCard label="Critical / High" value={`${sevCounts.CRITICAL} / ${sevCounts.HIGH}`} color="text-red-700" bg="bg-red-50" border="border-red-200" icon={<AlertCircle className="h-4 w-4 text-red-700" />} />
              <SummaryCard label="Active Breaches" value={activeBreaches.filter(b => b.status !== "Resolved" && b.status !== "Waived").length} color="text-orange-700" bg="bg-orange-50" border="border-orange-200" icon={<AlertTriangle className="h-4 w-4 text-orange-700" />} />
              <SummaryCard label="Penalty Exposure" value={`$${totalExposure.toLocaleString()}`} color="text-red-700" bg="bg-white" border="border-gray-200" icon={<DollarSign className="h-4 w-4 text-red-700" />} />
            </div>

            {tab !== "qa" && (
              <div className="animate-in fade-in duration-300">
                <PerformanceCockpit
                  kpis={kpis}
                  breaches={breaches}
                  activeBreaches={activeBreaches}
                  sevCounts={sevCounts}
                  kpiTypeCounts={kpiTypeCounts}
                  penaltyByParty={penaltyByParty}
                  actualVsThreshold={actualVsThreshold}
                  flags={flags}
                  breachStatusCounts={breachStatusCounts}
                  penaltyAccrualData={penaltyAccrualData}
                  severityStatusMatrix={severityStatusMatrix}
                />
              </div>
            )}

            {/* Dashboard Tabs & Detail Views */}
            <div className="space-y-4">

              {/* Tab Navigation */}
              <div className="bg-white rounded-xl border border-gray-200 p-1 flex shadow-sm">
                <button onClick={() => setTab("kpis")} className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${tab === "kpis" ? "bg-[#0084C7] text-white shadow-md shadow-blue-500/10" : "text-gray-500 hover:text-gray-800"}`}>
                  KPI Registry
                </button>
                <button onClick={() => setTab("flags")} className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${tab === "flags" ? "bg-[#0084C7] text-white shadow-md shadow-blue-500/10" : "text-gray-500 hover:text-gray-800"}`}>
                  Compliance Flags
                </button>
                <button onClick={() => setTab("actuals")} className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${tab === "actuals" ? "bg-[#0084C7] text-white shadow-md shadow-blue-500/10" : "text-gray-500 hover:text-gray-800"}`}>
                  Performance Logs
                </button>
                <button onClick={() => setTab("qa")} className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${tab === "qa" ? "bg-[#0084C7] text-white shadow-md shadow-blue-500/10" : "text-gray-500 hover:text-gray-800"}`}>
                  Q&A Library
                </button>
              </div>

              {/* Dynamic View Injection */}
              {tab === "kpis" && (
                <div className="space-y-4 animate-in fade-in duration-300">
                  <KpiRegistry
                    kpis={kpis}
                    activeBreaches={activeBreaches}
                    expandedKpi={expandedKpi}
                    handleExpandKpi={handleExpandKpi}
	                    chartMode={chartMode}
	                    setChartMode={setChartMode}
	                    kpiTimeSeries={kpiTimeSeries}
	                    loading={loading}
	                    extracting={extractingKpis}
	                    onExtractKPIs={handleExtractKpis}
	                  />
                </div>
              )}

              {tab === "flags" && (
                <div className="animate-in fade-in duration-300">
                  <ComplianceFlags
                    flags={flags}
                    expandedFlag={expandedFlag}
                    setExpandedFlag={setExpandedFlag}
                    handleUpdateStatus={handleUpdateStatus}
                    handleUpdateNotes={handleUpdateNotes}
                    handleChat={handleChat}
                    handleOpenEmailModal={handleOpenEmailModal}
                  />
                </div>
              )}

              {tab === "actuals" && (
                <div className="animate-in fade-in duration-300">
                  <PerformanceActuals actuals={actuals} />
                </div>
              )}

              {tab === "qa" && (
                <div className="animate-in fade-in duration-300">
                  <QuestionLibrary
                    savedQA={savedQA}
                    handleDeleteQAPair={handleDeleteQAPair}
                    handleChat={handleChat}
                    setChatOpen={setChatOpen}
                    contractId={selectedContract}
                  />
                </div>
              )}

            </div>
          </div>
        </div>

        {/* RAG Chat Assistant */}
        <ContractGuardianChat
          chatOpen={chatOpen}
          setChatOpen={setChatOpen}
          chatMessages={chatMessages}
          chatLoading={chatLoading}
          currentQuery={currentQuery}
          setCurrentQuery={setCurrentQuery}
          qaApprovalState={qaApprovalState}
          setQaApprovalState={setQaApprovalState}
          handleChat={handleChat}
          handleResetChat={handleResetChat}
          handleSaveQAPair={handleSaveQAPair}
          handleApproveAndAnswer={handleApproveAndAnswer}
          setActiveArtifact={setActiveArtifact as any}
          workflowStatus={guardianWorkflow}
        />

        {/* Sliding Embedded Chat Panel (from left) */}
        <div
          className={`fixed top-0 left-0 h-full w-[450px] bg-white border-r border-gray-200 shadow-2xl z-[60] transition-transform duration-500 ease-in-out ${
            embeddedChatOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          {embeddedChatOpen && (
            <ChatPanel
              contractId={selectedContract}
              onClose={() => setEmbeddedChatOpen(false)}
            />
          )}
        </div>

        {/* Agent Inspector Bottom Drawer */}
        <AgentInspector
          planSteps={planSteps}
          thoughts={thoughtsList}
          toolCalls={workbenchToolCalls}
          facts={facts}
          safetyStatus={safetyStatus}
        />
      </div>
    </div>
    </ErrorBoundary>
  );
}
