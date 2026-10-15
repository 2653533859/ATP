import http from './http'

export interface ExplorationNode {
  id: string
  name: string
  depth: number
  actions_count: number
  visited_count: number
}

export interface ExplorationLink {
  from: string
  to: string
  action: string
}

export interface ExplorationCoverageMetrics {
  total_states: number
  total_actions_discovered: number
  total_actions_visited: number
  coverage_percent: number
  total_transitions: number
  current_state_id: string | null
  circuit_breaker?: {
    is_tripped?: boolean
    trip_reason?: string | null
    trip_category?: string | null
    consecutive_zero_elements?: number
    consecutive_failures?: number
    oscillation_count?: number
    step_count?: number
  }
  nodes?: ExplorationNode[]
  links?: ExplorationLink[]
}

export interface ExplorationStepRequest {
  elements: Array<Record<string, unknown>>
  screen_name: string
  session_id?: string
  strategy?: 'bfs' | 'dfs'
  max_depth?: number
}

export interface ExplorationStepResponse {
  session_id: string
  next_action: Record<string, unknown> | null
  current_state_id: string
  metrics: ExplorationCoverageMetrics
}

export interface SynthesizeCaseRequest {
  name: string
  module_id: number
  case_type?: 'android' | 'web' | 'ios'
  events: Array<Record<string, unknown>>
  description?: string
  persist?: boolean
}

export interface CircuitBreakerEvaluateRequest {
  element_count: number
  last_action_success?: boolean
  is_oscillation?: boolean
  screen_name?: string
}

export interface CircuitBreakerEvaluateResponse {
  is_tripped: boolean
  trip_reason: string | null
  trip_category: string | null
  consecutive_zero_elements: number
  consecutive_failures: number
  oscillation_count: number
  step_count: number
  status: 'normal' | 'tripped'
}

export const explorationApi = {
  step: (payload: ExplorationStepRequest) =>
    http.post<unknown, ExplorationStepResponse>('/exploration/step', payload),
  getSession: (sessionId: string) =>
    http.get<unknown, ExplorationCoverageMetrics>(`/exploration/sessions/${sessionId}`),
  synthesizeCase: (payload: SynthesizeCaseRequest) =>
    http.post<unknown, Record<string, unknown>>('/exploration/synthesize-case', payload),
  evaluateCircuitBreaker: (payload: CircuitBreakerEvaluateRequest) =>
    http.post<unknown, CircuitBreakerEvaluateResponse>('/exploration/circuit-breaker/evaluate', payload),
}
