"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
import { MessageSquare, Sparkles, Bot, X, Database } from "lucide-react";
import ContractViewer from "./ContractViewer";
import { fetchContractText } from "@/lib/api";

interface QuestionLibraryProps {
  savedQA: any[];
  handleDeleteQAPair: (qaId: string) => void;
  handleChat: (query: string, breachId?: string) => void;
  setChatOpen: (isOpen: boolean) => void;
  contractId: string;
}

function confidenceScore(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.max(0, Math.min(1, value));
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return Math.max(0, Math.min(1, parsed));
    }
  }
  return null;
}

function confidenceClasses(score: number | null): string {
  if (score === null) return "text-slate-500";
  if (score >= 0.85) return "text-emerald-700";
  if (score >= 0.6) return "text-amber-700";
  return "text-red-700";
}

export default function QuestionLibrary({
  savedQA,
  handleDeleteQAPair,
  handleChat,
  setChatOpen,
  contractId,
}: QuestionLibraryProps) {
  const [contractText, setContractText] = useState<string>("");
  const [isLoadingText, setIsLoadingText] = useState(false);
  const [selectedQAId, setSelectedQAId] = useState<string | null>(null);
  const [expandedSourcesId, setExpandedSourcesId] = useState<string | null>(null);
  const [activeSource, setActiveSource] = useState<string>("");
  const splitRef = useRef<HTMLDivElement>(null);
  const [splitHeight, setSplitHeight] = useState<number | null>(null);

  useEffect(() => {
    if (contractId) {
      setIsLoadingText(true);
      fetchContractText(contractId)
        .then((res) => {
          if (res.status === "success") {
            setContractText(res.text);
          }
        })
        .catch((e) => console.error("Failed to load contract text:", e))
        .finally(() => setIsLoadingText(false));
    }
  }, [contractId]);

  useEffect(() => {
    function updateSplitHeight() {
      if (!splitRef.current) return;
      const rect = splitRef.current.getBoundingClientRect();
      const bottomReserve = 80;
      const available = window.innerHeight - rect.top - bottomReserve;
      setSplitHeight(Math.max(360, available));
    }

    updateSplitHeight();
    window.addEventListener("resize", updateSplitHeight);
    return () => {
      window.removeEventListener("resize", updateSplitHeight);
    };
  }, [savedQA.length]);

  const selectedQA = savedQA.find((qa) => qa.qa_id === selectedQAId) || null;

  // Calculate unique sources across all saved QA items
  const totalUniqueSources = useMemo(() => {
    const allSources = new Set<string>();
    savedQA.forEach((qa) => {
      if (Array.isArray(qa.sources)) {
        qa.sources.forEach((s: string) => {
          if (s) allSources.add(s);
        });
      }
    });
    return allSources.size;
  }, [savedQA]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
            Saved Question-Answer Pairs
            {savedQA.length > 0 && (
              <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-blue-700">
                <Database className="h-3 w-3" />
                {totalUniqueSources} {totalUniqueSources === 1 ? "source" : "sources"}
              </span>
            )}
          </h2>
          <p className="text-xs text-gray-400 mt-0.5">Questions answered and saved from the chat agent</p>
        </div>
        <button
          onClick={() => handleChat("What should I ask about this contract?")}
          className="shrink-0 flex items-center gap-1.5 px-3 py-2 rounded-lg bg-blue-600 text-white text-xs font-bold hover:bg-blue-700 transition-all shadow-sm"
        >
          <Bot className="h-3.5 w-3.5" /> Generate Questions in Chat
        </button>
      </div>
      {savedQA.length > 0 ? (
        <div
          ref={splitRef}
          className="grid min-h-0 grid-cols-1 items-stretch gap-5 overflow-hidden lg:grid-cols-[minmax(0,3fr)_minmax(0,5fr)]"
          style={splitHeight ? { height: `${splitHeight}px` } : undefined}
        >
          <div className="grid grid-cols-1 content-start gap-2 overflow-y-auto pb-14 pr-1 lg:order-2 lg:h-full">
            {savedQA.map((qa: any, qi: number) => {
              const score = confidenceScore(qa.confidence);
              return (
                    <div
                      key={qa.qa_id || qi}
                      onClick={() => {
                        setSelectedQAId(qa.qa_id);
                        if (qa.sources?.length > 0) {
                          setExpandedSourcesId(qa.qa_id);
                          setActiveSource(qa.sources[0]);
                        }
                      }}
                      className={`rounded-lg border px-3 py-3 transition-all cursor-pointer ${
                        selectedQAId === qa.qa_id
                          ? "bg-white border-indigo-300 shadow-sm ring-1 ring-indigo-100"
                          : "bg-white border-gray-200 hover:border-indigo-200"
                      }`}
                    >
                      <div className="flex justify-between items-start gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="mb-1 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wide">
                            <span className="text-indigo-600">
                            {qa.category}
                          </span>
                          {score !== null && (
                              <span className={confidenceClasses(score)}>
                              {Math.round(score * 100)}%
                            </span>
                          )}
                          </div>
                          <p className="line-clamp-2 text-xs font-bold leading-snug text-gray-800 flex items-start gap-1.5">
                            <MessageSquare className={`h-3.5 w-3.5 shrink-0 mt-0.5 ${selectedQAId === qa.qa_id ? 'text-indigo-600' : 'text-indigo-300'}`} />
                            {qa.question}
                          </p>
                          {selectedQAId === qa.qa_id && (
                            <p className="mt-2 text-[11px] leading-relaxed text-gray-500">
                              {qa.answer}
                            </p>
                          )}
                          {selectedQAId === qa.qa_id && qa.justification && (
                            <p className="mt-2 border-l-2 border-slate-200 pl-2 text-[11px] leading-relaxed text-slate-500">
                              <span className="font-semibold text-slate-700">Evidence: </span>
                              {qa.justification}
                            </p>
                          )}
                          {qa.sources && qa.sources.length > 0 && (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedQAId(qa.qa_id);
                                setExpandedSourcesId((current) => current === qa.qa_id ? null : qa.qa_id);
                                setActiveSource(qa.sources[0] || "");
                              }}
                              className={`mt-2 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-bold ring-1 transition-colors ${
                                expandedSourcesId === qa.qa_id
                                  ? "bg-blue-600 text-white ring-blue-600"
                                  : "bg-blue-50 text-blue-700 ring-blue-100 hover:bg-blue-100"
                              }`}
                              aria-expanded={expandedSourcesId === qa.qa_id}
                              aria-label={`${qa.sources.length} sources. Toggle source citations.`}
                            >
                              <Database className="h-3 w-3" />
                              {qa.sources.length} {qa.sources.length === 1 ? "Source" : "Sources"}
                            </button>
                          )}
                          {expandedSourcesId === qa.qa_id && qa.sources?.length > 0 && (
                            <div className="mt-2 rounded-lg border border-blue-100 bg-blue-50/40 p-2">
                              <p className="mb-1.5 text-[9px] font-bold uppercase tracking-widest text-blue-500">
                                Source citations
                              </p>
                              <div className="flex flex-wrap gap-1.5">
                              {qa.sources.map((source: string, idx: number) => (
                                <button
                                  type="button"
                                  key={`${source}-${idx}`}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setSelectedQAId(qa.qa_id);
                                    setActiveSource(source);
                                  }}
                                  className={`inline-flex max-w-full items-start gap-1 rounded-md px-2 py-1 text-left text-[10px] font-medium ring-1 transition-colors ${
                                    activeSource === source
                                      ? "bg-cyan-100 text-cyan-800 ring-cyan-300"
                                      : "bg-white text-blue-700 ring-blue-100 hover:bg-blue-50"
                                  }`}
                                >
                                  <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-blue-50 text-[9px] font-bold">
                                    {idx + 1}
                                  </span>
                                  <span className="break-words text-left">
                                    {source}
                                  </span>
                                </button>
                              ))}
                              </div>
                            </div>
                          )}
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteQAPair(qa.qa_id);
                            if (selectedQAId === qa.qa_id) setSelectedQAId(null);
                          }}
                          className="shrink-0 text-gray-300 hover:text-red-500 transition-colors p-1 rounded"
                          title="Remove"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                      {qa.created_at && (
                        <p className="mt-2 text-[10px] text-gray-400">
                          Saved{" "}
                          {new Date(qa.created_at).toLocaleDateString(undefined, {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                          })}
                        </p>
                      )}
                    </div>
              );
            })}
          </div>
          <div className="min-h-0 lg:order-1 lg:h-full">
            <ContractViewer
              text={contractText}
              isLoading={isLoadingText}
              highlightTexts={[
                ...(selectedQA?.sources || []),
                ...(selectedQA?.exact_quotes || [])
              ]}
              highlightText={selectedQA ? (selectedQA.justification || selectedQA.answer) : undefined}
              activeHighlightText={activeSource}
            />
          </div>
        </div>
      ) : (
        <div className="text-center py-16 bg-white rounded-xl border border-gray-200">
          <div className="h-16 w-16 rounded-2xl bg-indigo-50 flex items-center justify-center mx-auto mb-4">
            <Sparkles className="h-8 w-8 text-indigo-400" />
          </div>
          <p className="text-sm font-semibold text-gray-700">No saved questions yet</p>
          <p className="text-xs text-gray-400 mt-1 max-w-xs mx-auto">
            Open the chat, ask the agent to generate questions, edit them, then approve to get contract-grounded
            answers. Save any answer to see it here.
          </p>
          <button
            onClick={() => {
              setChatOpen(true);
              handleChat("What should I ask about this contract?");
            }}
            className="mt-4 flex items-center gap-2 mx-auto px-4 py-2 rounded-lg bg-indigo-600 text-white text-xs font-bold hover:bg-indigo-700 transition-all shadow-sm"
          >
            <Bot className="h-3.5 w-3.5" /> Start in Chat
          </button>
        </div>
      )}
    </div>
  );
}
