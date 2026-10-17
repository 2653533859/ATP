import http from './http'

export interface SemanticLocatorDTO {
  locator_type: string
  locator_value: string
  semantic_role?: string
  element_text?: string
}

export interface SemanticActionStepDTO {
  step_id: string
  action_type: string
  source_platform: string
  target_platform: string
  source_locator?: SemanticLocatorDTO
  target_locator?: SemanticLocatorDTO
  parameters: Record<string, any>
  confidence: number
  notes?: string
}

export interface ActionMappingResultDTO {
  mapping_id: string
  case_id?: string
  case_name?: string
  source_platform: string
  target_platform: string
  total_steps: number
  mapped_steps_count: number
  average_confidence: number
  unresolved_count: number
  unresolved_step_ids: string[]
  mapped_steps: SemanticActionStepDTO[]
  created_at: string
}

export interface ParityGapItemDTO {
  gap_id: string
  gap_type: 'MISSING_CORE_CONTROL' | 'MISSING_OPTIONAL_CONTROL' | 'SEMANTIC_TEXT_DRIFT' | 'ACTION_CAPABILITY_MISMATCH' | 'LAYOUT_ORIENTATION_DIFF'
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  title: string
  description: string
  source_node?: any
  target_node?: any
  suggested_fix?: string
  detected_at: string
}

export interface ParityScoreBreakdownDTO {
  control_alignment_score: number
  core_business_score: number
  text_consistency_score: number
  interaction_compatibility_score: number
  weighted_composite_score: number
}

export interface ParityAuditReportDTO {
  report_id: string
  screen_name: string
  source_platform: string
  target_platform: string
  composite_score: number
  grade: 'GRADE_A' | 'GRADE_B' | 'GRADE_C' | 'GRADE_F'
  verdict: 'PASS' | 'WARN' | 'BLOCK'
  scores: ParityScoreBreakdownDTO
  matrix_summary: {
    total_source_nodes: number
    total_target_nodes: number
    aligned_pairs_count: number
    alignment_rate: number
  }
  discrepancy_summary: {
    total_gaps_count: number
    critical_count: number
    high_count: number
    medium_count: number
    low_count: number
  }
  gaps: ParityGapItemDTO[]
  executive_summary: string
  generated_at: string
}

export const crossPlatformMigrationApi = {
  translateCase(payload: {
    case_id?: string
    case_name?: string
    source_platform: string
    target_platform: string
    steps: any[]
    target_candidates?: any[]
  }): Promise<{ message: string; result: ActionMappingResultDTO }> {
    return http.post('/migration/case/translate', payload)
  },

  matchElements(payload: {
    source_element: any
    candidates: any[]
    threshold?: number
  }): Promise<{ match: any; is_confident: boolean }> {
    return http.post('/migration/elements/match', payload)
  },

  batchMigrate(payload: {
    case_ids: string[]
    source_platform: string
    target_platform: string
    target_device_id?: string
  }): Promise<{ message: string; batch: any }> {
    return http.post('/migration/batch', payload)
  },

  listHistory(limit: number = 50): Promise<{ total: number; history: any[] }> {
    return http.get('/migration/history/list', { params: { limit } })
  },

  getMigration(migrationId: string): Promise<{ migration: ActionMappingResultDTO }> {
    return http.get(`/migration/${migrationId}`)
  },

  analyzeParity(payload: {
    screen_name: string
    source_platform?: string
    target_platform?: string
    source_elements: any[]
    target_elements: any[]
  }): Promise<{ message: string; report: ParityAuditReportDTO }> {
    return http.post('/migration/parity/analyze', payload)
  },

  listParityReports(limit: number = 50): Promise<{ total: number; reports: ParityAuditReportDTO[] }> {
    return http.get('/migration/parity/reports', { params: { limit } })
  },

  getParityReport(reportId: string): Promise<{ report: ParityAuditReportDTO }> {
    return http.get(`/migration/parity/report/${reportId}`)
  },
}
