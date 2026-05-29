"use client";

import { useEffect, useState } from "react";
import { Bot, User, Loader2, Sparkles, CheckCircle2, Database, RefreshCw, Maximize2, ChevronDown, ChevronRight } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { ToolCallLog } from "./ToolCallLog";
import { ArtifactViewer } from "./ArtifactViewer";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  thought?: string;
  geminiThought?: string;
  plan?: string;
  delegations?: Delegation[];
  isStreaming?: boolean;
  artifact?: { type: string; content: string } | null;
  toolCalls?: any[];
  citations?: any[];
}

interface Delegation {
  key?: string;
  agent?: string;
  intent?: string;
  task?: string;
  status?: "queued" | "started" | "running" | "completed" | "failed" | string;
  step_id?: string;
  reason?: string;
  thinking?: string;
  error?: string;
}

function parseThoughtBlocks(thought: string) {
  const regex = /\*\*(.*?)\*\*([\s\S]*?)(?=(?:\*\*(?:.*?)\*\*|$))/g;
  const sections: { heading: string; text: string }[] = [];
  let match;
  while ((match = regex.exec(thought)) !== null) {
    const heading = match[1].trim();
    const text = match[2].trim();
    if (heading || text) {
      sections.push({ heading, text });
    }
  }
  return sections;
}

function ThoughtSection({ heading, text }: { heading: string; text: string }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="border border-slate-100 rounded-lg overflow-hidden bg-white shadow-sm mb-1.5 last:mb-0">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-3 py-2 text-left bg-slate-50/60 hover:bg-slate-100/80 transition-colors"
      >
        <span className="font-semibold text-slate-700 text-[11px] flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-400 shrink-0" />
          {heading}
        </span>
        {isOpen ? (
          <ChevronDown className="h-3.5 w-3.5 text-slate-400 shrink-0" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-slate-400 shrink-0" />
        )}
      </button>
      {isOpen && (
        <div className="px-3 py-2.5 bg-white border-t border-slate-50 text-[11px] text-slate-600 leading-relaxed">
          <MarkdownText text={text} />
        </div>
      )}
    </div>
  );
}

function MarkdownText({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeRaw]}
      components={{
        p: ({ node, ...props }) => <p className="mb-2 last:mb-0" {...props} />,
        strong: ({ node, ...props }) => <strong className="font-semibold text-slate-900" {...props} />,
        em: ({ node, ...props }) => <em className="text-slate-500" {...props} />,
        ul: ({ node, ...props }) => <ul className="mb-2 list-disc space-y-1 pl-4" {...props} />,
        ol: ({ node, ...props }) => <ol className="mb-2 list-decimal space-y-1 pl-4" {...props} />,
        li: ({ node, ...props }) => <li className="pl-1" {...props} />,
        code: ({ node, ...props }) => (
          <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[10px] text-slate-700" {...props} />
        ),
      }}
    >
      {text}
    </ReactMarkdown>
  );
}

function ThinkingBlock({
  text,
  label = "Thinking",
  active = false,
  compact = false,
}: {
  text: string;
  label?: string;
  active?: boolean;
  compact?: boolean;
}) {
  return (
    <div className={`rounded-lg border border-violet-100 bg-white shadow-sm ${compact ? "p-2" : "p-3"}`}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-widest text-violet-600">
          {active ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
          {label}
        </span>
        {active && (
          <span className="rounded-full bg-violet-50 px-2 py-0.5 text-[9px] font-semibold text-violet-600">
            live
          </span>
        )}
      </div>
      <div className={`${compact ? "max-h-32" : "max-h-52"} overflow-y-auto pr-1 text-[11px] leading-relaxed text-slate-700`}>
        <MarkdownText text={text} />
      </div>
    </div>
  );
}

interface ChatMessageProps {
  message: Message;
  qaApprovalState?: any;
  setQaApprovalState?: (state: any) => void;
  handleApproveAndAnswer?: (categories: any[]) => void;
  handleSaveQAPair?: (category: string, question: string, answer: string, sources?: string[], justification?: string, exact_quotes?: string[], confidence?: number) => void;
  setActiveArtifact?: (artifact: any | null) => void;
}

function confidenceScore(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.max(0, Math.min(1, value));
  }
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    const parsed = Number(normalized);
    if (Number.isFinite(parsed)) return Math.max(0, Math.min(1, parsed));
    if (normalized === "high") return 0.9;
    if (normalized === "medium") return 0.7;
    if (normalized === "low") return 0.4;
  }
  return null;
}

function confidenceClasses(score: number | null): string {
  if (score === null) return "bg-slate-100 text-slate-700";
  if (score >= 0.85) return "bg-emerald-100 text-emerald-700";
  if (score >= 0.6) return "bg-amber-100 text-amber-700";
  return "bg-red-100 text-red-700";
}

function delegationStatusClasses(status?: string): string {
  if (status === "completed") return "bg-emerald-100 text-emerald-700 border-emerald-200";
  if (status === "failed") return "bg-red-100 text-red-700 border-red-200";
  return "bg-blue-100 text-blue-700 border-blue-200";
}

function delegationStatusLabel(status?: string): string {
  if (status === "completed") return "completed";
  if (status === "failed") return "failed";
  if (status === "queued") return "queued";
  if (status === "started" || status === "running") return "running";
  return status || "running";
}

function displayAgentName(item: Delegation): string {
  const task = `${item.task || ""} ${item.intent || ""}`.toLowerCase();
  if (task.includes("autonomous") || task.includes("mitigate") || task.includes("recommend") || task.includes("next action")) {
    return "ActionAgent";
  }
  if (task.includes("evidence") || task.includes("source")) return "EvidenceAgent";
  return item.agent || "Specialist Agent";
}

function reasoningSummary(displayThought: string, activeDelegation?: Delegation) {
  if (displayThought.trim()) return displayThought.trim();
  if (activeDelegation) {
    return `**Current Focus**\nI am using ${displayAgentName(activeDelegation)} to check: ${activeDelegation.task || "the next contract analysis step"}.`;
  }
  return "";
}

function inProgressThinking(item: Delegation): string {
  const status = item.status || "";
  if (!["queued", "started", "running"].includes(status)) return "";
  return `I am reviewing this work item now:\n\n**${item.task || "Analyze the next contract work item."}**\n\nI am checking the relevant contract clauses, KPI records, breach evidence, and remediation context before returning a conclusion.`;
}

export function ChatMessage({
  message,
  qaApprovalState,
  setQaApprovalState,
  handleApproveAndAnswer,
  handleSaveQAPair,
  setActiveArtifact,
}: ChatMessageProps) {
  const isUser = message.role === "user";
  const [showAuditTrail, setShowAuditTrail] = useState(Boolean(message.isStreaming));
  const rawContent = message.content || "";
  const [visibleContent, setVisibleContent] = useState(rawContent);
  const isTyping =
    !isUser &&
    rawContent.length > visibleContent.length &&
    rawContent.startsWith(visibleContent);

  useEffect(() => {
    if (isUser) {
      setVisibleContent(rawContent);
      return;
    }

    if (!rawContent) {
      setVisibleContent("");
      return;
    }

    if (!rawContent.startsWith(visibleContent)) {
      setVisibleContent(rawContent);
      return;
    }

    if (visibleContent.length >= rawContent.length) return;

    const remaining = rawContent.length - visibleContent.length;
    const step =
      remaining > 2400 ? 18 :
      remaining > 1000 ? 12 :
      remaining > 300 ? 7 :
      4;

    const timer = window.setTimeout(() => {
      setVisibleContent((current) => {
        if (!rawContent.startsWith(current)) return rawContent;
        return rawContent.slice(0, Math.min(rawContent.length, current.length + step));
      });
    }, 14);

    return () => window.clearTimeout(timer);
  }, [isUser, rawContent, visibleContent]);

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[90%] overflow-hidden break-words rounded-2xl p-4 text-xs leading-relaxed shadow-md bg-blue-600 text-white">
          {message.content}
        </div>
      </div>
    );
  }

  // Assistant Message parsing
  let displayContent = visibleContent;
  let displayThought = message.thought || "";
  const displayGeminiThought = message.geminiThought || "";
  const directThinking = displayGeminiThought.trim();
  let displayPlan = message.plan || "";
  const delegations = message.delegations || [];
  const completedDelegations = delegations.filter((item) => item.status === "completed").length;
  const allDelegationsCompleted = delegations.length > 0 && completedDelegations === delegations.length;
  const activeDelegation = delegations.find((item) =>
    ["queued", "started", "running"].includes(item.status || "")
  );
  const traceThought = reasoningSummary(displayThought, activeDelegation);

  // Extract ALL thoughts
  let thoughtMatch;
  while ((thoughtMatch = displayContent.match(/<thought>([\s\S]*?)(?:<\/thought>|$)/))) {
    displayThought += (displayThought ? "\n\n" : "") + thoughtMatch[1].trim();
    displayContent = displayContent.replace(
      /(?:```\w*\s*)?<thought>[\s\S]*?(?:<\/thought>|$)(?:\s*```)?/,
      ""
    );
  }

  // Extract ALL plans
  let planMatch;
  while ((planMatch = displayContent.match(/<plan>([\s\S]*?)(?:<\/plan>|$)/))) {
    displayPlan += (displayPlan ? "\n\n" : "") + planMatch[1].trim();
    displayContent = displayContent.replace(
      /(?:```\w*\s*)?<plan>[\s\S]*?(?:<\/plan>|$)(?:\s*```)?/,
      ""
    );
  }

  // Clean up stray markdown artifacts for reasoning
  displayContent = displayContent.replace(/```xml\s*/g, "").replace(/```\s*$/g, "").trim();
  const shouldShowTrace = showAuditTrail || Boolean(message.isStreaming);

  // Parse QA blocks EARLY (before ReactMarkdown renders them as code)
  let parsedQaBlock: any = null;
  {
    // Try fenced ```json ... ``` first
    const qaMatch = displayContent.match(/```json\s*([\s\S]*?)```/);
    if (qaMatch) {
      try {
        const parsed = JSON.parse(qaMatch[1].trim());
        if (parsed.type === "qa_approval" || parsed.type === "qa_answers") {
          parsedQaBlock = parsed;
          displayContent = displayContent.replace(/```json[\s\S]*?```/, "").trim();
        }
      } catch {}
    }
    // Fallback: bare JSON block
    if (!parsedQaBlock) {
      const bareMatch = displayContent.match(
        /(\{[\s\S]*"type"\s*:\s*"qa_(?:approval|answers)"[\s\S]*\})/
      );
      if (bareMatch) {
        try {
          const parsed = JSON.parse(bareMatch[1].trim());
          if (parsed.type === "qa_approval" || parsed.type === "qa_answers") {
            parsedQaBlock = parsed;
            displayContent = displayContent.replace(bareMatch[1], "").trim();
          }
        } catch {}
      }
    }
  }

  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[100%] overflow-hidden break-words rounded-2xl p-4 text-xs leading-relaxed shadow-md bg-white border border-gray-100 text-gray-700 prose prose-sm max-w-none prose-p:leading-relaxed prose-p:m-0 prose-ul:m-0 prose-li:m-0 prose-strong:text-gray-800 prose-ul:pl-4">
        {/* Contract Guardian reasoning trace */}
        {(directThinking || traceThought || displayPlan || delegations.length > 0 || (message.toolCalls && message.toolCalls.length > 0)) && (
          <div className="mb-3 overflow-hidden rounded-xl border border-blue-100 bg-blue-50/60 not-prose">
            <button
              type="button"
              onClick={() => setShowAuditTrail((current) => !current)}
              className="flex w-full items-center justify-between px-3 py-2 text-left"
            >
              <span className="flex min-w-0 items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-blue-700">
                {activeDelegation ? (
                  <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" />
                ) : allDelegationsCompleted ? (
                  <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                ) : (
                  <Database className="h-3.5 w-3.5 shrink-0" />
                )}
                Guardian Thinking
              </span>
              <span className="flex shrink-0 items-center gap-2 text-[10px] font-semibold text-blue-600">
                {delegations.length > 0 ? `${completedDelegations}/${delegations.length} agents` : `${message.toolCalls?.length || 0} ops`}
                {showAuditTrail ? (
                  <ChevronDown className="h-3.5 w-3.5" />
                ) : (
                  <ChevronRight className="h-3.5 w-3.5" />
                )}
              </span>
            </button>

            {shouldShowTrace && (
              <div className="space-y-4 border-t border-blue-100 p-4">
              {directThinking && (
              <div className="text-xs text-slate-700 leading-relaxed">
                <ThinkingBlock text={directThinking} active={Boolean(message.isStreaming)} />
              </div>
              )}

              {delegations.length > 0 && (
              <div className="text-xs text-slate-600 leading-relaxed">
                <div className="flex items-center gap-1.5 mb-2.5">
                  <Bot className="h-3.5 w-3.5 text-blue-500" />
                  <span className="font-bold uppercase tracking-widest text-blue-500 text-[10px]">
                    Specialist Agent Work
                  </span>
                </div>
                <div className="space-y-2">
                  {delegations.map((item, idx) => {
                    const liveThinking = inProgressThinking(item);
                    return (
                    <div key={item.key || `${item.agent}-${item.step_id}-${idx}`} className="rounded-lg border border-slate-100 bg-white p-3 shadow-sm">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-[11px] font-bold text-slate-800">
                            {displayAgentName(item)}
                          </p>
                          <p className="mt-0.5 text-[10px] text-slate-500">
                            {item.intent || "GENERAL_QUERY"}{item.step_id ? ` - Step ${item.step_id}` : ""}
                          </p>
                        </div>
                        <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase ${delegationStatusClasses(item.status)}`}>
                          {delegationStatusLabel(item.status)}
                        </span>
                      </div>
                      {item.task && (
                        <p className="mt-2 text-[11px] text-slate-600">{item.task}</p>
                      )}
                      {item.reason && (
                        <p className="mt-1 text-[10px] italic text-slate-400">{item.reason}</p>
                      )}
                      {item.thinking && (
                        <div className="mt-2">
                          <ThinkingBlock text={item.thinking} compact />
                        </div>
                      )}
                      {!item.thinking && liveThinking && (
                        <div className="mt-2">
                          <ThinkingBlock text={liveThinking} active compact />
                        </div>
                      )}
                      {item.error && (
                        <p className="mt-1 text-[10px] font-semibold text-red-600">{item.error}</p>
                      )}
                    </div>
                  );})}
                </div>
              </div>
              )}

              {traceThought && (
              <div className="text-xs text-slate-600 leading-relaxed">
                <div className="flex items-center gap-1.5 mb-2.5">
                  <Bot className="h-3.5 w-3.5 text-blue-500" />
                  <span className="font-bold uppercase tracking-widest text-blue-500 text-[10px]">
                    Work Notes
                  </span>
                </div>
                {(() => {
                  const sections = parseThoughtBlocks(traceThought);
                  if (sections.length > 0) {
                    return (
                      <div className="flex flex-col gap-1.5">
                        {sections.map((sec, idx) => (
                          <ThoughtSection key={idx} heading={sec.heading} text={sec.text} />
                        ))}
                      </div>
                    );
                  }
                  return (
                    <div className="rounded-lg border border-blue-100 bg-white px-3 py-2.5 text-[11px] shadow-sm">
                      <MarkdownText text={traceThought} />
                    </div>
                  );
                })()}
              </div>
              )}

              {displayPlan && (
              <div className="text-xs text-indigo-600">
                <div className="flex items-center gap-1.5 mb-2">
                  <span className="font-bold uppercase tracking-widest text-indigo-400 text-[10px]">
                    Execution Plan
                  </span>
                </div>
                {(() => {
                  const steps = displayPlan.match(/\d+[).]\s+[\s\S]*?(?=(?:\d+[).]\s+|$))/g);
                  if (steps && steps.length >= 1) {
                    return (
                      <div className="flex flex-col gap-2">
                        {steps.map((step: string, stepIndex: number) => {
                          const text = step.replace(/^\d+[).]\s+/, "").trim();
                          return (
                            <div
                              key={stepIndex}
                              className="flex items-start gap-2.5 px-3 py-2 rounded-lg bg-white/60 border border-indigo-50 shadow-sm"
                            >
                              <span className="font-bold text-[10px] bg-indigo-100 text-indigo-700 rounded-full w-4 h-4 flex items-center justify-center shrink-0 shadow-sm mt-[2px]">
                                {stepIndex + 1}
                              </span>
                              <span className="font-medium text-[11px] leading-snug">{text}</span>
                            </div>
                          );
                        })}
                      </div>
                    );
                  }
                  return <span className="italic whitespace-pre-wrap text-[11px]">{displayPlan}</span>;
                })()}
              </div>
              )}

              {message.toolCalls && message.toolCalls.length > 0 && (
              <div className="pt-2 border-t border-slate-200/60">
                <span className="font-bold uppercase tracking-widest text-slate-400 text-[10px] block mb-1.5">
                  Tool Operations
                </span>
                <ToolCallLog toolCalls={message.toolCalls} />
              </div>
              )}
              </div>
            )}
          </div>
        )}

        {/* Main Content */}
        {parsedQaBlock?.type === "qa_approval" ? (
          (() => {
            const cats =
              qaApprovalState?.msgId === message.id ? qaApprovalState.categories : parsedQaBlock.categories;
            return (
              <div className="space-y-3">
                {displayContent && <p className="text-xs text-gray-500 italic">{displayContent}</p>}
                <div className="rounded-xl border border-indigo-200 bg-indigo-50/60 overflow-hidden">
                  <div className="px-4 py-3 border-b border-indigo-100 flex items-center justify-between">
                    <span className="text-[11px] font-bold text-indigo-700 uppercase tracking-widest flex items-center gap-1.5">
                      <Sparkles className="h-3.5 w-3.5" /> Suggested Questions
                    </span>
                    <span className="text-[10px] text-indigo-500">Edit questions before approving</span>
                  </div>
                  <div className="divide-y divide-indigo-100">
                    {cats.map((cat: any, ci: number) => (
                      <div key={ci} className="p-4">
                        <p className="text-[11px] font-bold text-indigo-800 mb-2">{cat.name}</p>
                        <div className="space-y-2">
                          {cat.questions.map((q: string, qi: number) => (
                            <div key={qi} className="flex items-center gap-2">
                              <span className="text-[10px] font-bold text-indigo-400 shrink-0 w-4">
                                {qi + 1}.
                              </span>
                              <input
                                className="flex-1 text-[12px] text-gray-700 bg-white border border-indigo-100 rounded-lg px-3 py-1.5 focus:outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-200"
                                value={q}
                                onChange={(e) => {
                                  const updated = cats.map((c: any, cIdx: number) =>
                                    cIdx === ci
                                      ? {
                                          ...c,
                                          questions: c.questions.map((qq: string, qIdx: number) =>
                                            qIdx === qi ? e.target.value : qq
                                          ),
                                        }
                                      : c
                                  );
                                  setQaApprovalState?.({ msgId: message.id, categories: updated });
                                }}
                              />
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="px-4 py-3 bg-indigo-100/50 flex justify-end">
                    <button
                      onClick={() => handleApproveAndAnswer?.(cats)}
                      className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white text-[11px] font-bold hover:bg-indigo-700 transition-all shadow-sm active:scale-95"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" /> Approve & Get Answers
                    </button>
                  </div>
                </div>
              </div>
            );
          })()
        ) : parsedQaBlock?.type === "qa_answers" ? (
          <div className="space-y-3">
            {displayContent && <p className="text-xs text-gray-500 italic">{displayContent}</p>}
            <div className="rounded-xl border border-emerald-200 bg-emerald-50/40 overflow-hidden">
              <div className="px-4 py-3 border-b border-emerald-100 flex items-center justify-between">
                <span className="text-[11px] font-bold text-emerald-700 uppercase tracking-widest flex items-center gap-1.5">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Contract Answers
                </span>
                <div className="flex items-center gap-2">
                  {(() => {
                    const uniqueSources = new Set<string>();
                    parsedQaBlock.answers?.forEach((ans: any) => {
                      if (Array.isArray(ans.segment_ids)) {
                        ans.segment_ids.forEach((id: string) => {
                          if (id) uniqueSources.add(id);
                        });
                      }
                    });
                    return uniqueSources.size > 0 ? (
                      <span className="text-[9px] bg-emerald-100/80 border border-emerald-200/50 text-emerald-800 px-2 py-0.5 rounded-full font-bold shadow-sm flex items-center gap-1">
                        <Database className="h-2.5 w-2.5" />
                        {uniqueSources.size} {uniqueSources.size === 1 ? "source cited" : "sources cited"}
                      </span>
                    ) : null;
                  })()}
                  <span className="text-[10px] text-emerald-600 font-medium">
                    {parsedQaBlock.answers?.length} answers
                  </span>
                  <button
                    onClick={() => {
                      parsedQaBlock.answers?.forEach((item: any) => {
                        handleSaveQAPair?.(item.category || 'General', item.question, item.value || item.answer, item.segment_ids || [], item.justification || "", item.exact_quotes || [], confidenceScore(item.confidence) ?? undefined);
                      });
                    }}
                    className="shrink-0 flex items-center gap-1 px-2 py-1 rounded-lg bg-emerald-600 text-white text-[10px] font-bold hover:bg-emerald-700 transition-colors shadow-sm"
                  >
                    <Database className="h-3 w-3" /> Save All
                  </button>
                </div>
              </div>
              <div className="divide-y divide-emerald-100">
                {parsedQaBlock.answers?.map((item: any, ai: number) => (
                  <div key={ai} className="p-4 space-y-2">
                    {(() => {
                      const score = confidenceScore(item.confidence);
                      const confidenceLabel = score !== null ? `${Math.round(score * 100)}% confidence` : `${item.confidence} confidence`;
                      return (
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1">
                        <div className="flex items-center gap-1.5 flex-wrap mb-1">
                          {item.confidence && (
                            <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase ${confidenceClasses(score)}`}>
                              {confidenceLabel}
                            </span>
                          )}
                          {item.segment_ids && item.segment_ids.length > 0 && (
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-100 text-[9px] font-bold shadow-sm">
                              <Database className="h-2.5 w-2.5" />
                              {item.segment_ids.length} {item.segment_ids.length === 1 ? "source" : "sources"}
                            </span>
                          )}
                        </div>
                        <p className="text-[12px] font-bold text-gray-800">{item.question}</p>
                      </div>
                      <button
                        onClick={() => handleSaveQAPair?.(item.category || 'General', item.question, item.value || item.answer, item.segment_ids || [], item.justification || "", item.exact_quotes || [], score ?? undefined)}
                        className="shrink-0 flex items-center gap-1 px-2 py-1 rounded-lg border border-emerald-200 bg-white text-emerald-700 text-[10px] font-bold hover:bg-emerald-50 transition-colors"
                        title="Save to library"
                      >
                        <Database className="h-3 w-3" /> Save
                      </button>
                    </div>
                      );
                    })()}
                    <div className="text-[12px] text-gray-600 leading-relaxed border-l-2 border-emerald-300 pl-3 space-y-2">
                      <p>{item.value || item.answer}</p>

                      {item.justification && (
                        <div className="bg-emerald-50/50 p-2 rounded text-[11px] text-emerald-800 border border-emerald-100/50">
                          <span className="font-semibold block mb-1">Justification:</span>
                          {item.justification}
                        </div>
                      )}

                      {item.segment_ids && item.segment_ids.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          <span className="text-[10px] font-medium text-emerald-700 flex items-center mr-1">Sources:</span>
                          {item.segment_ids.map((id: string, idx: number) => (
                            <span key={idx} className="inline-block px-1.5 py-0.5 bg-white border border-emerald-200 rounded text-[9px] text-emerald-600 font-mono break-all">
                              {id}
                            </span>
                          ))}
                        </div>
                      )}

                      {item.exact_quotes && item.exact_quotes.length > 0 && (
                        <div className="mt-2 space-y-1.5">
                          <span className="text-[10px] font-semibold text-emerald-700 block">Exact Citations:</span>
                          {item.exact_quotes.map((quote: string, qidx: number) => (
                            <p key={qidx} className="text-[11px] bg-white border border-emerald-150 p-2 rounded italic text-gray-700 pl-2.5 border-l-2 border-l-emerald-500 shadow-sm leading-relaxed">
                              &quot;{quote}&quot;
                            </p>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : displayContent ? (
          <div className="text-gray-800 leading-relaxed text-[13px]">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeRaw]}
              components={{
                table: ({ node, ...props }) => (
                  <div className="overflow-x-auto my-5 border border-slate-200 rounded-xl shadow-sm bg-white [&::-webkit-scrollbar]:h-2 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-slate-300 [&::-webkit-scrollbar-thumb]:rounded-full">
                    <table className="w-full text-left border-collapse min-w-[600px]" {...props} />
                  </div>
                ),
                thead: ({ node, ...props }) => (
                  <thead className="bg-slate-50 border-b border-slate-200" {...props} />
                ),
                th: ({ node, ...props }) => (
                  <th
                    className="px-4 py-3 text-[11px] font-bold text-slate-500 uppercase tracking-wider whitespace-nowrap"
                    {...props}
                  />
                ),
                td: ({ node, ...props }) => (
                  <td className="px-4 py-3 text-[12px] text-slate-700 border-b border-slate-100" {...props} />
                ),
                tr: ({ node, ...props }) => (
                  <tr className="hover:bg-slate-50/50 transition-colors" {...props} />
                ),
                p: ({ node, ...props }) => <p className="mb-2 last:mb-0" {...props} />,
                ul: ({ node, ...props }) => <ul className="list-disc pl-4 space-y-1 mb-2" {...props} />,
                ol: ({ node, ...props }) => <ol className="list-decimal pl-4 space-y-1 mb-2" {...props} />,
              }}
            >
              {displayContent}
            </ReactMarkdown>
            {isTyping && (
              <span className="ml-0.5 inline-block h-4 translate-y-0.5 animate-pulse border-r-2 border-blue-500" />
            )}
          </div>
        ) : null}

        {message.citations && message.citations.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-100">
            <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-2 flex items-center gap-1">
              <Bot className="h-3 w-3" /> Verified Source
            </p>
            {message.citations.slice(0, 1).map((c: any, ci: number) => (
              <div
                key={ci}
                className="p-2 rounded bg-gray-50 text-[10px] text-gray-500 italic border-l-2 border-blue-400"
              >
                {c.text.substring(0, 150)}...
              </div>
            ))}
          </div>
        )}

        {message.artifact && (
          <div className="mt-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Generated Artifact
              </span>
              <button
                onClick={() => setActiveArtifact?.(message.artifact)}
                className="flex items-center gap-1 text-[10px] text-blue-600 font-bold hover:text-blue-800 transition-colors"
              >
                <Maximize2 className="h-3 w-3" /> Full View
              </button>
            </div>
            <ArtifactViewer artifact={message.artifact as any} />
          </div>
        )}

        {message.isStreaming && !visibleContent && (
          <div className="flex items-center gap-2 text-slate-400 py-1">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            <span className="text-[11px] italic">Guardian is writing...</span>
          </div>
        )}
      </div>
    </div>
  );
}
