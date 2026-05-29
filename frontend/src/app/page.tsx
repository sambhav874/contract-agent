"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import {
  ShieldCheck, AlertTriangle, CheckCircle2, ChevronDown, ArrowLeft,
  RefreshCw, Sparkles, DollarSign, AlertCircle, BarChart3,
  FileText, Activity, Database, Cpu, Lock, Download, Upload, Plus, ArrowRight, Bot, X
} from "lucide-react";
import {
  fetchContracts, fetchKPIs, fetchBreaches, fetchPerformance,
  evaluateContract, updateBreach, chatWithContractStream,
  fetchAvailableContracts, ingestContract, extractKPIs,
  getKpiTimeSeries, generateBreachEmail, sendBreachEmail, uploadActualsCsv, clearChatSession, uploadContract,
  saveQAPair, fetchSavedQA, deleteSavedQA, fetchSemanticMemory, fetchEpisodicMemory, fetchContractText
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
import ContractViewer from "@/components/dashboard/ContractViewer";
import IntegrationConfigurator from "@/components/dashboard/IntegrationConfigurator";
import AgentInspector from "@/components/agent/AgentInspector";
import { ErrorBoundary } from "@/components/shared/ErrorBoundary";

import { classifySeverity } from "@/lib/utils";
import {
  attachActualSourcesToBreaches,
  buildDemoBreachEmail,
  CONNECTED_SOURCES,
  DEMO_ACTUALS,
  DEMO_BREACHES,
  DEMO_CONTRACT_ID,
  DEMO_KPIS,
  demoTimeSeries,
  isDemoContractId,
  prepareDemoContracts,
} from "@/lib/demoData";

function withDemoFallback<T>(contractId: string, data: T[] | undefined | null, fallback: T[]) {
  if (isDemoContractId(contractId) && (!data || data.length === 0)) {
    return fallback;
  }
  return data || [];
}

const wait = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

type DemoPhase = "contract_only" | "extracting_kpis" | "review_kpis" | "integration_setup" | "connecting_sources" | "monitoring_live";
type SourceSyncStatus = "waiting" | "syncing" | "connected";
type DemoSourceSync = Record<string, SourceSyncStatus>;
type IntegrationConfig = {
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
};

const RECOMMENDED_TRACKED_KPI_IDS = new Set([
  "KPI-001",
  "KPI-003",
  "KPI-006",
  "KPI-007",
  "KPI-014",
  "KPI-015-A",
  "TIM-001",
]);

function initialSourceSync(): DemoSourceSync {
  return Object.fromEntries(CONNECTED_SOURCES.map((source) => [source.id, "waiting"])) as DemoSourceSync;
}

function sourceIdForActual(actual: any, fallbackIndex: number) {
  const metadata = actual?.metadata || {};
  const haystack = [
    actual?.source,
    metadata.source_type,
    metadata.feed,
    metadata.endpoint,
    metadata.workbook,
    metadata.sheet,
    metadata.ticket,
    metadata.queue,
    actual?.kpi_id,
  ].filter(Boolean).join(" ").toLowerCase();

  if (haystack.includes("erp") || haystack.includes("dispatch") || haystack.includes("invoice")) return "erp";
  if (haystack.includes("servicenow") || haystack.includes("ticket") || haystack.includes("inc-") || haystack.includes("emergency")) return "service";
  if (haystack.includes("excel") || haystack.includes("workbook") || haystack.includes("sheet") || haystack.includes("reconciliation") || haystack.includes("sustainability")) return "excel";
  if (haystack.includes("rest") || haystack.includes("api") || haystack.includes("iot") || haystack.includes("temperature") || haystack.includes("incident")) return "rest";

  return CONNECTED_SOURCES[fallbackIndex % CONNECTED_SOURCES.length]?.id || "erp";
}

function groupActualsBySource(actualRows: any[]) {
  const batches: Record<string, any[]> = Object.fromEntries(CONNECTED_SOURCES.map((source) => [source.id, []]));
  actualRows.forEach((actual, index) => {
    const sourceId = sourceIdForActual(actual, index);
    batches[sourceId] = [...(batches[sourceId] || []), actual];
  });
  return batches;
}

function sourceIdForKpiConfig(kpi: any) {
  const haystack = [kpi?.kpi_id, kpi?.name, kpi?.trigger_condition, kpi?.section].join(" ").toLowerCase();
  if (haystack.includes("on-time") || haystack.includes("delivery")) return "erp";
  if (haystack.includes("temperature") || haystack.includes("food safety") || haystack.includes("incident")) return "rest";
  if (haystack.includes("packaging") || haystack.includes("fulfillment") || haystack.includes("quality") || haystack.includes("special meal")) return "excel";
  if (haystack.includes("emergency") || haystack.includes("response")) return "service";
  if (haystack.includes("report")) return "excel";
  return "erp";
}

function requiredHeadersForKpi(kpi: any, sourceId: string) {
  const metric = String(kpi?.kpi_id || "kpi_id").toLowerCase().replace(/[^a-z0-9]+/g, "_");
  const haystack = [kpi?.kpi_id, kpi?.name, kpi?.trigger_condition].join(" ").toLowerCase();
  if (sourceId === "erp") return ["flight_leg_id", "catering_order_id", "std_utc", "delivery_scan_utc", "station_code", metric];
  if (sourceId === "rest" && haystack.includes("temperature")) return ["flight_leg_id", "sample_time_utc", "cart_id", "probe_temp_c", "station_code", metric];
  if (sourceId === "rest" && haystack.includes("incident")) return ["event_id", "opened_at_utc", "station_code", "meal_batch_id", "confirmed_flag", metric];
  if (sourceId === "rest") return ["flight_leg_id", "event_time_utc", "station_code", "event_type", metric];
  if (sourceId === "excel") return ["service_date", "flight_no", "station_code", "catering_order_id", metric, "reviewer"];
  return ["number", "opened_at", "assignment_group", "category", "state", "priority", "kpi_ref"];
}

function sourceDefaultsForKpi(kpi: any, sourceId: string) {
  const kpiId = String(kpi?.kpi_id || "KPI").replace(/[^A-Z0-9]+/gi, "_");
  const metric = kpiId.toLowerCase();
  const haystack = [kpi?.kpi_id, kpi?.name, kpi?.trigger_condition].join(" ").toLowerCase();

  if (sourceId === "erp") {
    return {
      connector: "SAP S/4HANA Dispatch",
      interfaceName: "SAP RFC / BAPI function module",
      bapiFunction: haystack.includes("fulfillment")
        ? "Z_CTR_ORDER_FULFILLMENT_GET"
        : haystack.includes("delivery")
          ? "Z_CTR_FLIGHT_DELIVERY_GET"
          : "Z_CTR_PERFORMANCE_GET",
      endpoint: undefined,
      filePattern: undefined,
      authMode: "SAP RFC destination CTR_PRD_100",
      watermark: "changed_on > last_success_utc",
      joinKey: "flight_leg_id + catering_order_id",
      transform: "Convert scan timestamps to target-attainment %",
    };
  }

  if (sourceId === "rest") {
    return {
      connector: "AIDX / IoT REST Feed",
      interfaceName: haystack.includes("temperature") ? "IoT telemetry REST API" : "IATA AIDX flight-event API",
      bapiFunction: undefined,
      endpoint: haystack.includes("temperature")
        ? "GET /iot/catering/v1/temperature-readings?since={watermark}"
        : haystack.includes("incident")
          ? "GET /aidx/catering/v1/safety-events?contract=airport_food_contract"
          : "GET /aidx/v1/flight-leg-events?carrier={carrier}&since={watermark}",
      filePattern: undefined,
      authMode: "OAuth2 client credentials",
      watermark: "sample_time_utc / event_time_utc",
      joinKey: "flight_leg_id + station_code",
      transform: `Map event payload to ${metric}`,
    };
  }

  if (sourceId === "excel") {
    return {
      connector: "SFTP Ops Workbooks",
      interfaceName: "SFTP XLSX/CSV landing zone",
      bapiFunction: undefined,
      endpoint: undefined,
      filePattern: `sftp://ops-share/catering/${metric}/YYYY/MM/*_${metric}_daily.xlsx`,
      authMode: "SFTP key pair + file checksum",
      watermark: "service_date + file_received_at",
      joinKey: "service_date + flight_no + station_code",
      transform: "Header validation, type coercion, duplicate-file guard",
    };
  }

  return {
    connector: "ServiceNow Incident Queue",
    interfaceName: "ServiceNow Table API",
    bapiFunction: undefined,
    endpoint: `GET /api/now/table/incident?sysparm_query=u_contract=airport_food_contract^u_kpi_ref=${kpiId}^state!=7`,
    filePattern: undefined,
    authMode: "OAuth2 integration user",
    watermark: "sys_updated_on",
    joinKey: "number + u_kpi_ref",
    transform: "Map incident state and assignment group to remediation status",
  };
}

function buildIntegrationConfig(kpi: any): IntegrationConfig {
  const sourceId = sourceIdForKpiConfig(kpi);
  const requiredHeaders = requiredHeadersForKpi(kpi, sourceId);
  const defaults = sourceDefaultsForKpi(kpi, sourceId);
  return {
    sourceId,
    pollSchedule: sourceId === "excel" ? "On file arrival" : sourceId === "service" ? "Every 15 min" : "Hourly",
    ...defaults,
    requiredHeaders,
    detectedHeaders: requiredHeaders,
    validationStatus: "valid",
  };
}

function buildIntegrationConfigs(kpiRows: any[]) {
  return Object.fromEntries(kpiRows.map((kpi) => [kpi.kpi_id, buildIntegrationConfig(kpi)]));
}

const KPI_EXTRACTION_THINKING = [
  "Reading the airline catering contract and separating service obligations from commercial terms.",
  "Locating clauses that contain measurable commitments: delivery windows, temperature controls, incident response, documentation, and sustainability.",
  "Normalizing thresholds into machine-readable rules such as >= 98.5%, == 100%, <= 30 minutes, and between ranges.",
  "Mapping every KPI to the responsible party so downstream flags know who owns remediation.",
  "Checking whether each clause has a consequence, penalty tier, response SLA, or corrective action requirement.",
  "Deduplicating repeated clause language while preserving penalty tiers as separate trackable records.",
  "Building the KPI registry fields: name, section, type, threshold, unit, party, penalty, and remediation.",
  "Preparing the dashboard in KPI-only mode because actual performance sources are not connected yet.",
  "Final validation: the registry is ready for reviewer inspection before evidence is applied.",
].join("\n\n");

function kpiClauseText(kpi: any) {
  if (kpi?.clause_text) return String(kpi.clause_text);

  const threshold = `${kpi?.operator || ""} ${kpi?.value_min ?? kpi?.value ?? ""}${kpi?.value_max ? ` - ${kpi.value_max}` : ""} ${kpi?.unit || ""}`.trim();
  const trigger = kpi?.trigger_condition || "the stated service obligation";
  const remediation = kpi?.remediation ? ` Remediation: ${kpi.remediation}` : "";
  const penalty = kpi?.consequence_value ? ` Consequence: ${kpi.consequence_value} ${kpi.consequence_unit || ""}.` : "";
  return `${kpi?.name || "KPI obligation"} requires ${trigger} with target ${threshold}.${remediation}${penalty}`;
}

function kpiReferenceActiveHighlight(kpi: any, contractText: string) {
  const candidates = [
    kpiClauseText(kpi),
    kpi?.trigger_condition,
    kpi?.section,
    kpi?.name,
    kpi?.structural_path,
  ]
    .map((candidate) => String(candidate || "").trim())
    .filter(Boolean);

  const lowerContractText = contractText.toLowerCase();
  return candidates.find((candidate) => lowerContractText.includes(candidate.toLowerCase())) || candidates[0] || "";
}

function buildDemoContractReferenceText(kpiRows: any[]) {
  const article3 = kpiRows.filter((kpi) => String(kpi.structural_path || kpi.section || "").includes("ARTICLE III"));
  const article4 = kpiRows.filter((kpi) => String(kpi.structural_path || kpi.section || "").includes("ARTICLE IV"));
  const article6 = kpiRows.filter((kpi) => String(kpi.structural_path || kpi.section || "").includes("ARTICLE VI"));

  const sectionBlock = (rows: any[]) => rows.map((kpi) => [
    `### ${kpi.section || kpi.name}`,
    "",
    kpiClauseText(kpi),
    "",
    `Responsible party: ${kpi.party || "Concessionaire"}.`,
    kpi.remediation ? `Remediation protocol: ${kpi.remediation}` : "",
    kpi.remediation_sla ? `Response SLA: ${kpi.remediation_sla}.` : "",
  ].filter(Boolean).join("\n")).join("\n\n");

  return [
    "# Airline Catering Supplier Contract",
    "",
    "This contract governs catering, meal delivery, operational reporting, and supplier performance obligations for airport food operations.",
    "",
    "## Article III - Commercial Terms",
    "",
    sectionBlock(article3),
    "",
    "## Article IV - Service Levels and Performance Standards",
    "",
    sectionBlock(article4),
    "",
    "## Article VI - Reporting and Audit",
    "",
    sectionBlock(article6),
  ].join("\n");
}

export default function Dashboard() {
  const [contracts, setContracts] = useState<any[]>([]);
  const [selectedContract, setSelectedContract] = useState("");
  const [kpis, setKpis] = useState<any[]>([]);
  const [approvedKpiIds, setApprovedKpiIds] = useState<Set<string>>(() => new Set());
  const [trackedKpiIds, setTrackedKpiIds] = useState<Set<string>>(() => new Set());
  const [removedKpiIds, setRemovedKpiIds] = useState<Set<string>>(() => new Set());
  const [integrationConfigs, setIntegrationConfigs] = useState<Record<string, IntegrationConfig>>({});
  const [breaches, setBreaches] = useState<any[]>([]);
  const [actuals, setActuals] = useState<any[]>([]);
  const [demoPhase, setDemoPhase] = useState<DemoPhase>("contract_only");
  const [demoSourceSync, setDemoSourceSync] = useState<DemoSourceSync>(() => initialSourceSync());
  const [loading, setLoading] = useState(true);
  const [expandedFlag, setExpandedFlag] = useState<string | null>(null);
  const [expandedKpi, setExpandedKpi] = useState<string | null>(null);
  const [tab, setTab] = useState<"kpis" | "integrations" | "flags" | "actuals" | "qa">("kpis");
  const showQaLibrary = false;

  // Phase 2 State
  const [emailModalOpen, setEmailModalOpen] = useState(false);
  const [isGeneratingEmail, setIsGeneratingEmail] = useState(false);
  const [isSendingEmail, setIsSendingEmail] = useState(false);
  const [emailForm, setEmailForm] = useState({ to: "", subject: "", body: "", breachId: "" });
  const [emailToast, setEmailToast] = useState<string | null>(null);
  const [kpiTimeSeries, setKpiTimeSeries] = useState<Record<string, any>>({});
  const [evaluating, setEvaluating] = useState(false);
  const [extractingKpis, setExtractingKpis] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<any[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatSessionId, setChatSessionId] = useState<string | null>(null);
  const [currentQuery, setCurrentQuery] = useState("");
  const [activeArtifact, setActiveArtifact] = useState<{ content: string, type: "svg" | "html" } | null>(null);
  const [chartMode, setChartMode] = useState<"actual" | "cumulative">("actual");
  const [referencedKpi, setReferencedKpi] = useState<any | null>(null);
  const [contractReferenceText, setContractReferenceText] = useState("");
  const [contractReferenceLoading, setContractReferenceLoading] = useState(false);

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

  const resetDashboardPosition = useCallback(() => {
    if (typeof window === "undefined") return;
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, []);

  const activateContractDashboard = useCallback((contractId: string) => {
    setSelectedContract(contractId);
    setJourney("DASHBOARD");
    setTab("kpis");
    setExpandedKpi(null);
    setExpandedFlag(null);
    setReferencedKpi(null);
    setApprovedKpiIds(new Set());
    setTrackedKpiIds(new Set());
    setRemovedKpiIds(new Set());
    setIntegrationConfigs({});
    if (isDemoContractId(contractId)) {
      setDemoPhase("contract_only");
      setDemoSourceSync(initialSourceSync());
      setKpis([]);
      setBreaches([]);
      setActuals([]);
      setKpiTimeSeries({});
    }
    resetDashboardPosition();
  }, [resetDashboardPosition]);

  function initializeKpiReviewState(kpiRows: any[]) {
    setApprovedKpiIds(new Set());
    setTrackedKpiIds(new Set());
    setRemovedKpiIds(new Set());
    setIntegrationConfigs(buildIntegrationConfigs(kpiRows));
  }

  function handleApproveKpiCandidate(kpiId: string) {
    if (!kpis.some((item) => item.kpi_id === kpiId)) return;
    setApprovedKpiIds((previous) => {
      const next = new Set(previous);
      next.add(kpiId);
      return next;
    });
    setRemovedKpiIds((previous) => {
      if (!previous.has(kpiId)) return previous;
      const next = new Set(previous);
      next.delete(kpiId);
      return next;
    });
    setIntegrationConfigs((previous) => {
      if (previous[kpiId]) return previous;
      const kpi = kpis.find((item) => item.kpi_id === kpiId);
      return kpi ? { ...previous, [kpiId]: buildIntegrationConfig(kpi) } : previous;
    });
  }

  function handleApproveAllKpiCandidates() {
    const remainingKpiIds = kpis
      .filter((kpi) => !removedKpiIds.has(kpi.kpi_id))
      .map((kpi) => kpi.kpi_id);

    setApprovedKpiIds(new Set(remainingKpiIds));
    setIntegrationConfigs((previous) => {
      const next = { ...previous };
      kpis.forEach((kpi) => {
        if (!removedKpiIds.has(kpi.kpi_id) && !next[kpi.kpi_id]) {
          next[kpi.kpi_id] = buildIntegrationConfig(kpi);
        }
      });
      return next;
    });
  }

  function handleTrackRecommendedKpis() {
    const recommendedIds = kpis
      .filter((kpi) => approvedKpiIds.has(kpi.kpi_id) && RECOMMENDED_TRACKED_KPI_IDS.has(kpi.kpi_id))
      .map((kpi) => kpi.kpi_id);
    const fallbackIds = recommendedIds.length > 0
      ? recommendedIds
      : kpis
          .filter((kpi) => approvedKpiIds.has(kpi.kpi_id) && !removedKpiIds.has(kpi.kpi_id))
          .slice(0, 7)
          .map((kpi) => kpi.kpi_id);

    setTrackedKpiIds(new Set(fallbackIds));
    setIntegrationConfigs((previous) => {
      const next = { ...previous };
      kpis.forEach((kpi) => {
        if (fallbackIds.includes(kpi.kpi_id) && !next[kpi.kpi_id]) {
          next[kpi.kpi_id] = buildIntegrationConfig(kpi);
        }
      });
      return next;
    });
  }

  function handleToggleKpiTracking(kpiId: string) {
    if (!approvedKpiIds.has(kpiId) || removedKpiIds.has(kpiId)) return;
    setTrackedKpiIds((previous) => {
      const next = new Set(previous);
      if (next.has(kpiId)) next.delete(kpiId);
      else next.add(kpiId);
      return next;
    });
    setIntegrationConfigs((previous) => {
      if (previous[kpiId]) return previous;
      const kpi = kpis.find((item) => item.kpi_id === kpiId);
      return kpi ? { ...previous, [kpiId]: buildIntegrationConfig(kpi) } : previous;
    });
  }

  function handleAmendKpi(kpiId: string, patch: Record<string, any>) {
    if (approvedKpiIds.has(kpiId) || removedKpiIds.has(kpiId)) return;
    setKpis((previous) => previous.map((kpi) => {
      if (kpi.kpi_id !== kpiId) return kpi;
      return { ...kpi, ...patch };
    }));
    setIntegrationConfigs((previous) => {
      const current = previous[kpiId];
      if (!current) return previous;
      const amendedKpi = { ...(kpis.find((item) => item.kpi_id === kpiId) || { kpi_id: kpiId }), ...patch };
      return {
        ...previous,
        [kpiId]: {
          ...current,
          requiredHeaders: current.requiredHeaders?.length ? current.requiredHeaders : requiredHeadersForKpi(amendedKpi, current.sourceId),
        },
      };
    });
  }

  function handleRemovePendingKpi(kpiId: string) {
    if (approvedKpiIds.has(kpiId)) return;
    setRemovedKpiIds((previous) => {
      const next = new Set(previous);
      next.add(kpiId);
      return next;
    });
    setExpandedKpi((current) => current === kpiId ? null : current);
  }

  function handleRestorePendingKpi(kpiId: string) {
    setRemovedKpiIds((previous) => {
      const next = new Set(previous);
      next.delete(kpiId);
      return next;
    });
  }

  function handleUpdateIntegrationConfig(kpiId: string, patch: Partial<IntegrationConfig>) {
    setIntegrationConfigs((previous) => {
      const current = previous[kpiId] || buildIntegrationConfig(kpis.find((item) => item.kpi_id === kpiId) || { kpi_id: kpiId });
      const sourceChanged = patch.sourceId && patch.sourceId !== current.sourceId;
      const kpi = kpis.find((item) => item.kpi_id === kpiId) || { kpi_id: kpiId };
      const nextSourceId = patch.sourceId || current.sourceId;
      const sourceDefaults = sourceChanged ? sourceDefaultsForKpi(kpi, nextSourceId) : {};
      const requestedRequiredHeaders = patch.requiredHeaders || current.requiredHeaders;
      const requiredHeaders = sourceChanged
        ? requiredHeadersForKpi(kpi, nextSourceId)
        : requestedRequiredHeaders;
      return {
        ...previous,
        [kpiId]: {
          ...current,
          ...sourceDefaults,
          ...patch,
          requiredHeaders,
          detectedHeaders: sourceChanged ? requiredHeaders.slice(0, Math.max(2, requiredHeaders.length - 1)) : patch.detectedHeaders || current.detectedHeaders,
          validationStatus: sourceChanged ? "warning" : patch.validationStatus || current.validationStatus,
        },
      };
    });
  }

  function handleApproveKpiReview() {
    if (!kpis.length || trackedKpiIds.size === 0) return;
    setDemoPhase("integration_setup");
    setTab("integrations");
    setExpandedKpi(null);
    upsertGuardianWorkflowMessage(
      `workflow-review-${Date.now()}`,
      workflowMarkdown(
        "KPI review approved",
        "Uploader approved the extracted KPI definitions and selected which approved KPIs should be tracked now.",
        [
          { label: "Review extracted KPI fields", status: "done" },
          { label: `${approvedKpiIds.size} KPIs accepted into the registry`, status: "done" },
          { label: `${trackedKpiIds.size} KPIs selected for active tracking`, status: "done" },
          { label: "Prepare source integration configs", status: "running" },
        ],
        "Accepted-but-untracked KPIs remain in the registry and can be activated when their data source is ready."
      ),
      "KPI review approved",
      false
    );
  }

  async function handleEvaluate() {
    if (!selectedContract || evaluating) return;
    if (isDemoContractId(selectedContract) && demoPhase !== "monitoring_live") {
      await handleConnectSources();
      return;
    }
    setEvaluating(true);
    try {
      await evaluateContract(selectedContract);
      const [b, a] = await Promise.all([fetchBreaches(selectedContract), fetchPerformance(selectedContract)]);
      const actualRows = withDemoFallback(selectedContract, a, DEMO_ACTUALS);
      const breachRows = attachActualSourcesToBreaches(withDemoFallback(selectedContract, b, DEMO_BREACHES), actualRows);
      setBreaches(breachRows);
      setActuals(actualRows);
      setTab("flags");
    } catch (e) {
      console.error(e);
      if (isDemoContractId(selectedContract)) {
        setBreaches(attachActualSourcesToBreaches(DEMO_BREACHES, DEMO_ACTUALS));
        setActuals(DEMO_ACTUALS);
        setTab("flags");
      }
    } finally {
      setEvaluating(false);
    }
  }

  async function handleUpdateStatus(breachId: string, newStatus: string) {
    setBreaches(prev => prev.map(b =>
      (b.breach_id === breachId || b._id === breachId) ? { ...b, status: newStatus } : b
    ));
    if (isDemoContractId(selectedContract)) return;
    try {
      await updateBreach(breachId, { status: newStatus });
    } catch (e) {
      console.error(e);
    }
  }

  async function handleUpdateNotes(breachId: string, newNotes: string) {
    setBreaches(prev => prev.map(b =>
      (b.breach_id === breachId || b._id === breachId) ? { ...b, notes: newNotes } : b
    ));
    if (isDemoContractId(selectedContract)) return;
    try {
      await updateBreach(breachId, { notes: newNotes });
    } catch (e) {
      console.error(e);
    }
  }

  function handleRemoveFlag(breachId: string) {
    setBreaches(prev => prev.filter(b => b.breach_id !== breachId && b._id !== breachId));
    setExpandedFlag(prev => prev === breachId ? null : prev);
  }

  async function handleOpenKpiReference(kpi: any) {
    const fallbackText = buildDemoContractReferenceText(kpis.length ? kpis : DEMO_KPIS);
    const activeClause = kpiClauseText(kpi);

    setReferencedKpi(kpi);
    setContractReferenceText(fallbackText);
    setContractReferenceLoading(Boolean(selectedContract));

    if (!selectedContract) {
      setContractReferenceLoading(false);
      return;
    }

    try {
      const response = await fetchContractText(selectedContract);
      const fetchedText = response?.text || "";
      const lowerFetched = fetchedText.toLowerCase();
      const triggerCondition = String(kpi.trigger_condition || "").trim().toLowerCase();
      const hasDirectClauseMatch =
        fetchedText &&
        (
          lowerFetched.includes(activeClause.toLowerCase()) ||
          (triggerCondition.length > 20 && lowerFetched.includes(triggerCondition))
        );

      setContractReferenceText(
        hasDirectClauseMatch
          ? fetchedText
          : `${fetchedText || fallbackText}\n\n---\n\n## ContractSense Clause Locator\n\n${fallbackText}`
      );
    } catch (error) {
      console.error("Failed to load contract reference", error);
      setContractReferenceText(fallbackText);
    } finally {
      setContractReferenceLoading(false);
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

      if (isDemoContractId(selectedContract) && demoPhase !== "monitoring_live") {
        return;
      }

      if (!kpiTimeSeries[kpiId]) {
        try {
          const data = await getKpiTimeSeries(selectedContract, kpiId);
          setKpiTimeSeries(prev => ({ ...prev, [kpiId]: data }));
        } catch (e) {
          console.error("Failed to load KPI timeseries", e);
          if (isDemoContractId(selectedContract)) {
            setKpiTimeSeries(prev => ({ ...prev, [kpiId]: demoTimeSeries(kpiId) }));
          }
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
      const demoEmail = isDemoContractId(selectedContract) ? buildDemoBreachEmail(breachId) : null;
      setEmailForm({
        to: data.suggested_to || demoEmail?.suggested_to || "",
        subject: data.subject || demoEmail?.subject || "",
        body: data.body || demoEmail?.body || "",
        breachId: breachId
      });
    } catch (e) {
      console.error(e);
      if (isDemoContractId(selectedContract)) {
        const data = buildDemoBreachEmail(breachId);
        setEmailForm({
          to: data.suggested_to || "",
          subject: data.subject,
          body: data.body,
          breachId,
        });
      } else {
        setEmailForm(prev => ({ ...prev, subject: "Error", body: "Failed to generate email template." }));
      }
    } finally {
      setIsGeneratingEmail(false);
    }
  }

  async function handleSendEmail() {
    setIsSendingEmail(true);
    try {
      if (isDemoContractId(selectedContract)) {
        await new Promise(resolve => setTimeout(resolve, 700));
      } else {
        await sendBreachEmail(emailForm.breachId, emailForm);
      }
      setEmailModalOpen(false);
      setEmailToast(`Escalation email sent to ${emailForm.to}.`);
      setTimeout(() => setEmailToast(null), 4500);
    } catch (e) {
      console.error(e);
      setEmailToast("Failed to send escalation email.");
      setTimeout(() => setEmailToast(null), 4500);
    } finally {
      setIsSendingEmail(false);
    }
  }

  async function handleUploadActuals(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file || !selectedContract) return;

    setEvaluating(true);
    try {
      if (isDemoContractId(selectedContract)) {
        const scopedActualRows = DEMO_ACTUALS.filter((actual: any) => trackedKpiIds.has(actual.kpi_id));
        const scopedBreachRows = DEMO_BREACHES.filter((breach: any) => trackedKpiIds.has(breach.kpi_id));
        setActuals(scopedActualRows);
        setBreaches(attachActualSourcesToBreaches(scopedBreachRows, scopedActualRows));
        setDemoSourceSync(Object.fromEntries(CONNECTED_SOURCES.map((source) => [source.id, "connected"])) as DemoSourceSync);
        setDemoPhase("monitoring_live");
        setTab("actuals");
        setEmailToast(
          scopedActualRows.length
            ? `Header validation passed for ${file.name}; rows mapped to accepted KPI configs.`
            : `No KPI has been accepted yet, so ${file.name} was not mapped into tracking.`
        );
        setTimeout(() => setEmailToast(null), 4500);
        return;
      }
      await uploadActualsCsv(selectedContract, file);
      const [p, b] = await Promise.all([
        fetchPerformance(selectedContract),
        fetchBreaches(selectedContract)
      ]);
      const actualRows = withDemoFallback(selectedContract, p, DEMO_ACTUALS);
      const scopedActualRows = isDemoContractId(selectedContract) && trackedKpiIds.size > 0
        ? actualRows.filter((actual: any) => trackedKpiIds.has(actual.kpi_id))
        : actualRows;
      const scopedBreachRows = withDemoFallback(selectedContract, b, DEMO_BREACHES).filter((breach: any) => !isDemoContractId(selectedContract) || trackedKpiIds.size === 0 || trackedKpiIds.has(breach.kpi_id));
      const breachRows = attachActualSourcesToBreaches(scopedBreachRows, scopedActualRows);
      setActuals(scopedActualRows);
      setBreaches(breachRows);
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
        thinking?: string;
        error?: string;
        type?: string;
        content?: string;
        source?: string;
        name?: string;
        args?: Record<string, unknown>;
        confidence?: number;
        reasoning?: string;
        steps?: Array<{ description?: string; task?: string; name?: string }>;
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
              if (data.source === "gemini_thinking") {
                accumulatedGeminiThought += data.content || "";
              } else {
                accumulatedThought += data.content || "";
              }
            } else if (data.type === "intent") {
              const confidence =
                typeof data.confidence === "number"
                  ? ` (${Math.round(data.confidence * 100)}% confidence)`
                  : "";
              accumulatedThought += [
                accumulatedThought ? "\n\n" : "",
                "**What I Am Checking**\n",
                `I need to compare this supplier contract against live KPI performance${confidence}. `,
                data.reasoning || "I will identify the highest exposure, confirm the supporting evidence, and decide the next action to reduce risk this week.",
              ].join("");
            } else if (data.type === "plan") {
              if (Array.isArray(data.steps) && data.steps.length > 0) {
                accumulatedPlan += data.steps
                  .map((step: any, index: number) => `${index + 1}. ${step.description || step.task || step.name || "Analyze request"}`)
                  .join("\n");
              } else {
                accumulatedPlan += data.content || "";
              }
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

        const preparedContracts = prepareDemoContracts(active || []);
        setContracts(preparedContracts);
        setSelectedContract(prev => prev || preparedContracts[0]?.contract_id || DEMO_CONTRACT_ID);
        setAvailableContracts(available || []);
        refreshMemoryFacts().catch(e => console.error(e));
      } catch (e) {
        console.error("Initial load error:", e);
        setContracts(prepareDemoContracts([]));
        setSelectedContract(prev => prev || DEMO_CONTRACT_ID);
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
    active: boolean,
    extra: Record<string, unknown> = {}
  ) {
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
        ...extra,
      };

      if (prev.some((message) => message.id === messageId)) {
        return prev.map((message) => message.id === messageId ? { ...message, ...nextMessage } : message);
      }
      return [...prev, nextMessage];
    });
  }

  function updateGuardianMessage(messageId: string, patch: Record<string, unknown>) {
    setChatMessages(prev => prev.map((message) => (
      message.id === messageId ? { ...message, ...patch } : message
    )));
  }

  async function typeGuardianThinking(messageId: string, fullText: string, durationMs = 30000) {
    const tickMs = 180;
    const totalTicks = Math.max(1, Math.floor(durationMs / tickMs));
    const charsPerTick = Math.max(1, Math.ceil(fullText.length / totalTicks));

    for (let cursor = charsPerTick; cursor < fullText.length; cursor += charsPerTick) {
      updateGuardianMessage(messageId, {
        geminiThought: fullText.slice(0, cursor),
        isStreaming: true,
      });
      await wait(tickMs);
    }

    updateGuardianMessage(messageId, {
      geminiThought: fullText,
      isStreaming: true,
    });
  }

  async function handleIngestContract(filename: string) {
    const messageId = `workflow-ingest-${Date.now()}`;
    setJourney("DASHBOARD");
    setDemoPhase("contract_only");
    setDemoSourceSync(initialSourceSync());
    setKpis([]);
    setBreaches([]);
    setActuals([]);
    setKpiTimeSeries({});
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

      const newContracts = await fetchContracts().catch(() => contracts);

      setContracts(prepareDemoContracts(newContracts || []));
      setSelectedContract(ingestRes.contract_id);
      setTab("kpis");
      setDemoSourceSync(initialSourceSync());
      setKpis([]);
      setBreaches([]);
      setActuals([]);

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
      const shouldUseDemoFallback = isDemoContractId(selectedContract) || /airport|food|catering/i.test(filename);
      if (shouldUseDemoFallback) {
        setContracts(prepareDemoContracts(contracts));
        setSelectedContract(DEMO_CONTRACT_ID);
        setTab("kpis");
        setDemoSourceSync(initialSourceSync());
        setKpis([]);
        setBreaches([]);
        setActuals([]);
        upsertGuardianWorkflowMessage(
          messageId,
          workflowMarkdown(
            "Contract ingestion complete",
            "Using cached airline catering contract for the demo.",
            [
              { label: "Load cached contract record", status: "done" },
              { label: "Parse contract structure", status: "done" },
              { label: "Prepare KPI extraction", status: "done" },
            ],
            "KPI extraction is ready. Actual performance data has not been connected yet."
          ),
          "Contract ingestion complete",
          false
        );
        return true;
      }
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
      true,
      { geminiThought: "" }
    );

    if (isDemoContractId(selectedContract)) {
      setDemoPhase("extracting_kpis");
      setDemoSourceSync(initialSourceSync());
      setKpis([]);
      setBreaches([]);
      setActuals([]);
      setTab("kpis");
      upsertGuardianWorkflowMessage(
        messageId,
        workflowMarkdown(
          "KPI extraction running live",
          `Contract: \`${selectedContract}\``,
          [
            { label: "Initialize KPI extraction", status: "done" },
            { label: "Scan indexed clauses", status: "running" },
            { label: "Extract thresholds, parties, penalties, and remediation terms", status: "running" },
            { label: "Refresh KPI registry", status: "pending" },
          ],
          "Contract Guardian is typing through the extraction workstream."
        ),
        "Extracting KPI registry...",
        true,
        { geminiThought: "" }
      );
      await typeGuardianThinking(messageId, KPI_EXTRACTION_THINKING, 30000);
      upsertGuardianWorkflowMessage(
        messageId,
        workflowMarkdown(
          "KPI extraction finalizing",
          `Contract: \`${selectedContract}\``,
          [
            { label: "Initialize KPI extraction", status: "done" },
            { label: "Scan indexed clauses", status: "done" },
            { label: "Extract thresholds, parties, penalties, and remediation terms", status: "done" },
            { label: "Refresh KPI registry", status: "running" },
          ],
          "Using cached extraction output because the model key is exhausted."
        ),
        "Refreshing KPI registry...",
        true,
        { geminiThought: KPI_EXTRACTION_THINKING }
      );
      const extractedRows = await fetchKPIs(selectedContract).catch(() => DEMO_KPIS);
      const demoKpiRows = extractedRows?.length ? extractedRows : DEMO_KPIS;
      setKpis(demoKpiRows);
      initializeKpiReviewState(demoKpiRows);
      setBreaches([]);
      setActuals([]);
      setDemoPhase("review_kpis");
      setTab("kpis");
      upsertGuardianWorkflowMessage(
        messageId,
        workflowMarkdown(
          "KPI extraction complete - KPI review required",
          `Contract: \`${selectedContract}\``,
          [
            { label: "Initialize KPI extraction", status: "done" },
            { label: "Scan indexed clauses", status: "done" },
            { label: `Extract ${demoKpiRows.length} KPI records`, status: "done" },
            { label: "Wait for uploader approval", status: "running" },
          ],
          "Reviewer must amend fields as needed, accept valid KPI candidates, choose which accepted KPIs to track now, or remove unwanted KPI candidates before monitoring is populated."
        ),
        "KPI extraction ready for review",
        false,
        { geminiThought: KPI_EXTRACTION_THINKING }
      );
      setChatOpen(false);
      setExtractingKpis(false);
      return;
    }

    try {
      const extractRes = await extractKPIs(selectedContract);
      const extractedKpis = withDemoFallback(selectedContract, extractRes.kpis, DEMO_KPIS);
      setKpis(extractedKpis);
      setApprovedKpiIds(new Set(extractedKpis.map((kpi: any) => kpi.kpi_id)));
      setTrackedKpiIds(new Set(extractedKpis.map((kpi: any) => kpi.kpi_id)));
      setIntegrationConfigs(buildIntegrationConfigs(extractedKpis));
      const extractedCount = extractRes.kpis_count ?? extractedKpis.length;
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
      const kpiRows = withDemoFallback(selectedContract, k, DEMO_KPIS);
      const actualRows = withDemoFallback(selectedContract, a, DEMO_ACTUALS);
      const breachRows = attachActualSourcesToBreaches(withDemoFallback(selectedContract, b, DEMO_BREACHES), actualRows);
      setKpis(kpiRows);
      setBreaches(breachRows);
      setActuals(actualRows);
      setTab("kpis");
      upsertGuardianWorkflowMessage(
        messageId,
        workflowMarkdown(
          "KPI extraction complete",
          `Contract: \`${selectedContract}\``,
          [
            { label: "Initialize KPI extraction", status: "done" },
            { label: "Scan indexed clauses", status: "done" },
            { label: `Extract ${kpiRows.length || extractedCount} KPI records`, status: "done" },
            { label: "Refresh KPI registry", status: "done" },
          ],
          "The KPI registry has been updated."
        ),
        "KPI extraction complete",
        false
      );
    } catch (e) {
      console.error(e);
      if (isDemoContractId(selectedContract)) {
        setKpis(DEMO_KPIS);
        setBreaches(attachActualSourcesToBreaches(DEMO_BREACHES, DEMO_ACTUALS));
        setActuals(DEMO_ACTUALS);
        setTab("kpis");
      }
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

  async function handleConnectSources() {
    if (!selectedContract || evaluating) return;
    if (isDemoContractId(selectedContract) && kpis.length === 0) {
      await handleExtractKpis();
      return;
    }
    if (isDemoContractId(selectedContract) && demoPhase === "review_kpis") {
      handleApproveKpiReview();
      return;
    }
    if (isDemoContractId(selectedContract) && trackedKpiIds.size === 0) {
      setTab("kpis");
      return;
    }

    const messageId = `workflow-sources-${Date.now()}`;
    setEvaluating(true);
    setChatOpen(false);
    setDemoPhase("connecting_sources");
    setDemoSourceSync(initialSourceSync());
    setTab("actuals");
    setBreaches([]);
    setActuals([]);
    upsertGuardianWorkflowMessage(
      messageId,
      workflowMarkdown(
        "Source connection started",
        "Connecting evidence streams for the airline catering contract.",
        [
          { label: "Connect ERP dispatch data", status: "running" },
          { label: "Connect REST monitoring endpoints", status: "pending" },
          { label: "Load Excel workbooks", status: "pending" },
          { label: "Evaluate actuals against KPI registry", status: "pending" },
        ]
      ),
      "Connecting evidence sources...",
      true
    );

    try {
      if (isDemoContractId(selectedContract)) {
        await wait(500);
        const [storedActualRows, storedBreachRows] = await Promise.all([
          fetchPerformance(selectedContract).catch(() => []),
          fetchBreaches(selectedContract).catch(() => []),
        ]);
        const actualRows = storedActualRows.length ? storedActualRows : DEMO_ACTUALS;
        const sourceBreaches = storedBreachRows.length ? storedBreachRows : DEMO_BREACHES;
        const trackedIds = trackedKpiIds;
        const trackedActualRows = actualRows.filter((actual: any) => trackedIds.has(actual.kpi_id));
        const trackedSourceBreaches = sourceBreaches.filter((breach: any) => trackedIds.has(breach.kpi_id));
        const breachRows = attachActualSourcesToBreaches(trackedSourceBreaches, trackedActualRows);
        const sourceBatches = groupActualsBySource(trackedActualRows);
        let loadedRows: any[] = [];

        for (let index = 0; index < CONNECTED_SOURCES.length; index += 1) {
          const source = CONNECTED_SOURCES[index];
          const batch = sourceBatches[source.id] || [];
          const sourceSteps = CONNECTED_SOURCES.map((item, stepIndex) => ({
            label: `${stepIndex < index ? "Connected" : stepIndex === index ? "Connecting" : "Queue"} ${item.label}`,
            status: stepIndex < index ? "done" as const : stepIndex === index ? "running" as const : "pending" as const,
          }));

          setDemoSourceSync(prev => ({ ...prev, [source.id]: "syncing" }));
          upsertGuardianWorkflowMessage(
            messageId,
            workflowMarkdown(
              `Connecting ${source.label}`,
              "Actual records are arriving from connected systems one source at a time.",
              [
                ...sourceSteps,
                { label: "Evaluate actuals against KPI registry", status: "pending" },
              ],
              `${loadedRows.length.toLocaleString()} records loaded so far.`
            ),
            `Connecting ${source.label}...`,
            true,
            {
              geminiThought: [
                `Opening ${source.type} source: ${source.label}.`,
                `Mapping records to the KPI registry before they affect compliance metrics.`,
                `${loadedRows.length.toLocaleString()} rows are already staged in the actuals log.`,
              ].join("\n\n"),
            }
          );

          if (batch.length > 0) {
            const previewCount = Math.max(1, Math.ceil(batch.length * 0.35));
            setActuals([...loadedRows, ...batch.slice(0, previewCount)]);
          }

          await wait(1500);

          loadedRows = [...loadedRows, ...batch];
          setActuals(loadedRows);
          setDemoSourceSync(prev => ({ ...prev, [source.id]: "connected" }));
          upsertGuardianWorkflowMessage(
            messageId,
            workflowMarkdown(
              `${source.label} connected`,
              "Actual records are being appended to the performance log.",
              [
                ...CONNECTED_SOURCES.map((item, stepIndex) => ({
                  label: `${stepIndex <= index ? "Connected" : "Queue"} ${item.label}`,
                  status: stepIndex <= index ? "done" as const : "pending" as const,
                })),
                { label: "Evaluate actuals against KPI registry", status: index === CONNECTED_SOURCES.length - 1 ? "running" : "pending" },
              ],
              `${loadedRows.length.toLocaleString()} actual records loaded.`
            ),
            `${source.label} connected`,
            true,
            {
              geminiThought: [
                `${source.label} is connected.`,
                `Loaded ${batch.length.toLocaleString()} records from this source.`,
                `${loadedRows.length.toLocaleString()} total actual records are now visible in the log.`,
              ].join("\n\n"),
            }
          );

          await wait(900);
        }

        setKpis(prev => prev.length ? prev : DEMO_KPIS);
        setActuals(trackedActualRows);
        setBreaches(breachRows);
        setExpandedFlag(breachRows[0]?.breach_id || null);
        setDemoSourceSync(Object.fromEntries(CONNECTED_SOURCES.map((source) => [source.id, "connected"])) as DemoSourceSync);
        setDemoPhase("monitoring_live");
        upsertGuardianWorkflowMessage(
          messageId,
          workflowMarkdown(
            "Sources connected",
            "Evidence streams are connected and the dashboard is populated.",
            [
              { label: "Connect ERP dispatch data", status: "done" },
              { label: "Connect REST monitoring endpoints", status: "done" },
              { label: "Load Excel workbooks", status: "done" },
              { label: "Evaluate actuals against KPI registry", status: "done" },
            ],
            `${trackedActualRows.length} actual records loaded for ${trackedIds.size} tracked KPIs and ${breachRows.length} breach signals detected.`
          ),
          "Sources connected",
          false
        );
        return;
      }

      setEvaluating(false);
      await handleEvaluate();
    } finally {
      setEvaluating(false);
    }
  }

  useEffect(() => {
    if (!selectedContract) return;
    if (isDemoContractId(selectedContract) && demoPhase !== "monitoring_live") {
      setLoading(false);
      if (demoPhase === "contract_only") {
        setKpis([]);
        setBreaches([]);
        setActuals([]);
        setExpandedFlag(null);
        setExpandedKpi(null);
      }
      return;
    }

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
        const kpiRows = withDemoFallback(selectedContract, k, DEMO_KPIS);
        const actualRows = withDemoFallback(selectedContract, a, DEMO_ACTUALS);
        const breachRows = attachActualSourcesToBreaches(withDemoFallback(selectedContract, b, DEMO_BREACHES), actualRows);
        const scopedActualRows = isDemoContractId(selectedContract)
          ? actualRows.filter((actual: any) => trackedKpiIds.has(actual.kpi_id))
          : actualRows;
        const scopedBreachRows = isDemoContractId(selectedContract)
          ? breachRows.filter((breach: any) => trackedKpiIds.has(breach.kpi_id))
          : breachRows;
        setKpis(kpiRows);
        if (!isDemoContractId(selectedContract)) {
          setApprovedKpiIds(new Set(kpiRows.map((kpi: any) => kpi.kpi_id)));
          setTrackedKpiIds(new Set(kpiRows.map((kpi: any) => kpi.kpi_id)));
          setIntegrationConfigs(buildIntegrationConfigs(kpiRows));
        } else if (trackedKpiIds.size === 0 && kpiRows.length > 0 && demoPhase === "monitoring_live") {
          initializeKpiReviewState(kpiRows);
        }
        setBreaches(scopedBreachRows);
        setActuals(scopedActualRows);
        if (isDemoContractId(selectedContract)) {
          setExpandedFlag(prev => prev || scopedBreachRows[0]?.breach_id || null);
        }
        refreshMemoryFacts().catch(e => console.error("Facts load error:", e));
      } catch (e) {
        console.error("Dashboard data load error:", e);
        if (isDemoContractId(selectedContract)) {
          setKpis(DEMO_KPIS);
          if (trackedKpiIds.size === 0) initializeKpiReviewState(DEMO_KPIS);
          const scopedActualRows = DEMO_ACTUALS.filter((actual: any) => trackedKpiIds.has(actual.kpi_id));
          const scopedBreachRows = attachActualSourcesToBreaches(
            DEMO_BREACHES.filter((breach: any) => trackedKpiIds.has(breach.kpi_id)),
            scopedActualRows
          );
          setActuals(scopedActualRows);
          setBreaches(scopedBreachRows);
          setExpandedFlag(scopedBreachRows[0]?.breach_id || null);
        }
      } finally {
        setLoading(false);
        clearTimeout(timer);
      }
    })();

    return () => clearTimeout(timer);
  }, [selectedContract, demoPhase]);

  useEffect(() => {
    if (journey !== "DASHBOARD") return;

    resetDashboardPosition();
    const frame = window.requestAnimationFrame(resetDashboardPosition);
    const timer = window.setTimeout(resetDashboardPosition, 250);

    return () => {
      window.cancelAnimationFrame(frame);
      window.clearTimeout(timer);
    };
  }, [journey, selectedContract, resetDashboardPosition]);

  useEffect(() => {
    if (journey !== "LANDING" || contracts.length === 0) return;
    const airportContract = contracts.find((contract) => isDemoContractId(contract.contract_id));
    if (airportContract && !isDemoContractId(selectedContract)) {
      setSelectedContract(airportContract.contract_id);
    }
  }, [contracts, journey, selectedContract]);

  useEffect(() => {
    if (tab !== "qa" || !selectedContract) return;
    if (!showQaLibrary) {
      setTab("kpis");
      return;
    }
    (async () => {
      try {
        const res = await fetchSavedQA(selectedContract);
        setSavedQA(res.items || []);
      } catch (e) {
        console.error("Failed to load saved QA", e);
      }
    })();
  }, [tab, selectedContract, showQaLibrary]);

  const isDemoLifecycle = isDemoContractId(selectedContract);
  const actualEvidenceConnected = !isDemoLifecycle || demoPhase === "connecting_sources" || demoPhase === "monitoring_live";
  const monitoringLive = !isDemoLifecycle || demoPhase === "monitoring_live";
  const activeTrackingIds = useMemo(() => {
    if (!isDemoLifecycle) return new Set(kpis.map((kpi) => kpi.kpi_id));
    return trackedKpiIds;
  }, [isDemoLifecycle, kpis, trackedKpiIds]);
  const trackedKpis = useMemo(() => {
    if (!isDemoLifecycle) return kpis;
    return kpis.filter((kpi) => activeTrackingIds.has(kpi.kpi_id));
  }, [activeTrackingIds, isDemoLifecycle, kpis]);
  const visibleActuals = actualEvidenceConnected
    ? actuals.filter((actual) => !isDemoLifecycle || activeTrackingIds.has(actual.kpi_id))
    : [];
  const visibleBreaches = monitoringLive
    ? breaches.filter((breach) => !isDemoLifecycle || activeTrackingIds.has(breach.kpi_id))
    : [];
  const visibleActualCountsBySource = useMemo(() => {
    const grouped = groupActualsBySource(visibleActuals);
    return Object.fromEntries(Object.entries(grouped).map(([sourceId, rows]) => [sourceId, rows.length]));
  }, [visibleActuals]);

  // Derived Analytics useMemos
  const kpiTypeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    trackedKpis.forEach(k => { const t = k.kpi_type || "other"; counts[t] = (counts[t] || 0) + 1; });
    return Object.entries(counts).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);
  }, [trackedKpis]);

  const penaltyByParty = useMemo(() => {
    const m: Record<string, number> = {};
    trackedKpis.forEach(k => { const p = k.party || "Unspecified"; m[p] = (m[p] || 0) + (k.consequence_value || 0); });
    return Object.entries(m).map(([name, value]) => ({ name: name.substring(0, 20), value })).filter(x => x.value > 0).sort((a, b) => b.value - a.value);
  }, [trackedKpis]);

  const complianceRate = useMemo(() => {
    if (!visibleBreaches.length) return 100;
    const onTrack = visibleBreaches.filter(b => !b.is_breach).length;
    return parseFloat(((onTrack / visibleBreaches.length) * 100).toFixed(1));
  }, [visibleBreaches]);

  const breachStatusCounts = useMemo(() => {
    const c: Record<string, number> = { Open: 0, "In Progress": 0, Resolved: 0, Waived: 0 };
    visibleBreaches.filter(b => b.is_breach).forEach(b => { const s = b.status || "Open"; c[s] = (c[s] || 0) + 1; });
    return Object.entries(c).map(([name, value]) => ({ name, value }));
  }, [visibleBreaches]);

  const severityStatusMatrix = useMemo(() => {
    const mx: Record<string, Record<string, number>> = {};
    (["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const).forEach(s => { mx[s] = { Open: 0, "In Progress": 0, Resolved: 0, Waived: 0 }; });
    visibleBreaches.forEach(b => { const sev = classifySeverity(b); const st = b.status || "Open"; if (mx[sev]?.[st] !== undefined) mx[sev][st]++; });
    return mx;
  }, [visibleBreaches]);

  const actualVsThreshold = useMemo(() => {
    return visibleBreaches
      .filter(b => b.threshold_value != null)
      .map(b => {
        const kpi = trackedKpis.find(k => k.kpi_id === b.kpi_id);
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
  }, [visibleBreaches, trackedKpis]);

  const penaltyAccrualData = useMemo(() => {
    if (!visibleBreaches.length) return [];
    const sorted = visibleBreaches.filter(b => b.is_breach && b.penalty_amount > 0 && b.timestamp)
      .sort((a, b) => (a.timestamp || "").localeCompare(b.timestamp || ""));
    let cum = 0;
    return sorted.map(b => {
      cum += b.penalty_amount || 0;
      const kpi = trackedKpis.find(k => k.kpi_id === b.kpi_id);
      let dl = ""; try { dl = new Date(b.timestamp).toLocaleDateString(undefined, { month: "short", day: "numeric" }); } catch { dl = b.timestamp || ""; }
      return { date: dl, penalty: b.penalty_amount, cumulative: cum, kpi: (kpi?.name || b.kpi_id || "").substring(0, 15) };
    });
  }, [visibleBreaches, trackedKpis]);

  const activeBreaches = visibleBreaches.filter(b => b.is_breach);
  const flags = visibleBreaches.map(b => {
    const kpi = trackedKpis.find(k => k.kpi_id === b.kpi_id);
    return { ...b, severity: classifySeverity(b), kpi };
  }).sort((a, b) => {
    const order = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
    return (order[a.severity as keyof typeof order] ?? 4) - (order[b.severity as keyof typeof order] ?? 4);
  });

  const sevCounts = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
  flags.forEach(f => { if (f.severity in sevCounts) sevCounts[f.severity as keyof typeof sevCounts]++; });
  const totalExposure = flags.reduce((s, f) => s + (f.penalty_amount || 0), 0);
  const evaluatedKpiIds = new Set(visibleBreaches.map(b => b.kpi_id));
  const trackedKpiCount = isDemoLifecycle ? trackedKpiIds.size : kpis.length;
  const demoPrimaryLabel =
    demoPhase === "contract_only" || demoPhase === "extracting_kpis"
      ? extractingKpis ? "Extracting..." : "Extract KPIs"
      : demoPhase === "review_kpis"
        ? "Continue to Integrations"
        : demoPhase === "integration_setup"
          ? "Connect Sources"
          : demoPhase === "connecting_sources"
            ? "Connecting..."
            : "Re-evaluate";
  const handlePrimaryDashboardAction = () => {
    if (isDemoLifecycle && !monitoringLive) {
      if (demoPhase === "contract_only" || demoPhase === "extracting_kpis") {
        void handleExtractKpis();
      } else if (demoPhase === "review_kpis") {
        handleApproveKpiReview();
      } else {
        void handleConnectSources();
      }
      return;
    }
    void handleEvaluate();
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
            <h2 className="text-lg font-semibold text-gray-800">Contract Performance Dashboard</h2>
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
        selectedContractId={selectedContract}
        availableContracts={availableContracts}
        onSelectContract={activateContractDashboard}
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

      {referencedKpi && (
        <div className="fixed inset-0 z-[65] flex items-center justify-center bg-slate-950/35 p-4 backdrop-blur-sm">
          <div className="flex h-[88vh] w-full max-w-7xl flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-100 bg-white px-5 py-3">
              <div className="min-w-0">
                <p className="text-[10px] font-bold uppercase tracking-wide text-blue-600">Contract Reference</p>
                <h2 className="truncate text-base font-bold text-slate-900">{referencedKpi.name}</h2>
              </div>
              <button
                onClick={() => setReferencedKpi(null)}
                className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
                aria-label="Close contract reference"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="grid min-h-0 flex-1 grid-cols-1 gap-0 lg:grid-cols-[390px_minmax(0,1fr)]">
              <aside className="min-h-0 overflow-y-auto border-b border-slate-100 bg-slate-50/70 p-5 lg:border-b-0 lg:border-r">
                <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="mb-3 flex items-start justify-between gap-3">
                    <div>
                      <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">{referencedKpi.kpi_id}</p>
                      <h3 className="mt-1 text-sm font-bold text-slate-900">{referencedKpi.name}</h3>
                    </div>
                    <span className="rounded-full border border-blue-100 bg-blue-50 px-2 py-1 text-[10px] font-bold uppercase text-blue-700">
                      {referencedKpi.kpi_type || "kpi"}
                    </span>
                  </div>

                  <div className="space-y-3 text-xs">
                    <div>
                      <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Contract Location</p>
                      <p className="mt-1 font-semibold text-slate-800">{referencedKpi.structural_path || referencedKpi.section || "Mapped clause"}</p>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="rounded-lg border border-blue-100 bg-blue-50 p-3">
                        <p className="text-[10px] font-bold uppercase text-blue-600">Threshold</p>
                        <p className="mt-1 text-sm font-bold text-blue-900">
                          {referencedKpi.operator} {referencedKpi.value_min ?? referencedKpi.value}
                          {referencedKpi.value_max ? ` - ${referencedKpi.value_max}` : ""}
                        </p>
                        <p className="text-[10px] text-blue-600">{referencedKpi.unit}</p>
                      </div>
                      <div className="rounded-lg border border-slate-200 bg-white p-3">
                        <p className="text-[10px] font-bold uppercase text-slate-400">Party</p>
                        <p className="mt-1 text-sm font-bold text-slate-800">{referencedKpi.party || "Unassigned"}</p>
                      </div>
                    </div>
                    <div>
                      <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Clause Evidence</p>
                      <p className="mt-1 rounded-lg border border-amber-100 bg-amber-50 p-3 leading-relaxed text-amber-900">
                        {kpiClauseText(referencedKpi)}
                      </p>
                    </div>
                    {referencedKpi.remediation && (
                      <div>
                        <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Remediation</p>
                        <p className="mt-1 leading-relaxed text-slate-700">{referencedKpi.remediation}</p>
                      </div>
                    )}
                  </div>
                </div>
              </aside>

              <main className="min-h-0 bg-slate-50 p-4">
                <ContractViewer
                  text={contractReferenceText}
                  isLoading={contractReferenceLoading}
                  highlightTexts={[
                    kpiClauseText(referencedKpi),
                    referencedKpi.section,
                    referencedKpi.structural_path,
                    referencedKpi.trigger_condition,
                    referencedKpi.name,
                  ].filter(Boolean)}
                  highlightText={kpiClauseText(referencedKpi)}
                  activeHighlightText={kpiReferenceActiveHighlight(referencedKpi, contractReferenceText)}
                />
              </main>
            </div>
          </div>
        </div>
      )}

      {emailToast && (
        <div className="fixed right-6 top-20 z-[70] rounded-lg border border-emerald-200 bg-white px-4 py-3 text-sm font-semibold text-emerald-700 shadow-lg">
          {emailToast}
        </div>
      )}

      <div className={`transition-all duration-700 ease-in-out ${journey !== "DASHBOARD" ? "blur-xl scale-[0.95] brightness-75 pointer-events-none" : ""}`}>

        {/* Header */}
        <div className="border-b border-gray-200 bg-white fixed top-0 w-full z-40">
          <div className="max-w-[1800px] mx-auto px-6 py-3">
            <div className="flex items-center justify-between gap-6">
            <div className="flex min-w-0 items-center gap-3">
              <button
                onClick={() => setJourney("LANDING")}
                className="flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-800 -ml-2"
              >
                <ArrowLeft className="h-4 w-4" /> Back
              </button>
              <div className="h-5 w-px shrink-0 bg-gray-200" />
              <div className="min-w-0">
                <h1 className="truncate text-base font-bold text-gray-800">Contract Performance Dashboard</h1>
                <div className="mt-0.5 flex items-center gap-2">
                  <select
                    value={selectedContract}
                    onChange={e => activateContractDashboard(e.target.value)}
                    className="max-w-[280px] cursor-pointer truncate border-none bg-transparent p-0 text-xs font-semibold text-[#0084C7] focus:ring-0"
                  >
                    {contracts.map((c, index) => <option key={`${c.contract_id}-${index}`} value={c.contract_id}>{c.contract_id}</option>)}
                  </select>
                </div>
              </div>
            </div>

            <div className="flex shrink-0 flex-nowrap items-center justify-end gap-2">
              <div className="relative">
                <input
                  type="file"
                  id="actuals-upload"
                  className="hidden"
                  accept=".csv,.xlsx"
                  onChange={handleUploadActuals}
                />
                <button
                  onClick={() => document.getElementById('actuals-upload')?.click()}
                  disabled={evaluating}
                  className="flex items-center gap-1.5 whitespace-nowrap rounded-md border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-500 shadow-sm transition-colors hover:text-gray-800"
                >
                  <Upload className="h-3.5 w-3.5" /> Upload Actuals
                </button>
              </div>
              <button
                onClick={() => setChatOpen(prev => !prev)}
                className="flex items-center gap-1.5 whitespace-nowrap rounded-md bg-slate-800 px-3 py-1.5 text-xs font-medium text-white shadow-sm transition-colors hover:bg-slate-950 active:scale-95"
              >
                <Bot className="h-3.5 w-3.5" /> Quick Chat
              </button>
              <div className="relative group">
                <button className="flex items-center gap-1.5 whitespace-nowrap rounded-md border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-500 shadow-sm transition-colors hover:text-gray-800">
                  <Download className="h-3.5 w-3.5" /> Export <ChevronDown className="h-3 w-3 opacity-50" />
                </button>
                <div className="absolute right-0 top-full mt-1 w-32 bg-white rounded-lg shadow-lg border border-gray-100 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50 overflow-hidden">
                  <button onClick={handleExportCsv} className="w-full text-left px-4 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50">CSV Report</button>
                  <button onClick={handleExportJson} className="w-full text-left px-4 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50">Raw JSON</button>
                </div>
              </div>
              <button onClick={handlePrimaryDashboardAction} disabled={evaluating || extractingKpis || (isDemoLifecycle && demoPhase === "review_kpis" && trackedKpiIds.size === 0)}
                className={`flex items-center gap-1.5 whitespace-nowrap rounded-md border px-3 py-1.5 text-xs font-medium shadow-sm transition-colors ${evaluating || extractingKpis ? "bg-[#0084C7] text-white border-[#0084C7]" : "text-gray-500 hover:text-gray-800 bg-white border-gray-200"}`}>
                <RefreshCw className={`h-3.5 w-3.5 ${evaluating || extractingKpis ? "animate-spin" : ""}`} />
                {isDemoLifecycle && !monitoringLive ? demoPrimaryLabel : evaluating ? "Evaluating..." : "Re-evaluate"}
              </button>
            </div>
            </div>
          </div>
        </div>

        <div className={`transition-all duration-500 ${activeArtifact ? "blur-md scale-[0.98] pointer-events-none brightness-95" : ""}`}>
          <div className="max-w-[1800px] mx-auto px-6 pt-24 space-y-5 pb-20">
            {/* Summary Cards */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <SummaryCard label="Compliance Rate" value={monitoringLive ? `${complianceRate}%` : "Pending"} color={monitoringLive ? (complianceRate >= 90 ? "text-green-700" : complianceRate >= 70 ? "text-amber-700" : "text-red-700") : "text-slate-500"} bg={monitoringLive ? (complianceRate >= 90 ? "bg-green-50" : complianceRate >= 70 ? "bg-amber-50" : "bg-red-50") : "bg-slate-50"} border={monitoringLive ? (complianceRate >= 90 ? "border-green-200" : complianceRate >= 70 ? "border-amber-200" : "border-red-200") : "border-slate-200"} icon={<ShieldCheck className={`h-4 w-4 ${monitoringLive ? (complianceRate >= 90 ? "text-green-700" : complianceRate >= 70 ? "text-amber-700" : "text-red-700") : "text-slate-500"}`} />} />
              <SummaryCard label="KPIs Tracked" value={`${monitoringLive && visibleBreaches.length > 0 ? evaluatedKpiIds.size : trackedKpiCount} / ${kpis.length}`} color="text-[#0084C7]" bg="bg-blue-50" border="border-blue-200" icon={<BarChart3 className="h-4 w-4 text-[#0084C7]" />} />
              <SummaryCard label="Critical / High" value={`${sevCounts.CRITICAL} / ${sevCounts.HIGH}`} color="text-red-700" bg="bg-red-50" border="border-red-200" icon={<AlertCircle className="h-4 w-4 text-red-700" />} />
              <SummaryCard label="Active Breaches" value={activeBreaches.filter(b => b.status !== "Resolved" && b.status !== "Waived").length} color="text-orange-700" bg="bg-orange-50" border="border-orange-200" icon={<AlertTriangle className="h-4 w-4 text-orange-700" />} />
              <SummaryCard label="Current Exposure" value={`$${totalExposure.toLocaleString()}`} color="text-red-700" bg="bg-white" border="border-gray-200" icon={<DollarSign className="h-4 w-4 text-red-700" />} />
            </div>

            {isDemoLifecycle && !monitoringLive && (
              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="max-w-2xl">
                    <p className="text-[10px] font-bold uppercase tracking-wide text-[#0084C7]">Demo Lifecycle</p>
                    <h2 className="mt-1 text-base font-bold text-slate-900">
                      {demoPhase === "contract_only" && "Contract ingested. KPI extraction is pending."}
                      {demoPhase === "extracting_kpis" && "Extracting KPI registry from the contract."}
                      {demoPhase === "review_kpis" && "KPI review required before tracking starts."}
                      {demoPhase === "integration_setup" && "Configure evidence sources for the approved KPIs."}
                      {demoPhase === "connecting_sources" && "Sources are connecting. Actual data is starting to arrive."}
                    </h2>
                    <p className="mt-2 text-sm leading-relaxed text-slate-500">
                      {demoPhase === "contract_only" &&
                        "At this stage ContractSense has the contract document, but no KPI registry or operational actuals have been loaded into the dashboard."}
                      {demoPhase === "extracting_kpis" &&
                        "The model step is simulated with cached extraction output because the API key is exhausted, so the demo can still show the intended workflow."}
                      {demoPhase === "review_kpis" &&
                        "The uploader can amend extracted fields, accept valid KPI candidates, choose which accepted KPIs should be tracked now, or remove unwanted candidates. Accepted-but-untracked KPIs stay in the registry for later."}
                      {demoPhase === "integration_setup" &&
                        "Each tracked KPI has a source configuration: ERP BAPI calls, REST endpoints, workbook patterns, polling schedule, and CSV/XLSX header validation."}
                      {demoPhase === "connecting_sources" &&
                        "ERP, API, workbook, and ticketing records are being mapped to the KPI registry. The performance log will show records first, then the dashboard will populate."}
                    </p>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    {(demoPhase === "contract_only" || demoPhase === "extracting_kpis") && (
                      <button
                        onClick={handleExtractKpis}
                        disabled={extractingKpis}
                        className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-4 py-2 text-xs font-bold text-white shadow-sm transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        <Sparkles className={`h-3.5 w-3.5 ${extractingKpis ? "animate-pulse" : ""}`} />
                        {extractingKpis ? "Extracting KPIs..." : "Extract KPIs"}
                      </button>
                    )}
                    {demoPhase === "review_kpis" && (
                      <button
                        onClick={handleApproveKpiReview}
                        disabled={trackedKpiIds.size === 0}
                        className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-4 py-2 text-xs font-bold text-white shadow-sm transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        Continue to Integrations
                      </button>
                    )}
                    {(demoPhase === "integration_setup" || demoPhase === "connecting_sources") && (
                      <button
                        onClick={handleConnectSources}
                        disabled={evaluating || trackedKpiIds.size === 0}
                        className="inline-flex items-center gap-2 rounded-md bg-[#0084C7] px-4 py-2 text-xs font-bold text-white shadow-sm transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        <Database className={`h-3.5 w-3.5 ${evaluating ? "animate-pulse" : ""}`} />
                        {evaluating ? "Connecting..." : "Connect Sources"}
                      </button>
                    )}
                  </div>
                </div>

                {tab !== "integrations" && (
                  <>
                    <div className="mt-5 grid gap-3 md:grid-cols-4">
                      {CONNECTED_SOURCES.map((source) => {
                        const status = demoSourceSync[source.id] || "waiting";
                        const connected = status === "connected";
                        const syncing = status === "syncing";
                        const loadedCount = visibleActualCountsBySource[source.id] || 0;
                        const configuredCount = trackedKpis.filter((kpi) => integrationConfigs[kpi.kpi_id]?.sourceId === source.id).length;
                        return (
                          <div key={source.id} className={`rounded-lg border p-3 transition-all ${
                            connected ? "border-emerald-200 bg-emerald-50/70" :
                            syncing ? "border-blue-200 bg-blue-50/70 shadow-sm" :
                            "border-slate-200 bg-slate-50"
                          }`}>
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">{source.type}</p>
                                <p className="mt-1 text-sm font-bold text-slate-900">{source.label}</p>
                              </div>
                              <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold uppercase ${
                                connected ? "bg-emerald-100 text-emerald-700" :
                                syncing ? "bg-blue-100 text-blue-700" :
                                "bg-white text-slate-400"
                              }`}>
                                {connected ? "Connected" : syncing ? "Syncing" : "Waiting"}
                              </span>
                            </div>
                            <p className="mt-2 line-clamp-2 text-[11px] leading-snug text-slate-500">{source.description}</p>
                            <p className="mt-2 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                              {configuredCount} configs · {connected || syncing ? `${loadedCount.toLocaleString()} records loaded` : "No records loaded"}
                            </p>
                          </div>
                        );
                      })}
                    </div>

                    {visibleActuals.length > 0 && (
                      <div className="mt-4 rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-xs font-semibold text-blue-700">
                        {visibleActuals.length} actual records received for tracked KPI configs. Final evaluation is populating the dashboard.
                      </div>
                    )}
                  </>
                )}
              </div>
            )}

            {monitoringLive && tab !== "qa" && (
              <div className="animate-in fade-in duration-300">
                <PerformanceCockpit
                  kpis={trackedKpis}
                  actuals={visibleActuals}
                  breaches={visibleBreaches}
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
                  {demoPhase === "review_kpis" ? "KPI Review" : "KPI Registry"}
                </button>
                {kpis.length > 0 && (
                  <button onClick={() => setTab("integrations")} className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${tab === "integrations" ? "bg-[#0084C7] text-white shadow-md shadow-blue-500/10" : "text-gray-500 hover:text-gray-800"}`}>
                    Integrations
                  </button>
                )}
                <button onClick={() => setTab("flags")} className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${tab === "flags" ? "bg-[#0084C7] text-white shadow-md shadow-blue-500/10" : "text-gray-500 hover:text-gray-800"}`}>
                  Compliance Flags
                </button>
                <button onClick={() => setTab("actuals")} className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${tab === "actuals" ? "bg-[#0084C7] text-white shadow-md shadow-blue-500/10" : "text-gray-500 hover:text-gray-800"}`}>
                  Performance Logs
                </button>
                {showQaLibrary && (
                  <button onClick={() => setTab("qa")} className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${tab === "qa" ? "bg-[#0084C7] text-white shadow-md shadow-blue-500/10" : "text-gray-500 hover:text-gray-800"}`}>
                    Q&A Library
                  </button>
                )}
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
                    actualsConnected={monitoringLive && visibleActuals.length > 0}
                    onReferContract={handleOpenKpiReference}
                    approvedKpiIds={approvedKpiIds}
                    trackedKpiIds={activeTrackingIds}
                    removedKpiIds={removedKpiIds}
                    onApproveKpi={handleApproveKpiCandidate}
                    onApproveAllKpis={handleApproveAllKpiCandidates}
                    onAmendKpi={handleAmendKpi}
                    onToggleKpiTracking={handleToggleKpiTracking}
                    onTrackRecommendedKpis={handleTrackRecommendedKpis}
                    onRemoveKpi={handleRemovePendingKpi}
                    onRestoreKpi={handleRestorePendingKpi}
                    reviewMode={demoPhase === "review_kpis"}
                    integrationConfigs={integrationConfigs}
                    sourceLabels={Object.fromEntries(CONNECTED_SOURCES.map((source) => [source.id, source.label]))}
                  />
                </div>
              )}

              {tab === "integrations" && (
                <div className="animate-in fade-in duration-300">
                  <IntegrationConfigurator
                    kpis={kpis}
                    trackedKpiIds={activeTrackingIds}
                    configs={integrationConfigs}
                    sources={CONNECTED_SOURCES}
                    sourceSync={demoSourceSync}
                    actualCountsBySource={visibleActualCountsBySource}
                    isConnecting={evaluating}
                    onUpdateConfig={handleUpdateIntegrationConfig}
                    onConnectSources={handleConnectSources}
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
                    handleRemoveFlag={handleRemoveFlag}
                  />
                </div>
              )}

              {tab === "actuals" && (
                <div className="animate-in fade-in duration-300">
                  <PerformanceActuals
                    actuals={actualEvidenceConnected ? actuals : []}
                    kpis={kpis}
                    integrationConfigs={integrationConfigs}
                    sourceLabels={Object.fromEntries(CONNECTED_SOURCES.map((source) => [source.id, source.label]))}
                    sourceSync={isDemoLifecycle ? demoSourceSync : undefined}
                  />
                </div>
              )}

              {showQaLibrary && tab === "qa" && (
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

        {/* Agent Inspector Bottom Drawer */}
        <AgentInspector
          planSteps={planSteps}
          thoughts={thoughtsList}
          toolCalls={workbenchToolCalls}
          facts={facts}
          safetyStatus={safetyStatus}
          actuals={visibleActuals}
        />
      </div>
    </div>
    </ErrorBoundary>
  );
}
