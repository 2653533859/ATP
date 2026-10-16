import http from './http'

export interface ChangedSymbolItem {
  symbol_id: string
  symbol_type: string
  symbol_name: string
  file_path: string
  start_line: number
  end_line: number
  changed_lines: number[]
  change_kind: string
  parent_class?: string | null
  route_method?: string | null
  route_path?: string | null
  decorators: string[]
  parameters: string[]
}

export interface ChangedFileDiffItem {
  file_path: string
  is_new_file: boolean
  is_deleted_file: boolean
  added_lines_count: number
  deleted_lines_count: number
  changed_line_numbers: number[]
}

export interface DiffAstAnalysisReportItem {
  analysis_id: string
  diff_summary: {
    total_files_changed: number
    total_added_lines: number
    total_deleted_lines: number
    net_lines_delta: number
    affected_symbols_count: number
    affected_routes_count: number
  }
  changed_files: ChangedFileDiffItem[]
  affected_symbols: ChangedSymbolItem[]
  affected_routes: Array<{
    route_method: string
    route_path: string
    handler_function: string
    file_path: string
    symbol_id: string
    changed_lines_count: number
  }>
  analyzed_at: string
}

export interface AnalyzeDiffAstRequest {
  diff_text: string
  file_sources?: Record<string, string>
}

export interface TestCaseRefItem {
  case_id: number
  case_name: string
  case_type: string
  project_id?: number | null
  priority: string
  target_endpoints: string[]
  target_symbols: string[]
}

export interface MappingStats {
  total_indexed_cases: number
  total_indexed_symbols: number
  total_indexed_routes: number
  total_indexed_files: number
}

export interface RegisterBindingRequest {
  case_id: number
  case_name: string
  case_type?: string
  project_id?: number | null
  priority?: string
  bound_symbols?: string[]
  bound_routes?: Array<[string, string]>
}

export interface QueryAffectedCasesRequest {
  symbols?: string[]
  routes?: string[]
  file_paths?: string[]
  project_id?: number | null
}

export type SelectionStrategy = 'minimal' | 'balanced' | 'comprehensive'

export interface SelectedCaseItem {
  case_id: number
  case_name: string
  priority: string
  selection_reason: string
  confidence_score: number
  estimated_duration_sec: number
  matched_symbols: string[]
  matched_routes: string[]
}

export interface SmartTestSelectionReportItem {
  selection_id: string
  diff_analysis_id: string
  strategy: SelectionStrategy
  total_repository_cases_count: number
  selected_cases_count: number
  pruned_cases_count: number
  pruning_ratio_pct: number
  estimated_execution_time_sec: number
  estimated_time_saved_sec: number
  selected_cases: SelectedCaseItem[]
  created_at: string
}

export interface SelectTestsRequest {
  diff_text: string
  file_sources?: Record<string, string>
  strategy?: SelectionStrategy
  max_cases?: number
  project_id?: number | null
  total_repo_cases_override?: number
}

export const ciImpactApi = {
  analyzeDiffAst(data: AnalyzeDiffAstRequest): Promise<{ message: string; report: DiffAstAnalysisReportItem }> {
    return http.post('/ci-impact/diff-ast/analyze', data)
  },

  listDiffAstReports(): Promise<{ total: number; reports: DiffAstAnalysisReportItem[] }> {
    return http.get('/ci-impact/diff-ast/reports')
  },

  getDiffAstReport(analysisId: string): Promise<DiffAstAnalysisReportItem> {
    return http.get(`/ci-impact/diff-ast/reports/${analysisId}`)
  },

  bindTestCase(data: RegisterBindingRequest): Promise<{ message: string; case: TestCaseRefItem }> {
    return http.post('/ci-impact/mapping/bind', data)
  },

  queryAffectedCases(data: QueryAffectedCasesRequest): Promise<{ total: number; cases: TestCaseRefItem[] }> {
    return http.post('/ci-impact/mapping/query-affected', data)
  },

  getMappingStats(): Promise<MappingStats> {
    return http.get('/ci-impact/mapping/stats')
  },

  selectTests(data: SelectTestsRequest): Promise<{ message: string; report: SmartTestSelectionReportItem }> {
    return http.post('/ci-impact/test-selection/select', data)
  },

  listSelectionReports(): Promise<{ total: number; reports: SmartTestSelectionReportItem[] }> {
    return http.get('/ci-impact/test-selection/reports')
  },

  getSelectionReport(selectionId: string): Promise<SmartTestSelectionReportItem> {
    return http.get(`/ci-impact/test-selection/reports/${selectionId}`)
  },
}
