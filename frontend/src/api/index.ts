import http from './http'

export type CasePriority = 'P0' | 'P1' | 'P2' | 'P3'
export type CaseLevel = 'smoke' | 'core' | 'regression' | 'extended'
export type ReviewStatus = 'pending' | 'approved' | 'rejected'
export type AutomationStatus = 'manual' | 'semi_auto' | 'auto'
export type CaseStatus = 'draft' | 'active' | 'deprecated'
export type CaseType = 'api' | 'graphql' | 'websocket' | 'grpc' | 'web' | 'android'
export type SuiteStatus = 'active' | 'archived'
export type SuiteRunStatus = 'pending' | 'running' | 'passed' | 'failed' | 'error'
export type PlanStatus = 'draft' | 'active' | 'archived'
export type ScheduleType = 'manual' | 'cron' | 'webhook'
export type TriggerType = 'manual' | 'cron' | 'webhook'
export type PlanRunStatus = 'pending' | 'running' | 'passed' | 'failed' | 'error'

export interface ProjectItem {
  id: number
  name: string
  project_code?: string | null
  description?: string | null
  owner_id: number
  created_at: string
  updated_at: string
}

export interface EnvironmentItem {
  id: number
  name: string
  description?: string | null
  project_id: number
  created_at?: string
  updated_at?: string
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

export interface SuiteCaseRef {
  case_id: number
  sort: number
}

export interface SuiteItem {
  id: number
  name: string
  description?: string | null
  project_id: number
  status: SuiteStatus
  creator_id: number
  case_ids: SuiteCaseRef[]
  parameterization?: Record<string, unknown> | null
  config: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface SuiteSavePayload {
  name: string
  description?: string | null
  project_id?: number
  case_ids: SuiteCaseRef[]
  parameterization?: Record<string, unknown> | null
  config?: Record<string, unknown>
}

export interface SuiteRunCaseItem {
  case_id: number
  case_name?: string
  run_id?: number | null
  status: SuiteRunStatus | string
  error?: string
}

export interface SuiteRunSummary {
  total?: number
  passed?: number
  failed?: number
  error?: number
  skipped?: number
  [key: string]: unknown
}

export interface SuiteRunItem {
  id: number
  suite_id: number
  triggered_by: number
  status: SuiteRunStatus
  environment?: string | null
  duration_ms?: number | null
  error_message?: string | null
  result_summary: SuiteRunSummary
  case_run_ids: SuiteRunCaseItem[]
  created_at: string
}

export interface PlanSuiteRef {
  suite_id: number
  sort: number
}

export interface PlanItem {
  id: number
  name: string
  description?: string | null
  project_id: number
  status: PlanStatus
  creator_id: number
  suite_ids: PlanSuiteRef[]
  schedule_type: ScheduleType
  cron_expression?: string | null
  webhook_secret?: string | null
  is_enabled: boolean
  auto_create_bugs: boolean
  env_id?: number | null
  last_run_at?: string | null
  next_run_at?: string | null
  created_at: string
  updated_at: string
}

export interface PlanSavePayload {
  name: string
  description?: string | null
  project_id?: number
  suite_ids: PlanSuiteRef[]
  schedule_type: ScheduleType
  cron_expression?: string | null
  is_enabled: boolean
  auto_create_bugs?: boolean
  env_id?: number | null
}

export interface PlanRunAutoBugItem {
  case_id: number
  bug_id: string
  bug_url?: string
  duplicate?: boolean
  attachment_uploaded?: boolean
}

export interface PlanRunSummary {
  total?: number
  passed?: number
  failed?: number
  error?: number
  auto_bugs?: PlanRunAutoBugItem[]
  auto_bugs_error?: string
  [key: string]: unknown
}

export interface PlanRunItem {
  id: number
  plan_id: number
  triggered_by?: number | null
  trigger_type: TriggerType
  status: PlanRunStatus
  duration_ms?: number | null
  error_message?: string | null
  suite_run_ids: Array<Record<string, unknown>>
  result_summary: PlanRunSummary
  created_at: string
}

export interface StatisticsExecutorTopItem {
  user_id: number | null
  username: string
  run_count: number
}

export interface StatisticsTriggerTypeStatItem {
  trigger_type: TriggerType
  count: number
}

export interface StatisticsAggregateTrendItem {
  date: string
  total: number
  passed: number
  rate: number
}

export interface MockRuleItem {
  id: number
  name: string
  project_id: number
  method: string
  path: string
  status_code: number
  response_headers: Record<string, string>
  response_body: string | null
  match_conditions: Record<string, Record<string, string>>
  delay_ms: number
  is_enabled: boolean
  render_template: boolean
  record_requests: boolean
  version: number
  recorded_samples: Array<Record<string, unknown>>
  creator_id: number
  created_at: string
  updated_at: string
}

export type BugTrackerType = 'jira' | 'zentao' | 'github'

export interface BugTrackerItem {
  id: number
  name: string
  project_id: number
  tracker_type: BugTrackerType
  config: Record<string, unknown>
  field_mapping: Record<string, unknown>
  is_enabled: boolean
  created_at: string
  updated_at: string
}

export interface BugLinkInfo {
  bug_id: string
  bug_url: string
  title: string
  duplicate_of?: string | null
  attachment_uploaded?: boolean
  status?: string | null
}

// ---- Mobile Special Testing ----
export type TaskType = 'performance' | 'stability' | 'fluency'
export type SourceType = 'apk_only' | 'case' | 'suite' | 'monkey'
export type DeviceScopeType = 'single_device' | 'device_group' | 'manual_pick'
export type MobileRunStatus = 'pending' | 'running' | 'completed' | 'failed' | 'stopped'
export type MobileTriggerType = 'manual' | 'schedule' | 'webhook'
export type IncidentType = 'crash' | 'anr' | 'fatal_log' | 'watchdog'
export type ArtifactType = 'csv' | 'json' | 'screenshot' | 'raw_log' | 'trace'
export type ScopeType = 'global' | 'project'

export interface MobileSpecialTaskItem {
  id: number
  name: string
  project_id: number
  task_type: TaskType
  source_type: SourceType
  source_id?: number | null
  device_scope_type: DeviceScopeType
  device_id?: number | null
  device_group_tag?: string | null
  apk_id?: number | null
  app_package?: string | null
  config_json: Record<string, unknown>
  schedule_enabled: boolean
  cron_expression?: string | null
  last_run_at?: string | null
  next_run_at?: string | null
  created_by?: number | null
  updated_by?: number | null
  created_at: string
  updated_at: string
}

export interface MobileSpecialRunItem {
  id: number
  task_id: number
  task_type: TaskType
  status: MobileRunStatus
  device_id?: number | null
  device_serial?: string | null
  apk_id?: number | null
  app_package?: string | null
  started_at?: string | null
  finished_at?: string | null
  duration_ms?: number | null
  summary_json: Record<string, unknown>
  config_snapshot: Record<string, unknown>
  trigger_type: MobileTriggerType
  triggered_by?: number | null
  created_at: string
  updated_at: string
}

export interface MobileMetricSampleItem {
  id: number
  run_id: number
  sample_time: string
  metric_type: string
  metric_value: number
  source?: string | null
  extra_json: Record<string, unknown>
}

export interface MobileIncidentItem {
  id: number
  run_id: number
  incident_type: IncidentType
  event_time: string
  title?: string | null
  detail?: string | null
  process_name?: string | null
  thread_name?: string | null
  artifact_path?: string | null
}

export interface MobileRunArtifactItem {
  id: number
  run_id: number
  artifact_type: ArtifactType
  file_path: string
  file_name: string
  file_size?: number | null
  created_at: string
}

export interface GlobalVariableItem {
  id: number
  scope_type: ScopeType
  project_id?: number | null
  key: string
  value: string
  is_secret: boolean
  description?: string | null
  created_at: string
  updated_at: string
}

export interface RunStepItem {
  step_index: number
  name: string
  status: string
  duration_ms: number | null
  request_data: Record<string, unknown> | null
  response_data: Record<string, unknown> | null
  error_message: string | null
  screenshot_url: string | null
}

export interface RunDetailItem {
  id: number
  case_id: number
  status: string
  environment?: string | null
  duration_ms?: number | null
  error_message?: string | null
  result_summary: Record<string, unknown>
  created_at: string
  steps: RunStepItem[]
  case_name?: string
  project_id?: number
  case?: { name?: string }
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
  get: (id: number) => http.get<any, RunDetailItem>(`/runs/${id}`),
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
    http.get<any, EnvironmentItem[]>('/environments', { params: { project_id: projectId } }),
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
    http.get<any, SuiteItem[]>('/suites', { params }),
  get: (id: number) => http.get<any, SuiteItem>('/suites/' + id),
  create: (data: SuiteSavePayload) => http.post<any, SuiteItem>('/suites', data),
  update: (id: number, data: SuiteSavePayload) => http.patch<any, SuiteItem>(`/suites/${id}`, data),
  delete: (id: number) => http.delete(`/suites/${id}`),
  run: (id: number, data?: { env_id?: number; extra_vars?: object }) =>
    http.post<any, SuiteRunItem>(`/suites/${id}/run`, data ?? {}),
  listRuns: (params?: { suite_id?: number }) =>
    http.get<any, SuiteRunItem[]>('/suite-runs', { params }),
  getRun: (id: number) => http.get<any, SuiteRunItem>('/suite-runs/' + id),
  exportRunHtml: (id: number) =>
    http.get<any, Blob>(`/suite-runs/${id}/export/html`, { responseType: 'blob' }),
  exportRunPdf: (id: number) =>
    http.get<any, Blob>(`/suite-runs/${id}/export/pdf`, { responseType: 'blob' }),
}

export const planApi = {
  list: (params?: { project_id?: number }) =>
    http.get<any, PlanItem[]>('/plans', { params }),
  get: (id: number) => http.get<any, PlanItem>('/plans/' + id),
  create: (data: PlanSavePayload) => http.post<any, PlanItem>('/plans', data),
  update: (id: number, data: PlanSavePayload) => http.patch<any, PlanItem>(`/plans/${id}`, data),
  delete: (id: number) => http.delete(`/plans/${id}`),
  run: (id: number, data?: { env_id?: number; extra_vars?: object }) =>
    http.post<any, PlanRunItem>(`/plans/${id}/run`, data ?? {}),
  listRuns: (params?: { plan_id?: number }) =>
    http.get<any, PlanRunItem[]>('/plan-runs', { params }),
  getRun: (id: number) => http.get<any, PlanRunItem>('/plan-runs/' + id),
  exportRunHtml: (id: number) =>
    http.get<any, Blob>(`/plan-runs/${id}/export/html`, { responseType: 'blob' }),
  exportRunPdf: (id: number) =>
    http.get<any, Blob>(`/plan-runs/${id}/export/pdf`, { responseType: 'blob' }),
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
  failureTop: (params?: { project_id?: number; days?: number; top?: number; case_type?: string }) =>
    http.get<any, Array<{ case_id: number; project_id: number; module_id: number; case_name: string; case_type: string; failure_count: number }>>(
      '/statistics/failure-top', { params },
    ),
  executorTop: (params?: { project_id?: number; days?: number; top?: number; case_type?: string }) =>
    http.get<any, StatisticsExecutorTopItem[]>('/statistics/executor-top', { params }),
  triggerTypeStats: (params?: { project_id?: number; days?: number }) =>
    http.get<any, StatisticsTriggerTypeStatItem[]>('/statistics/trigger-type-stats', { params }),
  planTrend: (params?: { project_id?: number; days?: number }) =>
    http.get<any, StatisticsAggregateTrendItem[]>('/statistics/plan-trend', { params }),
  suiteTrend: (params?: { project_id?: number; days?: number }) =>
    http.get<any, StatisticsAggregateTrendItem[]>('/statistics/suite-trend', { params }),
}

export const mockRuleApi = {
  list: (params?: { project_id?: number }) =>
    http.get<any, MockRuleItem[]>('/mock-rules', { params }),
  get: (id: number) => http.get<any, MockRuleItem>('/mock-rules/' + id),
  create: (data: object) => http.post<any, MockRuleItem>('/mock-rules', data),
  update: (id: number, data: object) => http.patch<any, MockRuleItem>(`/mock-rules/${id}`, data),
  delete: (id: number) => http.delete(`/mock-rules/${id}`),
  logs: (projectId: number) => http.get<any, any[]>(`/mock-rules/logs/${projectId}`),
  exportRules: (projectId: number) => http.get<any, { project_id: number; rules: MockRuleItem[] }>(`/mock-rules/export/${projectId}`),
  importRules: (data: { project_id: number; rules: any[] }) => http.post<any, MockRuleItem[]>('/mock-rules/import', data),
}

export const bugTrackerApi = {
  list: (params?: { project_id?: number }) =>
    http.get<any, BugTrackerItem[]>('/bug-trackers', { params }),
  get: (id: number) => http.get<any, BugTrackerItem>('/bug-trackers/' + id),
  create: (data: object) => http.post<any, BugTrackerItem>('/bug-trackers', data),
  update: (id: number, data: object) => http.patch<any, BugTrackerItem>(`/bug-trackers/${id}`, data),
  delete: (id: number) => http.delete(`/bug-trackers/${id}`),
  testConnection: (data: { tracker_id?: number; tracker_type: BugTrackerType; config: object }) =>
    http.post<any, { ok: boolean; message: string }>('/bug-trackers/test-connection', data),
  getBugStatus: (runId: number) =>
    http.get<any, { bug_id: string; status: string; bug_url?: string }>(`/runs/${runId}/bug-status`),
  createBug: (runId: number, data: { tracker_id: number; step_index?: number }) =>
    http.post<any, { bug_id: string; bug_url: string; title: string; duplicate_of?: string | null; attachment_uploaded?: boolean }>(`/runs/${runId}/create-bug`, data),
}

// ---- Mobile Special Testing ----
export const mobileSpecialApi = {
  // Tasks
  listTasks: (params?: { project_id?: number; task_type?: TaskType }) =>
    http.get<any, MobileSpecialTaskItem[]>('/mobile-special/tasks', { params }),
  getTask: (id: number) => http.get<any, MobileSpecialTaskItem>(`/mobile-special/tasks/${id}`),
  createTask: (data: object) => http.post<any, MobileSpecialTaskItem>('/mobile-special/tasks', data),
  updateTask: (id: number, data: object) => http.patch<any, MobileSpecialTaskItem>(`/mobile-special/tasks/${id}`, data),
  deleteTask: (id: number) => http.delete(`/mobile-special/tasks/${id}`),
  triggerTask: (id: number, data?: { device_id?: number; app_package?: string }) =>
    http.post<any, MobileSpecialRunItem>(`/mobile-special/tasks/${id}/run`, data ?? {}),
  // Runs
  listRuns: (params?: { task_id?: number; task_type?: TaskType; status_filter?: MobileRunStatus; project_id?: number; limit?: number; offset?: number }) =>
    http.get<any, MobileSpecialRunItem[]>('/mobile-special/runs', { params }),
  getRun: (id: number) => http.get<any, MobileSpecialRunItem>(`/mobile-special/runs/${id}`),
  getRunSummary: (id: number) => http.get<any, Record<string, unknown>>(`/mobile-special/runs/${id}/summary`),
  getRunSamples: (id: number, params?: { metric_type?: string; limit?: number }) =>
    http.get<any, MobileMetricSampleItem[]>(`/mobile-special/runs/${id}/samples`, { params }),
  getRunIncidents: (id: number) =>
    http.get<any, MobileIncidentItem[]>(`/mobile-special/runs/${id}/incidents`),
  getRunArtifacts: (id: number) =>
    http.get<any, MobileRunArtifactItem[]>(`/mobile-special/runs/${id}/artifacts`),
  stopRun: (id: number) => http.post<any, MobileSpecialRunItem>(`/mobile-special/runs/${id}/stop`),
  // Export
  exportRunCsv: (runId: number) =>
    http.get<any, Blob>(`/mobile-special/runs/${runId}/export/csv`, { responseType: 'blob' }),
  exportRunJson: (runId: number) =>
    http.get<any, Blob>(`/mobile-special/runs/${runId}/export/json`, { responseType: 'blob' }),
  // Statistics
  getOverview: (params?: { project_id?: number; days?: number }) =>
    http.get<any, { total_runs: number; completed_runs: number; failed_runs: number; running_runs: number; pass_rate: number; avg_duration_ms: number | null; total_incidents: number; recent_runs_7d: number }>('/mobile-special/statistics/overview', { params }),
  getTrend: (params?: { project_id?: number; days?: number }) =>
    http.get<any, Array<{ date: string; total: number; completed: number; failed: number; pass_rate: number }>>('/mobile-special/statistics/trend', { params }),
  getTaskStats: (params?: { project_id?: number; days?: number; limit?: number }) =>
    http.get<any, Array<{ task_id: number; task_name: string; task_type: string; total_runs: number; completed_runs: number; failed_runs: number; pass_rate: number; last_run_at: string | null }>>('/mobile-special/statistics/task-stats', { params }),
}

// ---- Global Variables ----
export const globalVariableApi = {
  list: (params?: { project_id?: number; scope_type?: ScopeType }) =>
    http.get<any, GlobalVariableItem[]>('/global-variables', { params }),
  get: (id: number, params?: { reveal_secret?: boolean }) =>
    http.get<any, GlobalVariableItem>(`/global-variables/${id}`, { params }),
  create: (data: object) => http.post<any, GlobalVariableItem>('/global-variables', data),
  update: (id: number, data: object) => http.patch<any, GlobalVariableItem>(`/global-variables/${id}`, data),
  delete: (id: number) => http.delete(`/global-variables/${id}`),
}
