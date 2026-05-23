import { AlertCircle, AlertTriangle, CheckCircle2 } from "lucide-react";

export const SEV_CONFIG: Record<string, any> = {
  CRITICAL: {
    dot: "bg-red-500",
    badge: "bg-red-100 text-red-700 border-red-200",
    color: "text-red-700",
    bg: "bg-red-50",
    border: "border-red-200",
    icon: AlertCircle,
    response: "< 1 hour",
  },
  HIGH: {
    dot: "bg-orange-400",
    badge: "bg-orange-100 text-orange-700 border-orange-200",
    color: "text-orange-700",
    bg: "bg-orange-50",
    border: "border-orange-200",
    icon: AlertTriangle,
    response: "Same business day",
  },
  MEDIUM: {
    dot: "bg-amber-300",
    badge: "bg-amber-100 text-amber-700 border-amber-200",
    color: "text-amber-700",
    bg: "bg-amber-50",
    border: "border-amber-200",
    icon: AlertTriangle,
    response: "Within 48 hours",
  },
  LOW: {
    dot: "bg-green-400",
    badge: "bg-green-100 text-green-700 border-green-200",
    color: "text-green-700",
    bg: "bg-green-50",
    border: "border-green-200",
    icon: CheckCircle2,
    response: "Next review cycle",
  },
};

export const STATUS_CONFIG: Record<string, any> = {
  Open: { color: "text-red-700", bg: "bg-red-50", border: "border-red-200", dot: "bg-red-500" },
  "In Progress": { color: "text-amber-700", bg: "bg-amber-50", border: "border-amber-200", dot: "bg-amber-400" },
  Resolved: { color: "text-green-700", bg: "bg-green-50", border: "border-green-200", dot: "bg-green-500" },
  Waived: { color: "text-gray-600", bg: "bg-gray-50", border: "border-gray-200", dot: "bg-gray-400" },
};

export function classifySeverity(breach: any): string {
  if (!breach.is_breach) return "LOW";
  const ratio = breach.actual_value / (breach.threshold_value || 1);
  if (breach.penalty_amount > 5000 || ratio > 2) return "CRITICAL";
  if (breach.penalty_amount > 1000 || ratio > 1.5) return "HIGH";
  return "MEDIUM";
}

export const KPI_TYPE_COLORS: Record<string, string> = {
  financial: "bg-emerald-50 text-emerald-700 border-emerald-200",
  sla: "bg-blue-50 text-blue-700 border-blue-200",
  penalty: "bg-red-50 text-red-700 border-red-200",
  volume: "bg-purple-50 text-purple-700 border-purple-200",
  timeline: "bg-amber-50 text-amber-700 border-amber-200",
  other: "bg-gray-50 text-gray-600 border-gray-200",
};

export const TYPE_COLORS: Record<string, string> = {
  financial: "#10b981",
  sla: "#3b82f6",
  penalty: "#ef4444",
  volume: "#8b5cf6",
  timeline: "#f59e0b",
  other: "#94a3b8",
};

export const PARTY_COLORS = ["#0084C7", "#8b5cf6", "#f59e0b", "#10b981", "#ef4444", "#6366f1"];

export const STATUS_BAR_COLORS: Record<string, string> = {
  Open: "#ef4444",
  "In Progress": "#f59e0b",
  Resolved: "#22c55e",
  Waived: "#94a3b8",
};
