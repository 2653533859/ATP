import http from './http'

export type RootCauseCategory =
  | 'ASSERTION_BUSINESS_LOGIC_DEFECT'
  | 'DOWNSTREAM_SERVICE_CRASH'
  | 'DATABASE_EXECUTION_FAILURE'
  | 'NETWORK_GATEWAY_TIMEOUT'
  | 'AUTHENTICATION_EXPIRED'
  | 'UI_DOM_LOCATOR_DRIFT'
  | 'TEST_DATA_PRECONDITION_UNMET'
  | 'RESOURCE_STARVATION'
  | 'UNKNOWN_FAILURE'

export interface EvidenceSnippetItem {
  evidence_type: 'CONSOLE_LOG' | 'HTTP_RESPONSE' | 'SPAN_TRACE' | 'ENV_FACTOR'
  title: string
  content: string
  is_key_evidence: boolean
}

export interface RootCauseAttributionReport {
  diagnosis_id: string
  case_id: string
  case_name: string
  category: RootCauseCategory
  confidence_score: number
  primary_root_cause_summary: string
  culprit_service: string
  culprit_location: string
  causal_chain: string[]
  evidence_snippets: EvidenceSnippetItem[]
  suggested_action: string
  diagnosed_at: string
}

export interface IncidentKnowledgeItem {
  incident_id: string
  title: string
  category: string
  service_name: string
  error_pattern: string
  signature_tokens: string[]
  root_cause_explanation: string
  verified_resolution: string
  external_ticket_ref: string
  occurrences_count: number
  created_at: string
}

export interface FingerprintMatchResultItem {
  incident: IncidentKnowledgeItem
  similarity_score: number
  match_tier: 'EXACT_MATCH' | 'HIGH_SIMILARITY' | 'MEDIUM_SIMILARITY' | 'LOW_SIMILARITY'
  matched_tokens: string[]
}

export interface IncidentMatchReport {
  query_fingerprint_tokens: string[]
  matches_count: number
  matches: FingerprintMatchResultItem[]
  best_match_resolution: string | null
  recommendation_summary: string
  matched_at: string
}

export interface DefectTicketItem {
  ticket_id: string
  title: string
  severity: 'CRITICAL' | 'MAJOR' | 'NORMAL' | 'MINOR'
  platform: 'JIRA' | 'GITHUB_ISSUE' | 'WEBHOOK_ROBOT'
  case_id: string
  case_name: string
  culprit_service: string
  assignee: string
  external_issue_id: string
  description: string
  status: 'OPEN' | 'ASSIGNED' | 'DISPATCHED' | 'RESOLVED'
  labels: string[]
  created_at: string
}

export const rootCauseDiagnosisApi = {
  analyze(data: {
    case_id: string
    case_name: string
    console_logs?: string
    http_status_code?: number
    http_response_body?: string
    spans?: any[]
    env_factors?: any
  }): Promise<{ message: string; report: RootCauseAttributionReport }> {
    return http.post('/diagnosis/root-cause/analyze', data)
  },

  batchAnalyze(failures: any[]): Promise<{ total: number; reports: RootCauseAttributionReport[] }> {
    return http.post('/diagnosis/root-cause/batch-analyze', { failures })
  },

  listReports(params?: { limit?: number; category?: string }): Promise<{ total: number; reports: RootCauseAttributionReport[] }> {
    return http.get('/diagnosis/root-cause/reports', { params })
  },

  getReport(diagnosisId: string): Promise<RootCauseAttributionReport> {
    return http.get(`/diagnosis/root-cause/reports/${diagnosisId}`)
  },

  clearReports(): Promise<{ message: string; cleared_count: number }> {
    return http.delete('/diagnosis/root-cause/reports')
  },
}

export const incidentFingerprintApi = {
  match(data: {
    error_message: string
    stack_trace?: string
    service_name?: string
    min_similarity?: number
    limit?: number
  }): Promise<IncidentMatchReport> {
    return http.post('/diagnosis/fingerprint/match', data)
  },

  registerIncident(data: {
    title: string
    category?: string
    service_name: string
    error_pattern: string
    root_cause_explanation: string
    verified_resolution: string
    external_ticket_ref?: string
    incident_id?: string
  }): Promise<{ message: string; incident: IncidentKnowledgeItem }> {
    return http.post('/diagnosis/fingerprint/incidents', data)
  },

  listIncidents(): Promise<{ total: number; incidents: IncidentKnowledgeItem[] }> {
    return http.get('/diagnosis/fingerprint/incidents')
  },

  deleteIncident(incidentId: string): Promise<{ message: string; incident_id: string }> {
    return http.delete(`/diagnosis/fingerprint/incidents/${incidentId}`)
  },

  clearIncidents(): Promise<{ message: string; cleared_count: number }> {
    return http.delete('/diagnosis/fingerprint/incidents')
  },
}

export const defectTicketDispatchApi = {
  dispatch(data: {
    case_id: string
    case_name: string
    category: string
    primary_summary: string
    culprit_service?: string
    culprit_location?: string
    causal_chain?: string[]
    suggested_action?: string
    http_status_code?: number
    error_message?: string
    platform?: string
    override_assignee?: string
    is_critical_asset?: boolean
  }): Promise<{ message: string; ticket: DefectTicketItem }> {
    return http.post('/diagnosis/ticket-dispatch/dispatch', data)
  },

  listTickets(params?: { platform?: string; severity?: string; culprit_service?: string; limit?: number }): Promise<{ total: number; tickets: DefectTicketItem[] }> {
    return http.get('/diagnosis/ticket-dispatch/tickets', { params })
  },

  getTicket(ticketId: string): Promise<DefectTicketItem> {
    return http.get(`/diagnosis/ticket-dispatch/tickets/${ticketId}`)
  },

  updateStatus(ticketId: string, status: string): Promise<{ message: string; ticket_id: string; status: string }> {
    return http.patch(`/diagnosis/ticket-dispatch/tickets/${ticketId}`, { status })
  },

  clearTickets(): Promise<{ message: string; cleared_count: number }> {
    return http.delete('/diagnosis/ticket-dispatch/tickets')
  },
}
