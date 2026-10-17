import http from './http'

export interface ChangedSymbolItem {
  symbol_id: string
  file_path: string
  symbol_name: string
  qualified_name: string
  symbol_type: string
  change_type: string
  severity: string
  line_start: number
  line_end: number
  touched_lines: number[]
  signature: string
}

export interface DiffSymbolExtractionReport {
  report_id: string
  total_files_analyzed: number
  changed_symbols_count: number
  symbols: ChangedSymbolItem[]
  analyzed_at: string
}

export interface ImpactedCaseItem {
  case_id: string
  case_name: string
  impacted_by_endpoints: string[]
  impacted_by_symbols: string[]
  call_lineage: string[]
  execution_cost_seconds: number
  priority: string
}

export interface PrecisionImpactAnalysisResult {
  analysis_id: string
  changed_symbols: string[]
  impacted_endpoints_count: number
  impacted_endpoints: string[]
  impacted_cases_count: number
  impacted_cases: ImpactedCaseItem[]
  total_cases_in_suite: number
  regression_reduction_ratio: number
  estimated_time_saved_seconds: number
  analyzed_at: string
}

export const precisionRegressionApi = {
  analyzeDiff(data: { diff_text: string; source_files: Record<string, string> }): Promise<{
    message: string
    report: DiffSymbolExtractionReport
  }> {
    return http.post('/precision-regression/diff/analyze', data)
  },

  recommendCases(data: { changed_symbols: string[]; total_suite_size?: number }): Promise<{
    message: string
    result: PrecisionImpactAnalysisResult
  }> {
    return http.post('/precision-regression/recommend', data)
  },

  analyzeAndRecommend(data: {
    diff_text: string
    source_files: Record<string, string>
    total_suite_size?: number
  }): Promise<{
    message: string
    diff_symbol_report: DiffSymbolExtractionReport
    precision_recommendation: PrecisionImpactAnalysisResult
  }> {
    return http.post('/precision-regression/analyze-and-recommend', data)
  },

  getCaseCoverage(caseId: string): Promise<{ coverage: any }> {
    return http.get(`/precision-regression/coverage/${caseId}`)
  },

  registerLineage(data: {
    symbol_name: string
    endpoint: string
    case_id?: string
    case_name?: string
    cost_seconds?: number
    priority?: string
  }): Promise<{ message: string }> {
    return http.post('/precision-regression/lineage/register', data)
  },
}
