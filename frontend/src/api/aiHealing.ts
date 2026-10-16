import http from './http'

export type LocatorType = 'xpath' | 'css_selector' | 'accessibility_id' | 'id' | 'name' | 'test_id' | 'text'

export interface ElementFingerprintItem {
  tag_name: string
  text_content?: string | null
  element_id?: string | null
  class_names?: string[]
  attributes?: Record<string, string>
  parent_tag?: string | null
  xpath?: string | null
}

export interface HealedLocatorProposalItem {
  proposal_id: string
  healed_locator: string
  locator_type: LocatorType
  confidence_score: number
  match_strategy: string
  matched_element: ElementFingerprintItem
  reason: string
}

export interface LocatorHealingResultItem {
  audit_id: string
  success: boolean
  original_locator: string
  best_proposal: HealedLocatorProposalItem | null
  all_proposals: HealedLocatorProposalItem[]
  elements_scanned_count: number
  healed_at: string
}


export type AssertionToleranceMode = 'strict' | 'compatible' | 'lenient'
export type SchemaDriftType = 'extra_field' | 'missing_field' | 'type_drift' | 'nullable_drift'

export interface SchemaDriftDetailItem {
  field_path: string
  drift_type: SchemaDriftType
  expected: any
  actual: any
  is_breaking: boolean
  description: string
  suggested_autofix?: Record<string, any> | null
}

export interface FlexibleAssertionResultItem {
  audit_id: string
  passed: boolean
  tolerance_mode: AssertionToleranceMode
  total_drifts_count: number
  drifts: SchemaDriftDetailItem[]
  autofixed_schema: Record<string, any> | null
  evaluated_at: string
  summary: string
}

export interface EvaluateSchemaAssertionRequest {
  expected_schema: Record<string, any>
  actual_payload: any
  mode?: AssertionToleranceMode
  ignore_extra_fields?: boolean
  ignore_array_order?: boolean
  allow_numeric_string_coercion?: boolean
  autofix_schema?: boolean
}
export interface HealLocatorRequest {
  original_locator: string
  locator_type?: LocatorType
  last_known_fingerprint?: ElementFingerprintItem | null
  live_dom_elements: ElementFingerprintItem[]
  min_confidence?: number
  error_message?: string
}

export const aiHealingLocatorsApi = {
  healLocator(data: HealLocatorRequest): Promise<LocatorHealingResultItem> {
    return http.post('/ai-healing/locators/heal', data)
  },

  listHistory(): Promise<{ total: number; history: LocatorHealingResultItem[] }> {
    return http.get('/ai-healing/locators/history')
  },
}

export const flexibleAssertionApi = {
  evaluate(data: EvaluateSchemaAssertionRequest): Promise<FlexibleAssertionResultItem> {
    return http.post('/ai-healing/assertions/evaluate', data)
  },

  autofix(data: EvaluateSchemaAssertionRequest): Promise<{
    message: string
    has_drifts: boolean
    drifts_count: number
    autofixed_schema: Record<string, any>
  }> {
    return http.post('/ai-healing/assertions/autofix', data)
  },

  listHistory(): Promise<{ total: number; history: FlexibleAssertionResultItem[] }> {
    return http.get('/ai-healing/assertions/history')
  },
}

export type HealingActionType = 'locator_replaced' | 'schema_autofixed' | 'assertion_tolerated' | 'retry_with_backoff'
export type HealingVerificationStatus = 'verified_success' | 'verified_failure' | 'pending_verify' | 'auto_accepted'

export interface FaultClusterItem {
  cluster_id: string
  signature: string
  primary_exception: string
  root_cause_summary: string
  occurrences_count: number
  affected_case_ids: number[]
  affected_run_ids: number[]
  first_seen: string
  last_seen: string
  suggested_healing_action: string
}

export interface HealingAuditEntryItem {
  audit_id: string
  case_id: number
  step_name: string
  action_type: HealingActionType
  original_value: any
  healed_value: any
  confidence_score: number
  verification_status: HealingVerificationStatus
  cluster_id?: string | null
  duration_ms: number
  metadata: Record<string, any>
  created_at: string
}

export interface HealingMetricsSummary {
  total_healing_actions_count: number
  verification_success_rate_pct: number
  average_confidence_score: number
  total_fault_clusters_count: number
  estimated_engineering_hours_saved: number
}

export interface ClusterErrorRequest {
  case_id: number
  run_id: number
  exception_type: string
  error_message: string
  stack_trace?: string | null
  root_cause_hint?: string | null
}

export interface RecordHealingActionRequest {
  case_id: number
  step_name: string
  action_type: HealingActionType
  original_value: any
  healed_value: any
  confidence_score?: number
  verification_status?: HealingVerificationStatus
  cluster_id?: string | null
  duration_ms?: number
  metadata?: Record<string, any>
}

export const healingAuditTrailApi = {
  clusterError(data: ClusterErrorRequest): Promise<{ message: string; cluster: FaultClusterItem }> {
    return http.post('/ai-healing/audit/cluster', data)
  },

  listClusters(): Promise<{ total: number; clusters: FaultClusterItem[] }> {
    return http.get('/ai-healing/audit/clusters')
  },

  getCluster(clusterId: string): Promise<FaultClusterItem> {
    return http.get(`/ai-healing/audit/clusters/${clusterId}`)
  },

  recordAction(data: RecordHealingActionRequest): Promise<{ message: string; entry: HealingAuditEntryItem }> {
    return http.post('/ai-healing/audit/record-action', data)
  },

  listEntries(params?: { case_id?: number; action_type?: string }): Promise<{ total: number; entries: HealingAuditEntryItem[] }> {
    return http.get('/ai-healing/audit/entries', { params })
  },

  getMetrics(): Promise<HealingMetricsSummary> {
    return http.get('/ai-healing/audit/metrics')
  },
}
