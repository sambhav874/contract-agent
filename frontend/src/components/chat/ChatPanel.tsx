"use client";

import { useState, useRef, useEffect } from "react";
import { Send, X, Bot } from "lucide-react";
import { chatWithContractStream } from "@/lib/api";
import { ChatMessage } from "./ChatMessage";

interface Delegation {
  key?: string;
  agent?: string;
  intent?: string;
  task?: string;
  status?: string;
  step_id?: string;
  reason?: string;
  thinking?: string;
  error?: string;
}

interface ToolCall {
  name: string;
  args: Record<string, unknown>;
  status: "running" | "done";
}

interface StreamEvent extends Delegation {
  type?: string;
  content?: string;
  name?: string;
  args?: Record<string, unknown>;
  source?: string;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  thought?: string;
  geminiThought?: string;
  plan?: string;
  delegations?: Delegation[];
  toolCalls?: ToolCall[];
  toolResults?: unknown[];
  artifact?: { type: string; content: string } | null;
  isStreaming?: boolean;
}

interface ChatPanelProps {
  contractId: string;
  onClose: () => void;
}

export function ChatPanel({ contractId, onClose }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  async function sendMessage() {
    const submittedInput = input.trim();
    if (!submittedInput || isLoading) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: submittedInput,
    };

    const assistantId = (Date.now() + 1).toString();
    const assistantMsg: Message = {
      id: assistantId,
      role: "assistant",
      content: "",
      thought: "",
      geminiThought: "",
      plan: "",
      delegations: [],
      toolCalls: [],
      toolResults: [],
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setInput("");
    setIsLoading(true);

    const sid = sessionId ?? `${contractId}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
    if (!sessionId) setSessionId(sid);

    try {
      const response = await chatWithContractStream(contractId, userMsg.content, undefined, sid);
      const reader = response.body?.getReader();
      if (!reader) return;

      let content = "";
      let thought = "";
      let geminiThought = "";
      let plan = "";
      const toolCalls: ToolCall[] = [];
      const delegations: Delegation[] = [];
      const decoder = new TextDecoder();
      let buffer = "";

      const upsertDelegation = (event: StreamEvent) => {
        const key = `${event.step_id || "main"}:${event.agent || "agent"}:${event.intent || "intent"}`;
        const existingIndex = delegations.findIndex((item) => item.key === key);
        const next = { ...(existingIndex >= 0 ? delegations[existingIndex] : {}), ...event, key };
        if (existingIndex >= 0) delegations[existingIndex] = next;
        else delegations.push(next);
      };

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
            const data = JSON.parse(trimmed.replace("data: ", "")) as StreamEvent;
            if (data.type === "thought") {
              if (data.source === "gemini_thinking") geminiThought += data.content || "";
              else thought += data.content || "";
            }
            else if (data.type === "plan") plan += data.content || "";
            else if (data.type === "content") content += data.content || "";
            else if (data.type === "delegation") upsertDelegation(data);
            else if (data.type === "tool_call")
              toolCalls.push({ name: data.name || "unknown_tool", args: data.args || {}, status: "running" });
            else if (data.type === "tool_result") {
              const tc = toolCalls.findLast((t) => t.name === data.name && t.status === "running");
              if (tc) tc.status = "done";
            }

            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content, thought, geminiThought, plan, delegations: [...delegations], toolCalls: [...toolCalls] }
                  : m
              )
            );
          } catch (e) {
            // skip malformed lines
          }
        }
      }

      // Parse artifacts
      let artifact = null;
      const fencedRegex = /```(?:html|svg|xml)\s*([\s\S]*?)```/i;
      const fencedMatch = fencedRegex.exec(content);
      if (fencedMatch) {
        const type = fencedMatch[1].includes("<svg") ? "svg" : "html";
        artifact = { type, content: fencedMatch[1].trim() };
        content = content.replace(fencedMatch[0], "").trim();
      }

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, content, artifact, isStreaming: false } : m
        )
      );
    } catch (e) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, content: "Error: " + String(e), isStreaming: false } : m
        )
      );
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-full bg-white border-l shadow-lg">
      <div className="flex items-center justify-between p-4 border-b">
        <div className="flex items-center gap-2">
          <Bot className="w-5 h-5 text-blue-600" />
          <h3 className="font-semibold text-gray-900">Contract Guardian AI</h3>
        </div>
        <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
          <X className="w-5 h-5" />
        </button>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 mt-8">
            <Bot className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p className="text-sm">Ask me about the contract</p>
          </div>
        )}
        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}
      </div>

      <div className="p-4 border-t">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
            placeholder="Ask a question..."
            className="flex-1 px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
            disabled={isLoading}
          />
          <button
            onClick={sendMessage}
            disabled={isLoading}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
