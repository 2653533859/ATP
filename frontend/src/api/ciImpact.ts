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
}
