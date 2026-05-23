"use client";

import { Check, HelpCircle } from "lucide-react";

interface CompletionSignalProps {
  signal: "done" | "clarify";
  onClarify?: () => void;
  question?: string;
}

export function CompletionSignal({ signal, onClarify, question }: CompletionSignalProps) {
  return (
    <div
      className={`flex items-center gap-3 p-3 rounded-lg ${
        signal === "done"
          ? "bg-green-50 border border-green-200"
          : "bg-amber-50 border border-amber-200"
      }`}
    >
      {signal === "done" ? (
        <>
          <Check className="w-5 h-5 text-green-600 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-green-800">Response complete</p>
            <p className="text-xs text-green-600">
              Agent has signalled completion. You can ask a follow-up.
            </p>
          </div>
        </>
      ) : (
        <>
          <HelpCircle className="w-5 h-5 text-amber-600 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-medium text-amber-800">Clarification needed</p>
            {question && <p className="text-xs text-amber-700 mt-0.5">{question}</p>}
            {onClarify && (
              <button
                onClick={onClarify}
                className="mt-2 text-sm text-amber-700 hover:text-amber-900 font-medium"
              >
                Provide clarification
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
