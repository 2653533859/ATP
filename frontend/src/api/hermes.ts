import http from './http'

export type HermesSourceType = 'knowledge' | 'requirement' | 'case'

export interface HermesEvaluationResult {
  set_id: string
  set_version: string
  case_id: string
  scores: {
    tool_selection: boolean | null
    citation_relevance: boolean | null
    answer_completeness: boolean | null
    refusal_correctness: boolean
  }
}

export interface HermesSourceItem {
  source_type: HermesSourceType
  source_id: number
  project_id?: number | null
  title: string
  excerpt: string
  source_ref?: string | null
  path: string
  match_terms: string[]
  match_score: number
  updated_at?: string | null
}

export interface HermesQueryResult {
  project_id: number
  query: string
  conversation_id: string
  history_used: number
  history_omitted: number
  context_chars: number
  context_budget: number
  source_types: HermesSourceType[]
  updated_from?: string | null
  updated_to?: string | null
  mode: 'llm_grounded' | 'project_retrieval' | 'no_results'
  answer: string
  sources: HermesSourceItem[]
  generated_at: string
  session_id: number
  message_index: number
  prompt_version: string
  latency_ms: number
  evaluation?: HermesEvaluationResult | null
}

export interface HermesSessionItem {
  id: number
  project_id: number
  title: string
  context_filters: Record<string, unknown>
  messages: Array<Record<string, unknown>>
  drafts: Array<Record<string, unknown>>
  metrics: Record<string, unknown>
  state_version: number
  created_at: string
  updated_at: string
}

export interface HermesGovernanceSummary {
  prompt_version: string
  prompt_versions: string[]
  evaluation_set: { id: string; version: string; size: number }
  sessions: number
  assistant_messages: number
  citation_coverage: number
  refusal_rate: number
  no_result_rate: number
  helpful_count: number
  not_helpful_count: number
  feedback_total: number
  helpful_rate: number | null
  average_latency_ms: number
  p95_latency_ms: number
  evaluation_quality: {
    runs: number
    cases_covered: number
    tool_selection: HermesEvaluationMetric
    citation_relevance: HermesEvaluationMetric
    answer_completeness: HermesEvaluationMetric
    refusal_correctness: HermesEvaluationMetric
  }
  model_planning: {
    attempts: number
    model_calls: number
    usage_calls: number
    input_tokens: number
    output_tokens: number
    total_tokens: number
    average_latency_ms: number
    fallback_count: number
    fallback_reasons: Record<string, number>
  }
  cost_tracking: {
    available: boolean
    reason?: 'no_model_calls' | 'usage_unavailable' | 'pricing_not_configured' | 'partially_unpriced' | null
    amounts_by_currency: Record<string, number>
    priced_calls: number
    unpriced_calls: number
  }
}

export interface HermesEvaluationMetric {
  evaluated: number
  passed: number
  rate: number | null
}

export type HermesToolName =
  | 'failed_tasks'
  | 'run_detail'
  | 'quality_trend'
  | 'requirement_case_links'
  | 'knowledge_detail'
export type HermesToolStatus = 'ok' | 'empty' | 'not_found' | 'timeout' | 'error'

export interface HermesToolDescriptor {
  name: HermesToolName
  description: string
  required_role: 'viewer'
  read_only: true
  timeout_max_ms: number
  arguments_schema: Record<string, unknown>
}

export interface HermesToolEvidence {
  evidence_id: string
  source_type: 'hermes_tool'
  source_ref: string
  title: string
  excerpt: string
  path: string
}

export interface HermesToolResult {
  project_id: number
  conversation_id: string
  tool: HermesToolName
  status: HermesToolStatus
  duration_ms: number
  message?: string | null
  data: Record<string, unknown>
  evidence: HermesToolEvidence[]
  generated_at: string
}

export interface HermesToolCall {
  project_id: number
  conversation_id: string
  tool: HermesToolName
  arguments?: Record<string, unknown>
  timeout_ms?: number
}

export interface HermesOrchestrationPlan {
  tool: HermesToolName
  arguments: Record<string, unknown>
  reason: string
}

export interface HermesOrchestrationStep {
  tool: HermesToolName
  arguments: Record<string, unknown>
  status: HermesToolStatus
  duration_ms: number
  message?: string | null
  data: Record<string, unknown>
  evidence: HermesToolEvidence[]
}

export interface HermesPlannerDecision {
  source: 'deterministic' | 'model' | 'deterministic_fallback'
  validation: 'not_attempted' | 'accepted' | 'unavailable' | 'rejected' | 'failed'
  model_name?: string | null
  prompt_version?: string | null
  fallback_reason?: string | null
  model_calls: number
  latency_ms: number
  usage_available: boolean
  input_tokens?: number | null
  output_tokens?: number | null
  total_tokens?: number | null
  estimated_cost?: number | null
  currency?: string | null
}

export interface HermesOrchestrationResult {
  project_id: number
  conversation_id: string
  query: string
  status: 'matched' | 'no_match' | 'needs_input' | 'cancelled'
  clarification?: string | null
  plans: HermesOrchestrationPlan[]
  steps: HermesOrchestrationStep[]
  planner: HermesPlannerDecision
  answer: string
  generated_at: string
  session_id?: number | null
  message_index?: number | null
  evaluation?: HermesEvaluationResult | null
}

export interface HermesQueryRequest {
  project_id: number
  query: string
  limit?: number
  conversation_id?: string
  history?: Array<{ role: 'user' | 'assistant'; content: string }>
  source_types?: HermesSourceType[]
  updated_from?: string
  updated_to?: string
  context_budget?: number
  session_id?: number
}

export interface HermesOrchestrationRequest {
  project_id: number
  query: string
  conversation_id?: string
  session_id?: number
}

export interface HermesDraftRequest {
  project_id: number
  draft_type: 'test_plan'
  payload: Record<string, unknown>
  sources?: Array<Record<string, unknown>>
}

export interface HermesFeedbackRequest {
  project_id: number
  message_index: number
  rating: 'helpful' | 'not_helpful'
  comment?: string
}

export const hermesApi = {
  query: (body: HermesQueryRequest) => http.post<unknown, HermesQueryResult>('/hermes/query', body),
  listTools: () => http.get<unknown, { tools: HermesToolDescriptor[]; generated_at: string }>('/hermes/tools'),
  executeTool: (body: HermesToolCall) => http.post<unknown, HermesToolResult>('/hermes/tools/execute', body),
  orchestrate: (body: HermesOrchestrationRequest) =>
    http.post<unknown, HermesOrchestrationResult>('/hermes/orchestrate', body),
  sessions: (projectId: number) =>
    http.get<unknown, HermesSessionItem[]>('/hermes/sessions', { params: { project_id: projectId } }),
  createSession: (projectId: number, title: string) =>
    http.post<unknown, HermesSessionItem>('/hermes/sessions', { project_id: projectId, title }),
  createDraft: (sessionId: number, body: HermesDraftRequest) =>
    http.post<unknown, { id: string; status: string }>(`/hermes/sessions/${sessionId}/drafts`, body),
  confirmDraft: (sessionId: number, body: { project_id: number; draft_id: string; confirmation: 'CONFIRM' }) =>
    http.post<unknown, { draft_id: string; status: string; plan_id: number }>(
      `/hermes/sessions/${sessionId}/drafts/confirm`,
      body,
    ),
  feedback: (sessionId: number, body: HermesFeedbackRequest) =>
    http.post(`/hermes/sessions/${sessionId}/feedback`, body),
  tool: (
    sessionId: number,
    toolName: 'failed_runs' | 'quality_summary',
    body: { project_id: number; arguments?: Record<string, unknown> },
  ) => http.post(`/hermes/sessions/${sessionId}/tools/${toolName}`, body),
  governance: (projectId: number) =>
    http.get<unknown, HermesGovernanceSummary>('/hermes/governance/summary', { params: { project_id: projectId } }),
}
