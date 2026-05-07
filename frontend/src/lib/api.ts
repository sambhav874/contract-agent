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

