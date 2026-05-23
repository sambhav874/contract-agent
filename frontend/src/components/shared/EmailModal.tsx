"use client";

import React from "react";
import { MailWarning, X, RefreshCw, Mail } from "lucide-react";

interface EmailFormState {
  to: string;
  subject: string;
  body: string;
}

interface EmailModalProps {
  isOpen: boolean;
  onClose: () => void;
  isGeneratingEmail: boolean;
  isSendingEmail: boolean;
  emailForm: EmailFormState;
  setEmailForm: React.Dispatch<React.SetStateAction<EmailFormState>>;
  onSend: () => void;
}

export default function EmailModal({
  isOpen,
  onClose,
  isGeneratingEmail,
  isSendingEmail,
  emailForm,
  setEmailForm,
  onSend,
}: EmailModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 animate-in">
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={() => !isGeneratingEmail && !isSendingEmail && onClose()}
      />
      <div className="relative w-full max-w-2xl bg-white rounded-2xl shadow-xl overflow-hidden flex flex-col">
        <div className="p-4 border-b border-gray-100 flex items-center justify-between bg-amber-50/50">
          <div className="flex items-center gap-2 text-amber-700">
            <MailWarning className="h-5 w-5" />
            <h3 className="text-sm font-bold">Automated Escalation Alert</h3>
          </div>
          <button
            disabled={isGeneratingEmail || isSendingEmail}
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-gray-600 rounded"
          >
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
                  onChange={(e) => setEmailForm((prev) => ({ ...prev, to: e.target.value }))}
                  className="w-full text-sm p-2 rounded border border-gray-200 focus:border-amber-400 focus:ring-1 focus:ring-amber-400 outline-none"
                />
              </div>
              <div>
                <label className="block text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1">Subject</label>
                <input
                  type="text"
                  value={emailForm.subject}
                  onChange={(e) => setEmailForm((prev) => ({ ...prev, subject: e.target.value }))}
                  className="w-full text-sm p-2 rounded border border-gray-200 font-semibold focus:border-amber-400 focus:ring-1 focus:ring-amber-400 outline-none"
                />
              </div>
              <div>
                <label className="block text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1">Message Body</label>
                <textarea
                  value={emailForm.body}
                  onChange={(e) => setEmailForm((prev) => ({ ...prev, body: e.target.value }))}
                  className="w-full text-sm p-3 rounded border border-gray-200 h-64 font-mono leading-relaxed focus:border-amber-400 focus:ring-1 focus:ring-amber-400 outline-none resize-none"
                />
              </div>
            </>
          )}
        </div>

        <div className="p-4 border-t border-gray-100 bg-white flex justify-end gap-3">
          <button
            onClick={onClose}
            disabled={isGeneratingEmail || isSendingEmail}
            className="px-4 py-2 rounded-lg text-sm font-semibold text-gray-600 hover:bg-gray-100 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onSend}
            disabled={isGeneratingEmail || isSendingEmail || !emailForm.to || !emailForm.subject}
            className="flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-bold text-white bg-amber-600 hover:bg-amber-700 disabled:opacity-50 transition-colors"
          >
            {isSendingEmail ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
            {isSendingEmail ? "Sending..." : "Dispatch Alert"}
          </button>
        </div>
      </div>
    </div>
  );
}
