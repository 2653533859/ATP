import http from './http'

export type CasePriority = 'P0' | 'P1' | 'P2' | 'P3'
export type CaseLevel = 'smoke' | 'core' | 'regression' | 'extended'
export type ReviewStatus = 'pending' | 'approved' | 'rejected'
export type AutomationStatus = 'manual' | 'semi_auto' | 'auto'
export type CaseStatus = 'draft' | 'active' | 'deprecated'
export type CaseType = 'api' | 'graphql' | 'websocket' | 'grpc' | 'web' | 'android'

export interface ProjectItem {
  id: number
  name: string
  project_code?: string | null
  description?: string | null
  owner_id: number
  created_at: string
  updated_at: string
}

export interface ModuleTreeItem {
  id: number
  name: string
  module_code?: string | null
  project_id: number
  parent_id?: number | null
  sort_order: number
  created_at: string
  children: ModuleTreeItem[]
}

export interface CaseStepItem {
  id?: number
  step_no?: number
  action: string
  test_data?: string | null
  expected_result?: string | null
  is_key_step?: boolean
  remarks?: string | null
  created_at?: string
  updated_at?: string
}

export interface CaseSummaryItem {
  id: number
  name: string
  description?: string | null
  case_code: string
  summary: string
  case_type: CaseType
  status: CaseStatus
  priority: CasePriority
  case_level: CaseLevel
  review_status: ReviewStatus
  automation_status: AutomationStatus
  tags: string[]
  module_id: number
  creator_id: number
  owner_id?: number | null
  is_ready_for_execution: boolean
  created_at: string
  updated_at: string
}

export interface CaseDetailItem extends CaseSummaryItem {
  preconditions: string[]
  postconditions: string[]
  submitted_at?: string | null
  reviewed_at?: string | null
  reviewed_by?: number | null
  review_comment?: string | null
  steps: CaseStepItem[]
  config: Record<string, unknown>
}

export interface CaseSnapshotItem {
  id: number
  case_id: number
  version: number
  name: string
  description?: string | null
  tags: string[]
  config: Record<string, unknown>
  snapshot_data: Record<string, unknown>
  updated_by: number
  updated_by_name: string
  created_at: string
}

export interface CaseQueryParams {
  project_id?: number
  module_id?: number
  case_type?: CaseType
  priority?: CasePriority
  status?: CaseStatus
  review_status?: ReviewStatus
  automation_status?: AutomationStatus
  owner_id?: number
  tag?: string
  keyword?: string
}

export interface CaseSavePayload {
  name: string
  description?: string
  summary?: string
  case_type?: CaseType
  module_id?: number
  tags?: string[]
  preconditions?: string[]
  postconditions?: string[]
  priority?: CasePriority
  case_level?: CaseLevel
  owner_id?: number | null
  automation_status?: AutomationStatus
  steps?: CaseStepItem[]
  config?: Record<string, unknown>
}

export const authApi = {
  login: (username: string, password: string) =>
    http.post<any, { access_token: string; refresh_token: string }>('/auth/login', { username, password }),

  me: () => http.get<any, { id: number; username: string; email: string; role: string }>('/auth/me'),
}

export const projectApi = {
  list: () => http.get<any, ProjectItem[]>('/projects'),
  create: (data: { name: string; description?: string; project_code?: string }) => http.post('/projects', data),
  update: (id: number, data: { name?: string; description?: string; project_code?: string }) => http.patch(`/projects/${id}`, data),
  delete: (id: number) => http.delete(`/projects/${id}`),
  getModules: (projectId: number) => http.get<any, ModuleTreeItem[]>(`/projects/${projectId}/modules`),
}

export const moduleApi = {
  create: (data: { name: string; module_code?: string; project_id: number; parent_id?: number | null; sort_order?: number }) => http.post('/modules', data),
  update: (id: number, data: { name?: string; module_code?: string; parent_id?: number | null; sort_order?: number }) => http.patch(`/modules/${id}`, data),
  delete: (id: number) => http.delete(`/modules/${id}`),
}

export const caseApi = {
  list: (params?: CaseQueryParams) =>
    http.get<any, CaseSummaryItem[]>('/cases', { params }),
  create: (data: CaseSavePayload) => http.post<any, CaseDetailItem>('/cases', data),
  get: (id: number) => http.get<any, CaseDetailItem>(`/cases/${id}`),
  update: (id: number, data: CaseSavePayload) => http.patch<any, CaseDetailItem>(`/cases/${id}`, data),
  delete: (id: number) => http.delete(`/cases/${id}`),
  copy: (id: number) => http.post<any, CaseDetailItem>(`/cases/${id}/copy`),
  submitReview: (id: number, data?: { comment?: string }) => http.post<any, CaseDetailItem>(`/cases/${id}/submit-review`, data ?? {}),
  approve: (id: number, data?: { comment?: string }) => http.post<any, CaseDetailItem>(`/cases/${id}/approve`, data ?? {}),
  reject: (id: number, data?: { comment?: string }) => http.post<any, CaseDetailItem>(`/cases/${id}/reject`, data ?? {}),
  deprecate: (id: number, data?: { comment?: string }) => http.post<any, CaseDetailItem>(`/cases/${id}/deprecate`, data ?? {}),
  reactivate: (id: number, data?: { comment?: string }) => http.post<any, CaseDetailItem>(`/cases/${id}/reactivate`, data ?? {}),
  run: (id: number, data?: { env_id?: number; extra_vars?: object }) =>
    http.post(`/cases/${id}/run`, data ?? {}),
  listSnapshots: (caseId: number, params?: { page?: number; page_size?: number }) =>
    http.get<any, { items: CaseSnapshotItem[]; total: number; page: number; page_size: number }>(
      `/cases/${caseId}/snapshots`, { params },
    ),
  rollback: (caseId: number, snapshotId: number) =>
    http.post<any, CaseDetailItem>(`/cases/${caseId}/rollback/${snapshotId}`),
}

export const runApi = {
  list: (params?: { case_id?: number; page?: number; page_size?: number }) =>
    http.get<any, { items: any[]; total: number; page: number; page_size: number }>('/runs', { params }),
  get: (id: number) => http.get(`/runs/${id}`),
  exportHtml: (id: number) =>
    http.get<any, Blob>(`/runs/${id}/export/html`, { responseType: 'blob' }),
  exportPdf: (id: number) =>
    http.get<any, Blob>(`/runs/${id}/export/pdf`, { responseType: 'blob' }),
}

export const scriptApi = {
  upload: (caseId: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return http.post(`/cases/${caseId}/script`, form)
  },
  get: (caseId: number) =>
    http.get<any, { content: string; exists: boolean; script_path?: string }>(`/cases/${caseId}/script`),
  saveContent: (caseId: number, content: string) => {
    const blob = new Blob([content], { type: 'text/x-python' })
    const file = new File([blob], 'test_case.py', { type: 'text/x-python' })
    const form = new FormData()
    form.append('file', file)
    return http.post(`/cases/${caseId}/script`, form)
  },
  delete: (caseId: number) => http.delete(`/cases/${caseId}/script`),
}

export const environmentApi = {
  list: (projectId: number) =>
    http.get<any, any[]>('/environments', { params: { project_id: projectId } }),
  create: (data: { name: string; description?: string; project_id: number }) =>
    http.post('/environments', data),
  update: (id: number, data: { name?: string; description?: string }) =>
    http.patch(`/environments/${id}`, data),
  delete: (id: number) => http.delete(`/environments/${id}`),
  getVariables: (id: number) => http.get<any, any[]>(`/environments/${id}/variables`),
  saveVariables: (id: number, data: { variables: Array<{ key: string; value: string; is_secret: boolean }> }) =>
    http.put(`/environments/${id}/variables`, data),
}

export const deviceApi = {
  list: (params?: { status_filter?: string }) =>
    http.get<any, any[]>('/devices', { params }),
  scan: () => http.post<any, any[]>('/devices/scan'),
  get: (id: number) => http.get('/devices/' + id),
  update: (id: number, data: { name?: string; description?: string }) =>
    http.patch(`/devices/${id}`, data),
  delete: (id: number) => http.delete(`/devices/${id}`),
  screenshot: (id: number) =>
    http.get<any, Blob>(`/devices/${id}/screenshot`, { responseType: 'blob' }),
  screenshotUrl: (id: number) => `/api/v1/devices/${id}/screenshot`,
  screenStreamUrl: (id: number, fps?: number) =>
    `/api/v1/devices/${id}/screen${fps ? `?fps=${fps}` : ''}`,
}

export const apkApi = {
  list: (params?: { project_id?: number }) =>
    http.get<any, any[]>('/apks', { params }),
  get: (id: number) => http.get('/apks/' + id),
  upload: (data: FormData) => http.post('/apks', data),
  update: (id: number, data: { description?: string; package_name?: string; version_name?: string; version_code?: number }) =>
    http.patch(`/apks/${id}`, data),
  delete: (id: number) => http.delete(`/apks/${id}`),
  download: (id: number) =>
    http.get<any, { url: string; filename: string }>(`/apks/${id}/download`),
}

export const suiteApi = {
  list: (params?: { project_id?: number }) =>
    http.get<any, any[]>('/suites', { params }),
  get: (id: number) => http.get('/suites/' + id),
  create: (data: object) => http.post('/suites', data),
  update: (id: number, data: object) => http.patch(`/suites/${id}`, data),
  delete: (id: number) => http.delete(`/suites/${id}`),
  run: (id: number, data?: { env_id?: number; extra_vars?: object }) =>
    http.post(`/suites/${id}/run`, data ?? {}),
  listRuns: (params?: { suite_id?: number }) =>
    http.get<any, any[]>('/suite-runs', { params }),
  getRun: (id: number) => http.get('/suite-runs/' + id),
}

export const planApi = {
  list: (params?: { project_id?: number }) =>
    http.get<any, any[]>('/plans', { params }),
  get: (id: number) => http.get('/plans/' + id),
  create: (data: object) => http.post('/plans', data),
  update: (id: number, data: object) => http.patch(`/plans/${id}`, data),
  delete: (id: number) => http.delete(`/plans/${id}`),
  run: (id: number, data?: { env_id?: number; extra_vars?: object }) =>
    http.post(`/plans/${id}/run`, data ?? {}),
  listRuns: (params?: { plan_id?: number }) =>
    http.get<any, any[]>('/plan-runs', { params }),
  getRun: (id: number) => http.get('/plan-runs/' + id),
}

export const notificationApi = {
  list: (params?: { project_id?: number }) =>
    http.get<any, any[]>('/notifications', { params }),
  get: (id: number) => http.get('/notifications/' + id),
  create: (data: object) => http.post('/notifications', data),
  update: (id: number, data: object) => http.patch(`/notifications/${id}`, data),
  delete: (id: number) => http.delete(`/notifications/${id}`),
  test: (id: number) => http.post(`/notifications/${id}/test`),
}

export const statisticsApi = {
  overview: (params?: { project_id?: number; days?: number }) =>
    http.get<any, { total_cases: number; total_runs: number; pass_rate: number; recent_runs_7d: number }>(
      '/statistics/overview', { params },
    ),
  passRateTrend: (params?: { project_id?: number; days?: number; case_type?: string }) =>
    http.get<any, Array<{ date: string; total: number; passed: number; rate: number }>>(
      '/statistics/pass-rate-trend', { params },
    ),
  durationTrend: (params?: { project_id?: number; days?: number; case_type?: string }) =>
    http.get<any, Array<{ date: string; avg_duration_ms: number; max_duration_ms: number; run_count: number }>>(
      '/statistics/duration-trend', { params },
    ),
  failureTop: (params?: { project_id?: number; days?: number; top?: number }) =>
    http.get<any, Array<{ case_id: number; project_id: number; module_id: number; case_name: string; case_type: string; failure_count: number }>>(
      '/statistics/failure-top', { params },
    ),
}

export const mockRuleApi = {
  list: (params?: { project_id?: number }) =>
    http.get<any, any[]>('/mock-rules', { params }),
  get: (id: number) => http.get('/mock-rules/' + id),
  create: (data: object) => http.post('/mock-rules', data),
  update: (id: number, data: object) => http.patch(`/mock-rules/${id}`, data),
  delete: (id: number) => http.delete(`/mock-rules/${id}`),
  logs: (projectId: number) => http.get<any, any[]>(`/mock-rules/logs/${projectId}`),
}

export const bugTrackerApi = {
  list: (params?: { project_id?: number }) =>
    http.get<any, any[]>('/bug-trackers', { params }),
  get: (id: number) => http.get('/bug-trackers/' + id),
  create: (data: object) => http.post('/bug-trackers', data),
  update: (id: number, data: object) => http.patch(`/bug-trackers/${id}`, data),
  delete: (id: number) => http.delete(`/bug-trackers/${id}`),
  createBug: (runId: number, data: { tracker_id: number; step_index?: number }) =>
    http.post<any, { bug_id: string; bug_url: string; title: string }>(`/runs/${runId}/create-bug`, data),
}
