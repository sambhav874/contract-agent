const API_BASE_URL = "http://localhost:8000";

async function apiError(res: Response, fallback: string) {
  let detail = fallback;
  try {
    const body = await res.clone().json();
    detail = body?.detail || body?.message || fallback;
  } catch {
    try {
      const text = await res.text();
      if (text.trim()) detail = text.trim();
    } catch {
      detail = fallback;
    }
  }
  return new Error(detail);
}

export async function fetchContracts() {
  const res = await fetch(`${API_BASE_URL}/contracts`);
  if (!res.ok) throw new Error("Failed to fetch contracts");
  return res.json();
}

export async function fetchContractText(contractId: string) {
  const res = await fetch(`${API_BASE_URL}/contracts/${contractId}/text`);
  if (!res.ok) throw new Error("Failed to fetch contract text");
  return res.json();
}

export async function fetchKPIs(contractId: string) {
  const res = await fetch(`${API_BASE_URL}/contracts/${contractId}/kpis`);
  if (!res.ok) throw new Error("Failed to fetch KPIs");
  return res.json();
}

export async function fetchBreaches(contractId: string) {
  const res = await fetch(`${API_BASE_URL}/contracts/${contractId}/breaches`);
  if (!res.ok) throw new Error("Failed to fetch breaches");
  return res.json();
}

export async function fetchPerformance(contractId: string) {
  const res = await fetch(`${API_BASE_URL}/contracts/${contractId}/performance`);
  if (!res.ok) throw new Error("Failed to fetch performance");
  return res.json();
}

export async function evaluateContract(contractId: string) {
  const res = await fetch(`${API_BASE_URL}/contracts/${contractId}/evaluate`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to run evaluation");
  return res.json();
}

export async function updateBreach(breachId: string, updates: any) {
  const res = await fetch(`${API_BASE_URL}/breaches/${breachId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  if (!res.ok) throw new Error("Failed to update breach");
  return res.json();
}

export async function chatWithContract(contractId: string, question: string, breachId?: string, sessionId?: string) {
  const res = await fetch(`${API_BASE_URL}/contracts/${contractId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, breach_id: breachId, session_id: sessionId }),
  });
  if (!res.ok) throw new Error("Failed to chat with contract");
  return res.json();
}

export async function chatWithContractStream(contractId: string, question: string, breachId?: string, sessionId?: string) {
  const res = await fetch(`${API_BASE_URL}/contracts/${contractId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, breach_id: breachId, session_id: sessionId }),
  });
  if (!res.ok) throw new Error("Failed to start chat stream");
  return res;
}

export async function clearChatSession(sessionId: string) {
  const res = await fetch(`${API_BASE_URL}/chat-session/${sessionId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to clear chat session");
  return res.json();
}

export async function fetchAvailableContracts() {
  const res = await fetch(`${API_BASE_URL}/available-contracts`);
  if (!res.ok) throw new Error("Failed to fetch available contracts");
  return res.json();
}

export async function ingestContract(filename: string) {
  const res = await fetch(`${API_BASE_URL}/contracts/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename }),
  });
  if (!res.ok) throw await apiError(res, "Failed to ingest contract");
  return res.json();
}

export async function extractKPIs(contractId: string) {
  const res = await fetch(`${API_BASE_URL}/contracts/${contractId}/extract-kpis`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to extract KPIs");
  return res.json();
}

export async function getKpiTimeSeries(contractId: string, kpiId: string) {
  const res = await fetch(`${API_BASE_URL}/contracts/${contractId}/kpis/${kpiId}/timeseries`);
  if (!res.ok) throw new Error("Failed to fetch KPI time-series");
  return res.json();
}

export async function generateBreachEmail(breachId: string) {
  const res = await fetch(`${API_BASE_URL}/breaches/${breachId}/generate-email`, {
    method: "POST"
  });
  if (!res.ok) throw new Error("Failed to generate breach email");
  return res.json();
}

export async function sendBreachEmail(breachId: string, payload: { to: string; subject: string; body: string }) {
  const res = await fetch(`${API_BASE_URL}/breaches/${breachId}/send-email`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to send breach email");
  return res.json();
}

export async function fetchPortfolioSummary() {
  const res = await fetch(`${API_BASE_URL}/portfolio/summary`);
  if (!res.ok) throw new Error("Failed to fetch portfolio summary");
  return res.json();
}
export async function uploadActualsCsv(contractId: string, file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE_URL}/contracts/${contractId}/actuals/upload`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error("Failed to upload actuals CSV");
  return res.json();
}
export async function uploadContract(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE_URL}/contracts/upload`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw await apiError(res, "Failed to upload contract file");
  return res.json();
}

// ── Question / Answer Library ──

export async function fetchQACategories(contractId: string) {
  const res = await fetch(`${API_BASE_URL}/contracts/${contractId}/qa/categories`);
  if (!res.ok) throw new Error("Failed to fetch QA categories");
  return res.json();
}

export async function generateQACategories(contractId: string) {
  const res = await fetch(`${API_BASE_URL}/contracts/${contractId}/qa/generate`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to generate QA categories");
  return res.json();
}

export async function searchAnswer(contractId: string, payload: { question: string }) {
  const res = await fetch(`${API_BASE_URL}/contracts/${contractId}/qa/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to search answer");
  return res.json();
}

export async function saveQAPair(contractId: string, payload: { category: string; question: string; answer: string; sources?: string[]; exact_quotes?: string[]; justification?: string; confidence?: number }) {
  const res = await fetch(`${API_BASE_URL}/contracts/${contractId}/qa/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to save QA pair");
  return res.json();
}

export async function fetchSavedQA(contractId: string) {
  const res = await fetch(`${API_BASE_URL}/contracts/${contractId}/qa/saved`);
  if (!res.ok) throw new Error("Failed to fetch saved QA");
  return res.json();
}

export async function deleteSavedQA(contractId: string, qaId: string) {
  const res = await fetch(`${API_BASE_URL}/contracts/${contractId}/qa/saved/${qaId}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete saved QA");
  return res.json();
}

export async function fetchSemanticMemory() {
  const res = await fetch(`${API_BASE_URL}/memory/semantic`);
  if (!res.ok) throw new Error("Failed to fetch semantic memory");
  return res.json();
}

export async function fetchEpisodicMemory() {
  const res = await fetch(`${API_BASE_URL}/memory/episodic`);
  if (!res.ok) throw new Error("Failed to fetch episodic memory");
  return res.json();
}
