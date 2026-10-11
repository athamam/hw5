// Talks to the Campus Customs FastAPI backend (Problem 7).
export const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

export type AgentName = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'
export type TicketStatus = 'open' | 'in_progress' | 'waiting_on_human' | 'resolved'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: TicketStatus
  notes: string | null
  created_at: string
  is_resolved: boolean
  open_or_resolved: 'open' | 'resolved'
}

export interface AgentEvent {
  index: number
  timestamp: string
  run_id: string
  ticket_id: number | null
  agent: AgentName
  delegated_by: AgentName | null
  depth: number
  kind: 'agent_turn' | 'tool_results' | 'end' | 'error'
  said: string | null
  tools: { tool: string; args?: Record<string, unknown>; result?: unknown }[]
  usage: { requests?: number; tool_calls?: number; total_tokens?: number }
  output: AgentOutput | null
}

export interface AgentOutput {
  agent?: AgentName
  summary?: string
  decision?: string
  recommendation?: string
  actions_taken?: string[]
  approval_ids?: number[]
  human_approvals_needed?: number[]
  draft_ids?: number[]
  blockers?: string[]
  next_steps?: string[]
  ticket_status?: TicketStatus
  facts?: { fact: string; source_tool: string }[]
}

export interface Approval {
  id: number
  kind: 'payment' | 'purchase_order' | 'price_override'
  ticket_id: number | null
  ref_type: string
  ref_id: string
  amount: number
  details: Record<string, unknown> | null
  reason: string
  requested_by: AgentName
  status: 'pending' | 'approved' | 'rejected'
  decided_by: string | null
  created_at: string
}

export interface Cash {
  account: string
  balance: number
  as_of: string
  pending_payment_requests: { id: number; amount: number; ref_type: string; ref_id: string }[]
  projected_balance: number
}

export interface RunResult {
  run_id: string
  ticket_id: number
  decision: (AgentOutput & { assigned_to: AgentName[] }) | null
  error: string | null
  usage: { requests: number; tool_calls: number; total_tokens: number }
  audit_steps: number
}

export interface TicketDetail {
  ticket: Ticket
  updates: { id: number; agent: string; note: string; created_at: string }[]
  approvals: Approval[]
  purchase_orders: Record<string, unknown>[]
  drafts: { id: number; recipient: string; subject: string; body: string; drafted_by: string }[]
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error((body as { detail?: string }).detail ?? `HTTP ${res.status}`)
  return body as T
}

export const api = {
  health: () => request<{ status: string; model: string; busy_with_ticket: number | null }>('/health'),
  tickets: () => request<{ tickets: Ticket[]; running_ticket: number | null }>('/tickets'),
  ticket: (id: number) => request<TicketDetail>(`/tickets/${id}`),
  run: (id: number) => request<RunResult>(`/tickets/${id}/run`, { method: 'POST' }),
  events: (after: number) => request<{ events: AgentEvent[]; last_index: number }>(`/events?after=${after}&limit=500`),
  approvals: () => request<{ approvals: Approval[] }>('/approvals?status=all'),
  approve: (id: number, approvedBy: string) =>
    request<{ result: Record<string, unknown>; cash_balance: number }>(`/approvals/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approved_by: approvedBy }),
    }),
  reject: (id: number, rejectedBy: string, reason: string) =>
    request<Record<string, unknown>>(`/approvals/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ rejected_by: rejectedBy, reason }),
    }),
  cash: () => request<Cash>('/cash'),
  reset: () => request<{ ok: boolean; cash_balance: number }>('/reset', { method: 'POST' }),
}
