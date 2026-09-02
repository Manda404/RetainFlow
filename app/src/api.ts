export type RetainFlowRow = Record<string, string | number | boolean | null | undefined>;

export type BusinessType =
  | "kpi"
  | "customer_ranking"
  | "customer_profile"
  | "customer_not_found"
  | "risk_explanation"
  | "retention_strategy"
  | "visualization"
  | "email_draft"
  | "data_table"
  | "data_count"
  | "data_query"
  | "text"
  | "combination";

export type ActivityItem = {
  id: string;
  agent: string;
  tool?: string;
  business_label: string;
  status: "pending" | "running" | "completed" | "failed" | "skipped";
  summary: string;
  started_at?: string;
  completed_at?: string;
  duration_ms?: number;
  details?: Record<string, unknown>;
  sources?: Array<Record<string, unknown>>;
  error?: string;
};

export type ChatResponse = {
  agent_name: string;
  answer: string;
  response_type: "text" | "table" | "plotly" | "email_draft" | "records";
  business_type: BusinessType;
  data: RetainFlowRow[] | RetainFlowRow | null;
  figure: Record<string, unknown> | null;
  metadata: Record<string, unknown> & { activity?: ActivityItem[] };
};

const API_BASE = import.meta.env.VITE_RETAINFLOW_API_BASE_URL || "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "RetainFlow API request failed");
  return payload;
}

export function health() {
  return request<{ status: string; service: string; version: string }>("/health");
}

export function chat(message: string, limit = 8) {
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ message, limit }),
  });
}

export function customerProfile(customerId: string) {
  return request<ChatResponse>(`/customers/${encodeURIComponent(customerId)}/profile`);
}

export function rowsFromResponse(payload: ChatResponse | null): RetainFlowRow[] {
  if (!payload?.data) return [];
  return Array.isArray(payload.data) ? payload.data : [payload.data];
}

export { API_BASE };
