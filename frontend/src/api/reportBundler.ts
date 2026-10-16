import http from './http'

export type ReportExportFormat = 'html5' | 'excel_detailed' | 'pdf_summary' | 'multi_modal_zip'

export interface ExportReportBundleRequest {
  run_id: number
  title: string
  project_name: string
  environment_name: string
  total_cases: number
  passed_cases: number
  failed_cases: number
  pass_rate_pct: number
  duration_sec: number
  format?: ReportExportFormat
  executed_by?: string
  cases_summary?: Array<Record<string, any>>
  digital_seal_signature?: string | null
  quality_score?: number | null
  healed_cases_count?: number
  perf_summary?: Record<string, any> | null
}

export interface ExportArtifactItem {
  bundle_id: string
  run_id: number
  format: ReportExportFormat
  filename: string
  content_type: string
  file_size_bytes: number
  created_at: string
  download_url?: string
}

export const reportBundlerApi = {
  exportBundle(data: ExportReportBundleRequest): Promise<{ message: string; artifact: ExportArtifactItem }> {
    return http.post('/reporting/exports/bundle', data)
  },

  listArtifacts(): Promise<{ total: number; artifacts: ExportArtifactItem[] }> {
    return http.get('/reporting/exports/artifacts')
  },

  getDownloadUrl(bundleId: string): string {
    return `/api/v1/reporting/exports/download/${bundleId}`
  },
}
