"use client";

import React, { useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  Database,
  FileText,
  FolderOpen,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Upload,
} from "lucide-react";

interface Contract {
  contract_id: string;
  name?: string;
  contract_type?: string;
}

interface AvailableFile {
  filename: string;
  size: number;
}

interface LandingOverlayProps {
  isOpen: boolean;
  contracts: Contract[];
  selectedContractId: string;
  availableContracts: AvailableFile[];
  onSelectContract: (contractId: string) => void;
  onUploadNewContract: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onIngestContract: (filename: string) => void;
}

export default function LandingOverlay({
  isOpen,
  contracts,
  selectedContractId,
  availableContracts,
  onSelectContract,
  onUploadNewContract,
  onIngestContract,
}: LandingOverlayProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [contractSearch, setContractSearch] = useState("");
  const [contractSort, setContractSort] = useState<"name" | "type" | "id">("name");

  if (!isOpen) return null;

  const formatSize = (size: number) => `${(size / 1024).toFixed(1)} KB`;
  const selectedContract = contracts.find((contract) => contract.contract_id === selectedContractId) || contracts[0];
  const visibleContracts = useMemo(() => {
    const query = contractSearch.trim().toLowerCase();
    return [...contracts]
      .filter((contract) => {
        const haystack = [
          contract.name,
          contract.contract_id,
          contract.contract_type,
        ].filter(Boolean).join(" ").toLowerCase();
        return !query || haystack.includes(query);
      })
      .sort((a, b) => {
        const left =
          contractSort === "type"
            ? a.contract_type || ""
            : contractSort === "id"
              ? a.contract_id || ""
              : a.name || a.contract_id || "";
        const right =
          contractSort === "type"
            ? b.contract_type || ""
            : contractSort === "id"
              ? b.contract_id || ""
              : b.name || b.contract_id || "";
        return left.localeCompare(right);
      });
  }, [contracts, contractSearch, contractSort]);

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/20 p-6 backdrop-blur-sm animate-in fade-in duration-300">
      <div className="w-full max-w-6xl overflow-hidden rounded-lg border border-slate-200 bg-white shadow-2xl">
        <div className="border-b border-slate-200 bg-white px-8 py-5">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-900">
                <ShieldCheck className="h-5 w-5 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-semibold tracking-tight text-slate-900">Contract Performance Dashboard</h1>
                <p className="mt-0.5 text-xs font-medium text-slate-500">
                  Contract intake for supplier performance monitoring.
                </p>
              </div>
            </div>

            <div className="grid w-full max-w-md grid-cols-3 overflow-hidden rounded-lg border border-slate-200 bg-slate-50 text-center text-[10px] font-bold uppercase tracking-wide text-slate-500">
              <div className="border-r border-slate-200 px-3 py-2 text-slate-800">Upload</div>
              <div className="border-r border-slate-200 px-3 py-2 text-slate-800">Ingest</div>
              <div className="px-3 py-2 text-slate-800">Dashboard</div>
            </div>
          </div>
        </div>

        <div className="grid h-[650px] grid-cols-1 overflow-hidden lg:grid-cols-[360px_1fr]">
          <aside className="flex min-h-0 flex-col border-r border-slate-200 bg-slate-50">
            <div className="border-b border-slate-200 px-6 py-4">
              <h2 className="text-xs font-bold uppercase tracking-wide text-slate-500">Indexed Contracts</h2>
              <p className="mt-1 text-xs text-slate-400">{contracts.length} active records</p>
              <div className="mt-4 space-y-2">
                <label className="flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs text-slate-500">
                  <Search className="h-3.5 w-3.5 text-slate-400" />
                  <input
                    value={contractSearch}
                    onChange={(event) => setContractSearch(event.target.value)}
                    placeholder="Search contracts"
                    className="w-full border-none bg-transparent p-0 text-xs font-medium text-slate-700 placeholder:text-slate-400 focus:ring-0"
                  />
                </label>
                <label className="flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs text-slate-500">
                  <SlidersHorizontal className="h-3.5 w-3.5 text-slate-400" />
                  <span className="shrink-0 font-semibold uppercase tracking-wide text-[10px] text-slate-400">Sort</span>
                  <select
                    value={contractSort}
                    onChange={(event) => setContractSort(event.target.value as "name" | "type" | "id")}
                    className="w-full border-none bg-transparent p-0 text-xs font-semibold text-slate-700 focus:ring-0"
                  >
                    <option value="name">Contract name</option>
                    <option value="type">Contract type</option>
                    <option value="id">Contract ID</option>
                  </select>
                </label>
              </div>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto p-4">
              {contracts.length === 0 ? (
                <div className="rounded-lg border border-dashed border-slate-300 bg-white p-6 text-center">
                  <Database className="mx-auto h-6 w-6 text-slate-300" />
                  <p className="mt-3 text-xs font-medium text-slate-400">No contracts indexed yet</p>
                </div>
              ) : visibleContracts.length === 0 ? (
                <div className="rounded-lg border border-dashed border-slate-300 bg-white p-6 text-center">
                  <Search className="mx-auto h-6 w-6 text-slate-300" />
                  <p className="mt-3 text-xs font-medium text-slate-400">No matching contracts</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {visibleContracts.map((contract, index) => {
                    const selected = contract.contract_id === selectedContractId;
                    return (
                    <button
                      key={`${contract.contract_id}-${index}`}
                      onClick={() => onSelectContract(contract.contract_id)}
                      className={`group w-full rounded-lg border bg-white p-4 text-left transition-all hover:border-blue-300 hover:shadow-sm ${
                        selected ? "border-blue-300 shadow-sm ring-1 ring-blue-100" : "border-slate-200"
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-blue-50 text-blue-600">
                          <CheckCircle2 className="h-4 w-4" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <h3 className="truncate text-sm font-semibold text-slate-800 group-hover:text-blue-700">
                            {contract.name || contract.contract_id}
                          </h3>
                          <p className="mt-1 truncate text-[10px] font-mono uppercase text-slate-400">
                            {contract.contract_id}
                          </p>
                          {contract.contract_type && (
                            <p className="mt-2 truncate text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                              {contract.contract_type}
                            </p>
                          )}
                        </div>
                      </div>
                    </button>
                    );
                  })}
                </div>
              )}
            </div>
          </aside>

          <main className="min-h-0 overflow-y-auto p-6">
            <div className="grid gap-4 lg:grid-cols-[minmax(280px,360px)_1fr]">
              <div className="rounded-lg border border-slate-200 bg-white p-5">
                <input
                  type="file"
                  ref={fileInputRef}
                  className="hidden"
                  accept=".md,.pdf"
                  onChange={onUploadNewContract}
                />
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-sm font-semibold text-slate-900">Upload Contract</h2>
                    <p className="mt-1 text-xs text-slate-500">PDF or Markdown contract file</p>
                  </div>
                  <div className="rounded-md bg-emerald-50 p-2 text-emerald-600">
                    <Upload className="h-4 w-4" />
                  </div>
                </div>

                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="mt-5 flex w-full items-center justify-center gap-2 rounded-md border border-emerald-600 bg-emerald-600 px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-emerald-700"
                >
                  Upload Contract
                  <ArrowRight className="h-4 w-4" />
                </button>
              </div>

              <div className="rounded-lg border border-slate-200 bg-slate-50 p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-sm font-semibold text-slate-900">Selected Contract</h2>
                    <p className="mt-1 text-xs text-slate-500">Open the monitoring dashboard for the highlighted contract.</p>
                  </div>
                  <div className="rounded-md bg-blue-50 p-2 text-blue-600">
                    <ShieldCheck className="h-4 w-4" />
                  </div>
                </div>
                <div className="mt-4 rounded-md border border-slate-200 bg-white px-4 py-3">
                  <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Current Record</p>
                  <p className="mt-1 truncate text-sm font-semibold text-slate-800">
                    {selectedContract?.name || selectedContract?.contract_id || "No contract selected"}
                  </p>
                  {selectedContract?.contract_id && (
                    <p className="mt-1 truncate font-mono text-[10px] uppercase text-slate-400">
                      {selectedContract.contract_id}
                    </p>
                  )}
                  {selectedContract?.contract_type && (
                    <p className="mt-2 truncate text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                      {selectedContract.contract_type}
                    </p>
                  )}
                </div>
                <button
                  disabled={!selectedContract?.contract_id}
                  onClick={() => selectedContract?.contract_id && onSelectContract(selectedContract.contract_id)}
                  className="mt-4 flex w-full items-center justify-center gap-2 rounded-md border border-blue-200 bg-white px-4 py-3 text-sm font-semibold text-blue-700 transition-colors hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Open Dashboard
                  <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="mt-4 overflow-hidden rounded-lg border border-slate-200 bg-white">
              <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50 px-4 py-3">
                <div>
                  <h2 className="text-sm font-semibold text-slate-900">Available Contract Files</h2>
                  <p className="mt-1 text-xs text-slate-500">{availableContracts.length} files available for ingestion</p>
                </div>
                <div className="rounded-md bg-amber-50 p-2 text-amber-600">
                  <FolderOpen className="h-4 w-4" />
                </div>
              </div>

              <div className="max-h-[230px] divide-y divide-slate-100 overflow-y-auto">
                {availableContracts.length === 0 ? (
                  <div className="p-8 text-center text-sm text-slate-400">No cached sources found</div>
                ) : (
                  availableContracts.map((file) => (
                    <button
                      key={file.filename}
                      onClick={() => onIngestContract(file.filename)}
                      className="grid w-full grid-cols-[minmax(260px,1fr)_90px_130px] items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-blue-50/60"
                    >
                      <span className="flex min-w-0 items-center gap-3">
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-slate-100 text-slate-500">
                          <FileText className="h-4 w-4" />
                        </span>
                        <span className="min-w-0">
                          <span className="block truncate text-sm font-semibold text-slate-800">{file.filename}</span>
                          <span className="block text-[10px] uppercase tracking-wide text-slate-400">
                            {file.filename.toLowerCase().endsWith(".pdf") ? "PDF source" : "Markdown source"}
                          </span>
                        </span>
                      </span>
                      <span className="text-xs font-medium text-slate-500">{formatSize(file.size)}</span>
                      <span className="justify-self-end rounded-md border border-blue-200 bg-white px-3 py-1.5 text-xs font-semibold text-blue-700">
                        Ingest
                      </span>
                    </button>
                  ))
                )}
              </div>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
