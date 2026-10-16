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
