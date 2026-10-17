import http from './http'

export interface TargetElementSpec {
  original_locator: string
  tag_name?: string
  text_content?: string
  test_id?: string
  attributes?: Record<string, string>
  bounding_box?: Record<string, number>
}

export interface CandidateElementItem {
  candidate_id: string
  tag_name: string
  text_content?: string
  test_id?: string
  attributes?: Record<string, string>
  bounding_box?: Record<string, number>
  xpath?: string
}

export interface StrategyScoreBreakdown {
  text_semantic_score: number
  test_id_score: number
  tag_role_score: number
  attribute_score: number
  spatial_score: number
  composite_confidence: number
}

export interface LocatorHealingResult {
  healing_id: string
  original_locator: string
  healed_locator: string
  is_healed: boolean
  confidence_score: number
  winning_strategy: string
  scores_breakdown: StrategyScoreBreakdown
  remediation_patch_code: string
  retry_executed: boolean
  retry_success: boolean
  healed_at: string
}

export interface HealingStatistics {
  total_healing_attempts: number
  successful_healings_count: number
  healing_success_rate_pct: number
  strategy_distribution: Record<string, number>
}

export interface AssertionPatchItem {
  patch_id: string
  case_id: string
  endpoint: string
  original_assertion: string
  patched_assertion: string
  patch_type: string
  confidence_score: number
  explanation: string
  python_code_diff: string
  is_applied: boolean
  created_at: string
}

export interface HealingStageRecordItem {
  stage_index: number
  stage_name: string
  status: 'PASSED' | 'BLOCKED' | 'SKIPPED' | 'FAILED'
  duration_ms: number
  summary: string
  details: Record<string, any>
}

export interface HealingAuditPipelineReport {
  pipeline_id: string
  case_id: string
  case_name: string
  failure_category: string
  patch_type: string
  original_code: string
  healed_code: string
  patch_diff: string
  diff_sha256: string
  dry_run_verified: boolean
  is_applied: boolean
  is_rolled_back: boolean
  stages: HealingStageRecordItem[]
  total_duration_ms: number
  verdict_summary: string
  created_at: string
}

export const smartLocatorHealingApi = {
  heal(data: {
    target: TargetElementSpec
    candidates: CandidateElementItem[]
    execute_retry?: boolean
  }): Promise<{ message: string; result: LocatorHealingResult }> {
    return http.post('/healing/locator/heal', data)
  },

  getHistory(params?: { limit?: number }): Promise<{ statistics: HealingStatistics; history: LocatorHealingResult[] }> {
    return http.get('/healing/locator/history', { params })
  },

  clearHistory(): Promise<{ message: string; cleared_count: number }> {
    return http.delete('/healing/locator/history')
  },
}

export const adaptiveAssertionPatchApi = {
  derive(data: {
    case_id: string
    original_assertion: string
    actual_response_payload: any
    endpoint?: string
    expected_value?: any
  }): Promise<{ message: string; patch: AssertionPatchItem }> {
    return http.post('/healing/assertion-patch/derive', data)
  },

  apply(patchId: string): Promise<{ message: string; patch_id: string }> {
    return http.post(`/healing/assertion-patch/apply/${patchId}`)
  },

  listPatches(params?: { case_id?: string; patch_type?: string }): Promise<{ total: number; patches: AssertionPatchItem[] }> {
    return http.get('/healing/assertion-patch/patches', { params })
  },

  clearPatches(): Promise<{ message: string; cleared_count: number }> {
    return http.delete('/healing/assertion-patch/patches')
  },
}

export const selfHealingPipelineApi = {
  execute(data: {
    case_id: string
    case_name: string
    console_logs?: string
    http_status_code?: number
    http_response_payload?: any
    broken_locator?: string
    dom_candidates?: any[]
    original_assertion?: string
    auto_apply?: boolean
  }): Promise<{ message: string; report: HealingAuditPipelineReport }> {
    return http.post('/healing/pipeline/execute', data)
  },

  rollback(pipelineId: string): Promise<{ message: string; pipeline_id: string }> {
    return http.post(`/healing/pipeline/${pipelineId}/rollback`)
  },

  listReports(params?: { limit?: number; applied_only?: boolean }): Promise<{ total: number; reports: HealingAuditPipelineReport[] }> {
    return http.get('/healing/pipeline/reports', { params })
  },

  getReport(pipelineId: string): Promise<HealingAuditPipelineReport> {
    return http.get(`/healing/pipeline/reports/${pipelineId}`)
  },

  clearReports(): Promise<{ message: string; cleared_count: number }> {
    return http.delete('/healing/pipeline/reports')
  },
}
export const selfHealingCoreApi = {
  diagnoseLocator(data: Record<string, any>): Promise<{ diagnosis: any }> {
    return http.post('/self-healing/locator/diagnose', data)
  },

  healStep(data: Record<string, any>): Promise<{ message: string; result: any }> {
    return http.post('/self-healing/locator/heal', data)
  },

  commitPatch(patchId: string): Promise<{ message: string; patch: any }> {
    return http.post(`/self-healing/patch/${patchId}/commit`)
  },

  rejectPatch(patchId: string): Promise<{ message: string; patch: any }> {
    return http.post(`/self-healing/patch/${patchId}/reject`)
  },

  getPatch(patchId: string): Promise<{ patch: any }> {
    return http.get(`/self-healing/patch/${patchId}`)
  },

  listPatches(params?: { status?: string; limit?: number }): Promise<{ total: number; patches: any[] }> {
    return http.get('/self-healing/patches', { params })
  },
}
