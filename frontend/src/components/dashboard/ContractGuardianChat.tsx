"use client";

import React, { useState, useMemo, useEffect, useRef } from "react";
import {
  Bot,
  RefreshCw,
  X,
  Send,
  Database,
  Brain,
  Terminal,
  Activity,
  Shield,
  Sparkles
} from "lucide-react";

// Import modular components
import { ChatMessage } from "../chat/ChatMessage";

interface ContractGuardianChatProps {
  chatOpen: boolean;
  setChatOpen: (isOpen: boolean) => void;
  chatMessages: any[];
  chatLoading: boolean;
  currentQuery: string;
  setCurrentQuery: (q: string) => void;
  qaApprovalState: any;
  setQaApprovalState: (state: any) => void;
  handleChat: (question: string, breachId?: string) => void;
  handleResetChat: () => void;
  handleSaveQAPair: (category: string, question: string, answer: string, sources?: string[], justification?: string, exact_quotes?: string[], confidence?: number) => void;
  handleApproveAndAnswer: (categories: any[]) => void;
  setActiveArtifact: (artifact: any) => void;
  workflowStatus?: { active: boolean; label: string } | null;
}

export default function ContractGuardianChat({
  chatOpen,
  setChatOpen,
  chatMessages,
  chatLoading,
  currentQuery,
  setCurrentQuery,
  qaApprovalState,
  setQaApprovalState,
  handleChat,
  handleResetChat,
  handleSaveQAPair,
  handleApproveAndAnswer,
  setActiveArtifact,
  workflowStatus,
}: ContractGuardianChatProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  // Auto scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatMessages, chatLoading, workflowStatus]);

  const handleExportChat = () => {
    const chatText = chatMessages
      .map(
        (m) =>
          `[${m.role.toUpperCase()}]\n${
            m.content || (m.plan ? "Plan: " + m.plan : "")
          }`
      )
      .join("\n\n");
    const blob = new Blob([chatText], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `chat-export-${new Date().toISOString()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Extract operations info from last assistant message
  const lastAssistantMessage = useMemo(() => {
    return chatMessages.findLast((m) => m.role === "assistant");
  }, [chatMessages]);

  const statusBarText = useMemo(() => {
    if (workflowStatus?.active) {
      return workflowStatus.label;
    }
    if (chatLoading) {
      if (lastAssistantMessage?.delegations && lastAssistantMessage.delegations.length > 0) {
        const activeDelegation = lastAssistantMessage.delegations.find((item: { status?: string; agent?: string }) =>
          ["queued", "started", "running"].includes(item.status || "")
        );
        if (activeDelegation) {
          return `Delegated to ${activeDelegation.agent}...`;
        }
        return `${lastAssistantMessage.delegations.length} agent handoff${lastAssistantMessage.delegations.length === 1 ? "" : "s"} complete`;
      }
      if (lastAssistantMessage?.thought) {
        return "Thinking & reasoning...";
      }
      if (lastAssistantMessage?.toolCalls && lastAssistantMessage.toolCalls.length > 0) {
        const activeTool = lastAssistantMessage.toolCalls.find((tc: any) => tc.status === "running");
        if (activeTool) {
          return `Executing ${activeTool.name}...`;
        }
        return `Operations active (${lastAssistantMessage.toolCalls.length} tools called)`;
      }
      return "Thinking & reasoning...";
    }
    return "Agent Ready";
  }, [chatLoading, lastAssistantMessage, workflowStatus]);

  const hasActiveStatus = chatLoading || Boolean(workflowStatus?.active);

  return (
    <>
      {/* Floating Chat Button */}
      {!chatOpen && (
        <button
          onClick={() => setChatOpen(true)}
          className="fixed bottom-6 right-6 h-14 w-14 rounded-full bg-blue-600 text-white shadow-2xl flex items-center justify-center hover:scale-110 transition-all active:scale-95 z-40 group animate-in"
        >
          <Bot className="h-7 w-7" />
          <span className="absolute right-16 bg-white border border-gray-100 text-blue-600 text-xs font-bold px-3 py-1.5 rounded-lg shadow-xl opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
            Contract Guardian
          </span>
        </button>
      )}

      {/* Chat Sidebar */}
      <div
        className={`fixed top-0 right-0 h-full w-full max-w-[520px] bg-white/95 backdrop-blur-xl border-l border-gray-200 shadow-[-10px_0_30px_rgba(0,0,0,0.05)] z-50 transition-transform duration-500 ease-in-out ${
          chatOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex flex-col h-full">
          {/* Chat Header */}
          <div className="p-4 border-b border-gray-100 flex items-center justify-between bg-blue-600/5">
            <div className="flex items-center gap-2.5">
              <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-lg">
                <Bot className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-gray-800">Contract Guardian</h3>
                <p className="text-[10px] text-blue-600 font-semibold tracking-tight uppercase">
                  RAG-Powered Audit Intelligence
                </p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              {chatMessages.length > 0 && (
                <>
                  <button
                    onClick={handleExportChat}
                    title="Export chat"
                    className="px-2 py-1 text-[10px] font-semibold text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors uppercase tracking-wide flex items-center gap-1"
                  >
                    <Database className="h-3 w-3" /> Export
                  </button>
                  <button
                    onClick={handleResetChat}
                    title="New conversation"
                    className="px-2 py-1 text-[10px] font-semibold text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors uppercase tracking-wide flex items-center gap-1"
                  >
                    <RefreshCw className="h-3 w-3" /> New
                  </button>
                </>
              )}
              <button
                onClick={() => setChatOpen(false)}
                className="p-1.5 hover:bg-gray-100 rounded-full transition-colors text-gray-400"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>

          {/* Slim Live Streaming Status Bar */}
          <div className="h-7 px-4 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              {hasActiveStatus ? (
                <>
                  <span className="h-1.5 w-1.5 bg-blue-600 rounded-full animate-ping shrink-0" />
                  <span className="text-[10px] text-blue-700 font-semibold uppercase tracking-wider">
                    {statusBarText}
                  </span>
                </>
              ) : (
                <>
                  <span className="h-1.5 w-1.5 bg-emerald-500 rounded-full shrink-0" />
                  <span className="text-[10px] text-emerald-700 font-semibold uppercase tracking-wider">
                    {statusBarText}
                  </span>
                </>
              )}
            </div>

            <div className="flex items-center gap-2 text-[9px] font-bold text-gray-400">
              <span className="flex items-center gap-0.5">
                <Brain className="h-2.5 w-2.5" /> Thinking Config Enabled
              </span>
            </div>
          </div>

          {/* Scrollable Content Body */}
          <div
            ref={messagesContainerRef}
            className="flex-1 overflow-y-auto p-4 space-y-4"
          >
            {chatMessages.length === 0 && (
              <div className="flex flex-col items-center justify-center py-12 text-center px-6">
                <div className="h-16 w-16 rounded-3xl bg-blue-50 flex items-center justify-center mb-4">
                  <Bot className="h-8 w-8 text-blue-500" />
                </div>
                <h4 className="text-sm font-bold text-gray-800 mb-1">How can I help?</h4>
                <p className="text-xs text-gray-500 leading-relaxed mb-6">
                  Ask me about penalty clauses, audit frequencies, or specific breaches. I search your contract in real-time.
                </p>
                <div className="w-full space-y-2">
                  {[
                    "What is the penalty for Late Deliveries?",
                    "Are there any Force Majeure clauses?",
                    "How often should we run audits?",
                  ].map((q) => (
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
              <ChatMessage
                key={i}
                message={msg}
                qaApprovalState={qaApprovalState}
                setQaApprovalState={setQaApprovalState}
                handleApproveAndAnswer={handleApproveAndAnswer}
                handleSaveQAPair={handleSaveQAPair}
                setActiveArtifact={setActiveArtifact}
              />
            ))}

            <div ref={messagesEndRef} />
          </div>

          {/* Footer Input Bar */}
          <div className="p-4 border-t border-gray-100 bg-gray-50">
            <div className="relative">
              <input
                type="text"
                value={currentQuery}
                onChange={(e) => setCurrentQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleChat(currentQuery);
                  }
                }}
                placeholder="Ask your question..."
                disabled={chatLoading}
                className="w-full pl-4 pr-12 py-3 rounded-xl border border-gray-200 bg-white text-xs focus:ring-2 focus:ring-blue-100 focus:border-blue-400 transition-all outline-none"
              />
              <button
                onClick={() => handleChat(currentQuery)}
                disabled={chatLoading || !currentQuery.trim()}
                className="absolute right-2 top-2 p-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors shadow-lg active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
            <p className="text-[9px] text-gray-400 text-center mt-2 font-medium">
              Answers are grounded in retrieved contract sources
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
