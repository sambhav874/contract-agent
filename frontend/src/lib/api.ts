const API_BASE_URL = "http://localhost:8000";

export async function fetchContracts() {
  const res = await fetch(`${API_BASE_URL}/contracts`);
  if (!res.ok) throw new Error("Failed to fetch contracts");
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

export async function chatWithContract(contractId: string, question: string, breachId?: string) {
  const res = await fetch(`${API_BASE_URL}/contracts/${contractId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, breach_id: breachId }),
  });
  if (!res.ok) throw new Error("Failed to chat with contract");
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
  if (!res.ok) throw new Error("Failed to ingest contract");
  return res.json();
}

export async function extractKPIs(contractId: string) {
  const res = await fetch(`${API_BASE_URL}/contracts/${contractId}/extract-kpis`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to extract KPIs");
  return res.json();
}

