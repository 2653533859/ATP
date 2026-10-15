import http from './http'

export type ChaosActionType =
  | 'service_down_503'
  | 'circuit_breaker_trip'
  | 'latency_jitter'
  | 'corrupt_payload'

export interface ChaosRule {
  service_name: string
  route_pattern: string
  action: ChaosActionType
  traffic_ratio: number
  methods: string[]
  header_matchers?: Record<string, string>
  action_params?: Record<string, any>
  enabled: boolean
}

export interface ChaosExperiment {
  experiment_id: string
  name: string
  description?: string
  status: 'active' | 'paused' | 'completed'
  created_at: string
  rules: ChaosRule[]
  stats?: {
    total_evaluated: number
    total_injected: number
    injected_ratio_pct: number
  }
}

export interface CreateChaosExperimentRequest {
  name: string
  description?: string
  rules: ChaosRule[]
}

export const meshChaosApi = {
  listExperiments(): Promise<{ total: number; experiments: ChaosExperiment[] }> {
    return http.get('/mesh-chaos/experiments')
  },

  createExperiment(data: CreateChaosExperimentRequest): Promise<ChaosExperiment> {
    return http.post('/mesh-chaos/experiments', data)
  },

  getExperiment(id: string): Promise<ChaosExperiment> {
    return http.get(`/mesh-chaos/experiments/${id}`)
  },

  setExperimentStatus(id: string, status: 'active' | 'paused' | 'completed'): Promise<{ experiment_id: string; status: string }> {
    return http.post(`/mesh-chaos/experiments/${id}/status`, { status })
  },

  evaluateMeshRequest(data: {
    service_name: string
    path: string
    method?: string
    headers?: Record<string, string>
  }): Promise<{
    inject_fault: boolean
    action: string
    status_code?: number
    latency_ms?: number
    response_body?: any
    matched_rule_service?: string
  }> {
    return http.post('/mesh-chaos/evaluate', data)
  },

  getTopology(): Promise<{
    services: string[]
    dependencies: Array<{ caller: string; callee: string }>
  }> {
    return http.get('/mesh-chaos/blast-radius/topology')
  },

  evaluateBlastRadius(data: {
    injected_service: string
    max_impacted_services?: number
    max_depth?: number
    max_error_rate?: number
    protected_services?: string[]
  }): Promise<any> {
    return http.post('/mesh-chaos/blast-radius/evaluate', data)
  },

  enforceBlastRadius(data: {
    experiment_id: string
    injected_service: string
    max_impacted_services?: number
    max_depth?: number
    max_error_rate?: number
    protected_services?: string[]
  }): Promise<any> {
    return http.post('/mesh-chaos/blast-radius/enforce', data)
  },

  compileResilienceReport(data: {
    experiment_id: string
    services_data?: Array<Record<string, any>>
    sla_baseline_target?: number
    blast_radius_breached?: boolean
    emergency_aborted?: boolean
  }): Promise<any> {
    return http.post('/mesh-chaos/resilience-report/compile', data)
  },
}
