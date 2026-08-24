import http from './http'

export type CasePriority = 'P0' | 'P1' | 'P2' | 'P3'
export type CaseLevel = 'smoke' | 'core' | 'regression' | 'extended'
export type ReviewStatus = 'pending' | 'approved' | 'rejected'
export type AutomationStatus = 'manual' | 'semi_auto' | 'auto'
export type CaseStatus = 'draft' | 'active' | 'deprecated'
export type ScriptStatus = 'generated' | 'missing' | 'not_applicable'
export type CaseType = 'api' | 'graphql' | 'websocket' | 'grpc' | 'web' | 'android' | 'ios'
export type SuiteStatus = 'active' | 'archived'
export type SuiteRunStatus = 'pending' | 'running' | 'passed' | 'failed' | 'error'
export type SuiteExecutionMode = 'sequential' | 'parallel'
export type SuiteFailStrategy = 'fast-fail' | 'continue' | 'require-minimum-pass-rate'
export type PlanStatus = 'draft' | 'active' | 'archived'
export type ScheduleType = 'manual' | 'cron' | 'webhook'
export type TriggerType = 'manual' | 'cron' | 'webhook'
export type PlanRunStatus = 'pending' | 'running' | 'passed' | 'failed' | 'error'
export type ProjectStatus = 'active' | 'archived'
export type ProjectTemplate = 'blank' | 'api' | 'web' | 'android' | 'full'

export interface ProjectExportPayload {
  format_version: '1'
  exported_at: string
  project: {
    name: string
    project_code?: string | null
    description?: string | null
    run_retention_days_override?: number | null
    ai_model?: {
      name: string
      provider: string
      model_name: string
      supports_vision: boolean
    } | null
  }
  modules: Array<{
    id: number
    name: string
    module_code?: string | null
    parent_id?: number | null
    sort_order: number
  }>
  environments: Array<{
    name: string
    description?: string | null
    variables: Array<{ key: string; value?: string | null; is_secret: boolean; redacted: boolean }>
  }>
  datasets: Array<{
    name: string
    description?: string | null
    format: 'csv' | 'json'
    rows: Array<Record<string, unknown>>
    schema_fields: Array<Record<string, unknown>>
    validation_policy: 'soft' | 'hard'
  }>
  warnings: string[]
}

export interface ProjectImportPreview {
  valid: boolean
  conflicts: string[]
  warnings: string[]
  project_name: string
  project_code?: string | null
  summary: Record<string, number>
}

export interface ProjectItem {
  id: number
  name: string
  project_code?: string | null
  description?: string | null
  ai_llm_config_id?: number | null
  owner_id: number
  status: ProjectStatus
  current_user_role?: ProjectRoleType | null
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

export type ConfigurationSnapshotDomain =
  | 'environment'
  | 'global_variable'
  | 'ai_llm'
  | 'storage_policy'
  | 'notification'
  | 'performance_node'

export interface ConfigurationEntryItem {
  domain: string
  resource_id?: number | null
  project_id?: number | null
  name: string
  status: string
  updated_at?: string | null
  summary: Record<string, unknown>
  route: string
  can_manage: boolean
}

export interface ConfigurationSectionItem {
  key: string
  title: string
  description: string
  route: string
  project_scoped: boolean
  readonly: boolean
  available: boolean
  count: number
  entries: ConfigurationEntryItem[]
}

export interface ConfigurationCenterOverview {
  checked_at: string
  project_id?: number | null
  sections: ConfigurationSectionItem[]
}

export interface ConfigurationRevisionItem {
  id: number
  domain: string
  resource_id: number
  project_id?: number | null
  resource_name: string
  fingerprint: string
  reason?: string | null
  redacted_payload: Record<string, unknown>
  created_by?: number | null
  created_at: string
  updated_at: string
}

export interface ConfigurationRevisionDiffChange {
  path: string
  change_type: 'added' | 'removed' | 'changed'
  changed: boolean
  sensitive: boolean
  before?: unknown
  after?: unknown
}

export interface ConfigurationRevisionImpact {
  code: string
  title: string
  description: string
  severity: 'high' | 'medium' | 'low'
  affected_features: string[]
}

export interface ConfigurationRevisionDiff {
  revision_id: number
  domain: string
  resource_id: number
  project_id?: number | null
  resource_name: string
  historical_fingerprint: string
  current_fingerprint?: string | null
  current_available: boolean
  current_status: 'available' | 'missing'
  changed: boolean
  changed_field_count: number
  sensitive_changed_field_count: number
  truncated: boolean
  message?: string | null
  changes: ConfigurationRevisionDiffChange[]
  impacts: ConfigurationRevisionImpact[]
}

export interface ConfigurationRevisionRollbackResult {
  source_revision_id: number
  resource_id: number
  domain: string
  changed: boolean
  message: string
  revision: ConfigurationRevisionItem
}

export interface EnvVariableItem {
  id?: number
  key: string
  value: string
  is_secret: boolean
}

export type DeviceStatus = 'online' | 'offline' | 'busy'
export type DeviceScanStatus = 'queued' | 'running' | 'completed' | 'failed'

export interface DeviceItem {
  id: number
  serial: string
  name?: string | null
  model?: string | null
  brand?: string | null
  os_version?: string | null
  sdk_version?: string | null
  resolution?: string | null
  status: DeviceStatus
  ip_address?: string | null
  port?: number | null
  description?: string | null
  last_seen_at?: string | null
  created_at: string
  updated_at: string
}

export interface DeviceScanResult {
  status: DeviceScanStatus
  scan_id?: string | null
  devices: DeviceItem[]
  error?: string | null
}

export interface AndroidWorkerItem {
  worker_id: string
  status: 'online'
  queues: string[]
  capabilities: string[]
  hostname?: string | null
  pid?: number | null
  updated_at: number
  expires_at: number
}

export interface DeviceLeaseItem {
  device_id: number
  owner_id?: number | null
  owner_label: string
  acquired_at: string
  heartbeat_at: string
  expires_at: string
  lease_token?: string | null
}

export interface AndroidUiTarget {
  text?: string | null
  resourceId?: string | null
  contentDesc?: string | null
  className?: string | null
  bounds?: { left: number; top: number; right: number; bottom: number } | null
  clickable?: boolean
  enabled?: boolean
}

export interface ApkItem {
  id: number
  project_id: number
  filename: string
  package_name?: string | null
  version_name?: string | null
  version_code?: number | null
  file_size: number
  object_name: string
  description?: string | null
  uploaded_by: number
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

export interface CaseFlakyStats {
  is_flaky: boolean
  total_runs: number
  passed_runs: number
  failed_runs: number
  error_runs: number
  failure_rate: number
  window_size: number
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
  ai_generated?: boolean
  script_status?: ScriptStatus
  dataset_id?: number | null
  dataset_version?: number | null
  flaky_stats?: CaseFlakyStats
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

export interface CaseReviewQueueItem {
  id: number
  project_id: number
  project_name: string
  module_id: number
  module_name: string
  name: string
  case_code: string
  summary: string
  case_type: string
  priority: string
  case_level: string
  review_status: ReviewStatus
  automation_status: AutomationStatus
  creator_id: number
  owner_id?: number | null
  submitted_at?: string | null
  reviewed_at?: string | null
  reviewed_by?: number | null
  reviewer_name?: string | null
  review_comment?: string | null
  step_count: number
  snapshot_count: number
  latest_snapshot_version?: number | null
  created_at: string
  updated_at: string
}

export interface CaseReviewQueueResult {
  items: CaseReviewQueueItem[]
  total: number
  page: number
  page_size: number
  counts: { all: number; pending: number; approved: number; rejected: number }
}

export interface CaseReviewBatchResult {
  requested: number
  processed: number
  processed_ids: number[]
  skipped_ids: number[]
}

export interface CaseReviewHistoryItem {
  id: number
  case_id: number
  action: string
  status: string
  comment?: string | null
  reviewer_id?: number | null
  reviewer_name: string
  source: string
  snapshot_version?: number | null
  created_at: string
}

export interface ScriptUploadResponse {
  script_path: string
  size: number
}

export interface ApiRequestFileUploadResponse {
  object_name: string
  filename: string
  content_type: string
  size: number
}

export type WebRecordingStatus = 'starting' | 'recording' | 'stopping' | 'stopped' | 'error'

export interface WebRecordingStep {
  action: string
  name: string
  params: Record<string, unknown>
}

export interface WebRecordingArtifact {
  kind: 'trace' | 'har' | 'report' | string
  filename: string
  content_type: string
  size: number
  url: string
}

export interface WebRecordingItem {
  id: string
  status: WebRecordingStatus
  start_url: string
  current_url?: string
  browser?: 'chromium' | 'firefox' | 'webkit'
  project_id?: number | null
  steps: WebRecordingStep[]
  asset_ids?: number[]
  console_messages?: Array<{ type: string; text: string }>
  page_errors?: Array<{ message: string }>
  network_events?: Array<Record<string, unknown>>
  failed_requests?: Array<Record<string, unknown>>
  error_responses?: Array<Record<string, unknown>>
  artifacts?: Record<string, WebRecordingArtifact>
  artifact_error?: string | null
  error?: string | null
}

export interface WebRecordingWorkerStatus {
  worker_id: string
  active_sessions: number
  capacity: number
  available: boolean
  updated_at?: number | null
}

export interface WebRecordingWorkersResponse {
  mode: string
  ready: boolean
  workers: WebRecordingWorkerStatus[]
  registered_count: number
  available_count: number
}

export interface CaseRunStartResponse {
  id: number
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
  dataset_id?: number | null
  dataset_version?: number | null
}

export interface CaseImportConflict {
  index: number
  module_id: number
  name: string
  reason: string
}

export interface CaseImportPreview {
  total: number
  valid_count: number
  invalid_count: number
  conflicts: CaseImportConflict[]
  errors: string[]
}

export interface CaseImportResult {
  imported: number
  skipped_count: number
  case_ids: number[]
  conflicts: CaseImportConflict[]
}

export type RequirementStatusType = 'draft' | 'active' | 'archived'
export type RequirementRelationType = 'covers' | 'validates'
export type CriterionStatusType = 'draft' | 'approved'

export interface AcceptanceCriterionItem {
  id: string
  text: string
  priority: CasePriority
  status: CriterionStatusType
}

export interface RequirementCaseLinkItem {
  id: number
  requirement_id: number
  case_id: number
  case_name: string
  case_code: string
  case_type: string
  case_status: string
  review_status: string
  module_id: number
  module_name: string
  relation_type: RequirementRelationType
  criterion_ids: string[]
  note?: string | null
  created_by?: number | null
  created_at: string
}

export interface RequirementListItem {
  id: number
  project_id: number
  requirement_code?: string | null
  title: string
  description?: string | null
  status: RequirementStatusType
  priority: CasePriority
  acceptance_criteria: AcceptanceCriterionItem[]
  source: string
  source_ref?: string | null
  version: number
  creator_id: number
  owner_id?: number | null
  linked_case_count: number
  covered_criterion_count: number
  coverage_rate: number
  created_at: string
  updated_at: string
}

export interface RequirementDetailItem extends RequirementListItem {
  links: RequirementCaseLinkItem[]
}

export interface RequirementListResult {
  items: RequirementListItem[]
  total: number
  page: number
  page_size: number
}

export interface RequirementImpactCandidateItem {
  case_id: number
  case_name: string
  case_code: string
  case_type: string
  module_id: number
  module_name: string
  match_terms: string[]
}

export interface RequirementImpactItem {
  requirement_id: number
  requirement_version: number
  criteria_total: number
  criteria_covered: number
  coverage_rate: number
  linked_case_count: number
  impact_level: 'high' | 'medium' | 'low'
  uncovered_criteria: AcceptanceCriterionItem[]
  candidate_cases: RequirementImpactCandidateItem[]
}

export interface RequirementParseResult {
  title: string
  description: string
  acceptance_criteria: AcceptanceCriterionItem[]
  keywords: string[]
  warnings: string[]
}

export interface RequirementCreatePayload {
  project_id: number
  title: string
  description?: string | null
  status?: RequirementStatusType
  priority?: CasePriority
  acceptance_criteria?: Array<Partial<AcceptanceCriterionItem> & { text: string }>
  source?: string
  source_ref?: string | null
  owner_id?: number | null
}

export interface RequirementUpdatePayload {
  title?: string
  description?: string | null
  status?: RequirementStatusType
  priority?: CasePriority
  acceptance_criteria?: Array<Partial<AcceptanceCriterionItem> & { text: string }>
  source?: string
  source_ref?: string | null
  owner_id?: number | null
}

export interface RequirementCaseLinkPayload {
  case_id: number
  relation_type?: RequirementRelationType
  criterion_ids?: string[]
  note?: string | null
}

export type KnowledgeSourceType = 'standard' | 'defect' | 'solution' | 'runbook' | 'experience' | 'requirement' | 'execution'
export type KnowledgeStatusType = 'draft' | 'published' | 'archived'

export interface KnowledgeSearchItem {
  key: string
  document_id?: number | null
  source_type: KnowledgeSourceType
  title: string
  excerpt: string
  project_id?: number | null
  project_name?: string | null
  source_ref?: string | null
  tags: string[]
  status: string
  match_terms: string[]
  match_score: number
  target_path?: string | null
  is_global: boolean
  is_editable: boolean
  updated_at: string
}

export interface KnowledgeDetailItem extends KnowledgeSearchItem {
  summary?: string | null
  content: string
  version: number
  author_id?: number | null
  created_at: string
}

export interface KnowledgeListResult {
  items: KnowledgeSearchItem[]
  total: number
  page: number
  page_size: number
  source_counts: Record<string, number>
}

export interface KnowledgeSavePayload {
  project_id?: number | null
  source_type: KnowledgeSourceType
  title: string
  summary?: string | null
  content: string
  source_ref?: string | null
  tags?: string[]
  status?: KnowledgeStatusType
}

export interface KnowledgeUpdatePayload {
  source_type?: KnowledgeSourceType
  title?: string
  summary?: string | null
  content?: string
  source_ref?: string | null
  tags?: string[]
  status?: KnowledgeStatusType
}

export interface SuiteCaseRef {
  case_id: number
  sort: number
}

export interface SuiteConfig {
  execution_mode?: SuiteExecutionMode
  max_workers?: number
  fail_strategy?: SuiteFailStrategy
  min_pass_rate?: number
  [key: string]: unknown
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
  config: SuiteConfig
  created_at: string
  updated_at: string
}

export interface SuiteSavePayload {
  name: string
  description?: string | null
  project_id?: number
  case_ids: SuiteCaseRef[]
  parameterization?: Record<string, unknown> | null
  config?: SuiteConfig
}

export interface SuiteRunCaseItem {
  case_id: number
  case_name?: string
  run_id?: number | null
  status: SuiteRunStatus | string
  error?: string
  flaky?: boolean
  flaky_failure_rate?: number
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
  trace_id?: string | null
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

export interface PlanConfig {
  execution_mode?: SuiteExecutionMode
  max_workers?: number
  fail_strategy?: SuiteFailStrategy
  min_pass_rate?: number
  [key: string]: unknown
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
  config?: PlanConfig
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
  config?: PlanConfig
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
  trace_id?: string | null
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

export interface StatisticsCaseTypeDistributionItem {
  case_type: string
  total: number
  passed: number
  failed: number
  error: number
  pass_rate: number
}

export interface ReportTrendItem {
  date: string
  total: number
  passed: number
  failed: number
  error: number
  pass_rate: number
  avg_duration_ms?: number | null
}

export interface ReportRunItem {
  id: number
  project_id: number
  case_id: number
  case_name: string
  case_type: string
  status: string
  duration_ms?: number | null
  error_message?: string | null
  created_at: string
}

export interface ReportOverviewItem {
  project_id?: number | null
  days: number
  total_cases: number
  executed_cases: number
  coverage_rate: number
  total_runs: number
  passed_runs: number
  failed_runs: number
  error_runs: number
  pass_rate: number
  avg_duration_ms?: number | null
  open_defects: number
  defect_health_rate: number
  quality_score: number
  trend: ReportTrendItem[]
  recent_runs: ReportRunItem[]
}

export interface ReportRunSnapshot {
  id: number
  project_id: number
  case_id: number
  case_name: string
  case_type: string
  status: string
  duration_ms?: number | null
  total_steps: number
  passed_steps: number
  failed_steps: number
  error_steps: number
  error_message?: string | null
  created_at: string
}

export interface ReportCompareMetric {
  key: string
  label: string
  baseline: number
  current: number
  delta: number
  unit?: string | null
}

export interface ReportCompareItem {
  project_id: number
  baseline: ReportRunSnapshot
  current: ReportRunSnapshot
  metrics: ReportCompareMetric[]
  has_regression: boolean
}

export interface RunRetentionPreview {
  cutoff: string
  retention_days: number
  plan_runs: number
  suite_runs: number
  test_runs: number
  mobile_runs: number
  estimated_objects: number
  estimated_objects_sampled: boolean
}

export interface RunRetentionExecuteResult {
  cutoff: string
  retention_days: number
  plan_runs: number
  suite_runs: number
  test_runs: number
  mobile_runs: number
  deleted_objects: number
  projects: RunRetentionProjectCleanup[]
}

export interface RunRetentionProjectCleanup {
  project_id: number
  project_name: string
  retention_days: number
  plan_runs: number
  suite_runs: number
  test_runs: number
  mobile_runs: number
  deleted_objects: number
}

export interface RunRetentionPerProjectPreview {
  global: Omit<RunRetentionPreview, 'cutoff'>
  projects: Array<{
    project_id: number
    project_name: string
    retention_days: number
    plan_runs: number
    suite_runs: number
    test_runs: number
    mobile_runs: number
    estimated_objects: number
    estimated_objects_sampled: boolean
    note?: string
  }>
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
  match_conditions: Record<string, Record<string, unknown>>
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

export interface MockAIGeneratedRule {
  name: string
  method: string
  path: string
  status_code: number
  response_headers: Record<string, string>
  response_body: string | null
  match_conditions: Record<string, Record<string, unknown>>
  delay_ms: number
  is_enabled: boolean
  render_template: boolean
  record_requests: boolean
}

export interface MockAIGenerateResult {
  project_id: number
  rules: MockAIGeneratedRule[]
  warnings: string[]
}

export type BugTrackerType = 'jira' | 'zentao' | 'github' | 'gitlab'

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
  linked_manually?: boolean
}

export type DefectStatus = 'open' | 'in_progress' | 'resolved' | 'reopened' | 'closed'
export type DefectPriority = 'P0' | 'P1' | 'P2' | 'P3'
export type DefectSeverity = 'blocker' | 'critical' | 'major' | 'minor' | 'trivial'
export type DefectRunType = 'case' | 'suite' | 'plan' | 'android' | 'performance'

export interface DefectRunLinkItem {
  id: number
  run_type: DefectRunType
  run_id: number
  case_id?: number | null
  evidence: Record<string, unknown>
  linked_by?: number | null
  created_at: string
}

export type DefectExternalSyncState = 'linked' | 'synced' | 'error'

export interface DefectExternalLinkItem {
  id: number
  defect_id: number
  tracker_id: number
  tracker_name: string
  tracker_type: BugTrackerType
  external_key: string
  external_url?: string | null
  external_title?: string | null
  external_status?: string | null
  sync_state: DefectExternalSyncState
  last_synced_at?: string | null
  last_error?: string | null
  created_by?: number | null
  created_at: string
  updated_at: string
}

export interface DefectItem {
  id: number
  project_id: number
  case_id?: number | null
  title: string
  description?: string | null
  status: DefectStatus
  priority: DefectPriority
  severity: DefectSeverity
  fingerprint?: string | null
  resolution?: string | null
  labels: string[]
  occurrence_count: number
  last_seen_at?: string | null
  creator_id?: number | null
  assignee_id?: number | null
  created_at: string
  updated_at: string
  run_links: DefectRunLinkItem[]
  external_links: DefectExternalLinkItem[]
}

export interface DefectMutationResult {
  defect: DefectItem
  created: boolean
  duplicate_of?: number | null
}

// ---- Mobile Special Testing ----
export type TaskType = 'performance' | 'stability' | 'fluency'
export type SourceType = 'apk_only' | 'case' | 'suite' | 'monkey'
export type DeviceScopeType = 'single_device' | 'device_group' | 'manual_pick'
export type MobileRunStatus = 'pending' | 'running' | 'completed' | 'failed' | 'stopped'
export type MobileTriggerType = 'manual' | 'schedule' | 'webhook'
export type IncidentType = 'crash' | 'anr' | 'fatal_log' | 'watchdog'
export type ArtifactType = 'csv' | 'json' | 'screenshot' | 'raw_log' | 'trace' | 'replay'
export type ScopeType = 'global' | 'project'
export type NotificationChannel = 'email' | 'wechat' | 'dingtalk'

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
  task_name?: string
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

export interface MobileRunEventItem {
  id: number
  run_id: number
  sequence: number
  event_time: string
  event_type: string
  phase?: string | null
  action?: string | null
  level?: string | null
  message?: string | null
  parameters_json: Record<string, unknown>
  result_json: Record<string, unknown>
  duration_ms?: number | null
}

export interface NotificationItem {
  id: number
  name: string
  channel: NotificationChannel
  config: Record<string, unknown>
  is_enabled: boolean
  updated_at?: string
}

export interface NotificationDeliveryItem {
  id: number
  project_id: number
  notification_config_id?: number | null
  notification_name: string
  channel: NotificationChannel
  status: 'sent' | 'failed'
  attempts: number
  summary: Record<string, unknown>
  error_message?: string | null
  created_at: string
}

export type MockRuleLogItem = Record<string, unknown>

export interface StoragePrefixStatItem {
  prefix: string
  object_count: number
  total_bytes: number
}

export interface StorageStatsItem {
  bucket: string
  total_object_count: number
  total_bytes: number
  prefixes: StoragePrefixStatItem[]
}

export interface StorageObjectPreviewItem {
  object_name: string
  last_modified?: string | null
  referenced_by_count: number
}

export interface StorageReferenceItem {
  reference_type: string
  record_id: number
  field_name: string
  object_name: string
  repairable: boolean
}

export interface StorageCleanupPreviewItem {
  prefixes: string[]
  retention_days: number
  scanned_object_count: number
  expired_object_count: number
  deletable_count: number
  blocked_count: number
  orphan_reference_count: number
  size_evicted_count?: number
  deletable_objects: StorageObjectPreviewItem[]
  blocked_objects: StorageObjectPreviewItem[]
  orphan_references: StorageReferenceItem[]
}

export interface StorageCleanupExecuteItem {
  requested_count: number
  deleted_count: number
  skipped_referenced_count: number
  missing_count: number
  repaired_reference_count: number
  deleted_objects: string[]
  skipped_objects: string[]
  repaired_references: StorageReferenceItem[]
}

export interface StorageDatasetReconcileItem {
  project_id: number
  dry_run: boolean
  scanned_count: number
  referenced_count: number
  orphan_count: number
  orphaned_objects: string[]
  truncated: boolean
  deleted_count: number
  errors: string[]
}

export interface StoragePolicyItem {
  id: number
  name: string
  prefix: string
  retention_days: number
  max_size_gb?: number | null
  enabled: boolean
  description?: string | null
  created_at: string
  updated_at: string
}

export interface StoragePolicyPayload {
  name?: string
  prefix?: string
  retention_days?: number
  max_size_gb?: number | null
  enabled?: boolean
  description?: string | null
}

export interface StorageAlertPayload {
  bucket: string
  total_bytes: number
  total_gb: number
  threshold_gb: number
  triggered_at: string
}

export interface StorageAlertResponse {
  alert: StorageAlertPayload | null
}

export type DashboardAlertMetric = 'pass_rate' | 'avg_duration_ms' | 'failure_count' | 'error_count' | 'total_runs'
export type DashboardAlertOperator = 'gt' | 'gte' | 'lt' | 'lte' | 'eq'

export interface DashboardAlertRuleItem {
  id: number
  name: string
  project_id: number
  metric: DashboardAlertMetric
  op: DashboardAlertOperator
  threshold: number
  window_minutes: number
  suppress_minutes: number
  notification_config_id?: number | null
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface DashboardAlertRulePayload {
  name?: string
  project_id?: number
  metric?: DashboardAlertMetric
  op?: DashboardAlertOperator
  threshold?: number
  window_minutes?: number
  suppress_minutes?: number
  notification_config_id?: number | null
  enabled?: boolean
}

export interface DashboardAlertEventItem {
  id: number
  rule_id: number
  triggered_at: string
  actual_value: number
  snoozed_until?: string | null
  created_at: string
  updated_at: string
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
  id?: number  // iter3 反馈端点需要 step_id
  healing_suggestion?: string | null
  healing_status?: string | null
  healing_at?: string | null
  healing_cache_hit?: boolean  // 仅运行时由 WS healing_suggestion 消息附带，不持久化
  healing_feedback?: 'adopted' | 'rejected' | null
  healing_feedback_at?: string | null
}

export interface RunDetailItem {
  id: number
  case_id: number
  trace_id?: string | null
  status: string
  environment?: string | null
  duration_ms?: number | null
  error_message?: string | null
  result_summary: Record<string, unknown>
  iteration_index?: number | null
  iteration_data?: Record<string, unknown> | null
  parent_run_id?: number | null
  created_at: string
  steps: RunStepItem[]
  case_name?: string
  project_id?: number
  case?: { name?: string }
}

export type WorkbenchTaskType = 'case' | 'suite' | 'plan' | 'android' | 'performance'
export type WorkbenchAction = 'retry' | 'stop'

export interface WorkbenchTodoItem {
  id: string
  kind: string
  priority: 'high' | 'medium' | 'low'
  project_id?: number | null
  project_name?: string | null
  title: string
  description?: string | null
  status: string
  created_at?: string | null
  due_at?: string | null
  path: string
  metadata: Record<string, unknown>
}

export interface WorkbenchTaskItem {
  id: string
  task_type: WorkbenchTaskType
  run_id: number
  source_id: number
  project_id?: number | null
  project_name?: string | null
  name: string
  status: string
  created_at?: string | null
  started_at?: string | null
  finished_at?: string | null
  duration_ms?: number | null
  error_message?: string | null
  detail_path: string
  can_retry: boolean
  can_stop: boolean
  metadata: Record<string, unknown>
}

export interface WorkbenchOverviewItem {
  generated_at: string
  project_id?: number | null
  counts: Record<string, number>
  todos: WorkbenchTodoItem[]
  tasks: WorkbenchTaskItem[]
  has_more_todos: boolean
  has_more_tasks: boolean
}

export interface WorkbenchTaskPage {
  generated_at: string
  project_id?: number | null
  status_filter?: string | null
  task_type?: string | null
  items: WorkbenchTaskItem[]
  total: number
  has_more: boolean
}

export interface WorkbenchTaskActionResult {
  action: WorkbenchAction
  task_type: WorkbenchTaskType
  run_id: number
  new_run_id?: number | null
  status: string
  message: string
}

export interface WorkbenchBatchActionResult {
  action: WorkbenchAction
  requested: number
  processed: number
  results: WorkbenchTaskActionResult[]
  failures: Array<{ task_type: WorkbenchTaskType; run_id: number; detail: string }>
}

export interface FailureDiagnosisResult {
  status: 'done' | 'skipped'
  source: 'llm' | 'rule' | 'rule_fallback'
  summary: string
  at: string
  failed_step_count: number
  screenshot_count: number
  repair_suggestions: Array<{
    step_index: number
    step_name: string
    suggestion_type: 'update_assertion' | 'update_request' | 'update_step' | 'investigate_environment'
    target: string
    suggested_change: string
    evidence: string
    confidence: number
  }>
  error_samples: Array<Record<string, unknown>>
}

export const authApi = {
  login: (username: string, password: string) =>
    http.post<unknown, { authenticated: boolean }>('/auth/login', { username, password }),

  logout: () => http.post<unknown, { authenticated: boolean }>('/auth/logout'),

  me: () => http.get<unknown, { id: number; username: string; email: string; role: string; is_active?: boolean }>('/auth/me'),

  updateMe: (data: {
    current_password: string
    username?: string
    email?: string
    new_password?: string
  }) => http.patch<unknown, { authenticated: boolean }>('/auth/me', data),
}

export type DependencyCheckStatus = 'ok' | 'error'
export type DependencyCheckCode = 'ok' | 'timeout' | 'unreachable' | 'bucket_missing'

export interface DependencyCheckItem {
  status: DependencyCheckStatus
  latency_ms: number
  code: DependencyCheckCode
}

export interface DependencyHealthResponse {
  status: 'ok' | 'degraded'
  checked_at: string
  dependencies: {
    postgres: DependencyCheckItem
    redis: DependencyCheckItem
    minio: DependencyCheckItem
  }
}

export const healthApi = {
  dependencies: () => http.get<unknown, DependencyHealthResponse>('/health/dependencies'),
}

export type RemoteToolboxCheckStatus = 'ok' | 'warning' | 'error'
export type RemoteToolboxCheckCategory = 'infrastructure' | 'execution'

export interface RemoteToolboxResourceItem {
  id: string
  name: string
  status: RemoteToolboxCheckStatus
  summary: string
  metadata: Record<string, unknown>
}

export interface RemoteToolboxCheckItem {
  key: string
  category: RemoteToolboxCheckCategory
  status: RemoteToolboxCheckStatus
  code: string
  latency_ms: number
  resources: RemoteToolboxResourceItem[]
}

export interface RemoteToolboxOverview {
  status: 'ok' | 'degraded' | 'error'
  checked_at: string
  checks: RemoteToolboxCheckItem[]
}

export const remoteToolboxApi = {
  overview: () => http.get<unknown, RemoteToolboxOverview>('/remote-toolbox/overview'),
}

export interface AdminUserItem {
  id: number
  username: string
  email: string
  role: 'admin' | 'engineer' | 'tester' | 'viewer'
  is_active: boolean
}

export const userApi = {
  list: (username?: string) => http.get<unknown, AdminUserItem[]>('/users', { params: { username } }),
  create: (data: {
    username: string
    email: string
    password: string
    role: AdminUserItem['role']
    is_active: boolean
  }) => http.post<unknown, AdminUserItem>('/users', data),
  update: (id: number, data: Partial<{
    username: string
    email: string
    password: string
    role: AdminUserItem['role']
    is_active: boolean
  }>) => http.patch<unknown, AdminUserItem>(`/users/${id}`, data),
}

export const projectApi = {
  list: () => http.get<unknown, ProjectItem[]>('/projects'),
  get: (id: number) => http.get<unknown, ProjectItem>(`/projects/${id}`),
  create: (data: { name: string; description?: string; project_code?: string; ai_llm_config_id?: number | null; template?: ProjectTemplate }) =>
    http.post<unknown, ProjectItem>('/projects', data),
  update: (id: number, data: { name?: string; description?: string; project_code?: string; ai_llm_config_id?: number | null }) =>
    http.patch(`/projects/${id}`, data),
  delete: (id: number) => http.delete(`/projects/${id}`),
  archive: (id: number) => http.post<unknown, ProjectItem>(`/projects/${id}/archive`),
  restore: (id: number) => http.post<unknown, ProjectItem>(`/projects/${id}/restore`),
  copy: (id: number, data: { name: string }) => http.post<unknown, ProjectItem>(`/projects/${id}/copy`, data),
  export: (id: number) => http.get<unknown, ProjectExportPayload>(`/projects/${id}/export`),
  previewImport: (data: { payload: ProjectExportPayload; conflict_policy: 'fail' | 'rename' }) =>
    http.post<unknown, ProjectImportPreview>('/projects/import/preview', data),
  importProject: (data: { payload: ProjectExportPayload; conflict_policy: 'fail' | 'rename' }) =>
    http.post<unknown, { project: ProjectItem; imported: Record<string, number>; warnings: string[] }>('/projects/import', data),
  getModules: (projectId: number) => http.get<unknown, ModuleTreeItem[]>(`/projects/${projectId}/modules`),
}

export const moduleApi = {
  create: (data: { name: string; module_code?: string; project_id: number; parent_id?: number | null; sort_order?: number }) => http.post('/modules', data),
  update: (id: number, data: { name?: string; module_code?: string; parent_id?: number | null; sort_order?: number }) => http.patch(`/modules/${id}`, data),
  delete: (id: number) => http.delete(`/modules/${id}`),
}

export const caseApi = {
  list: (params?: CaseQueryParams) =>
    http.get<unknown, CaseSummaryItem[]>('/cases', { params }),
  create: (data: CaseSavePayload) => http.post<unknown, CaseDetailItem>('/cases', data),
  previewImport: (projectId: number, cases: CaseSavePayload[]) =>
    http.post<unknown, CaseImportPreview>(`/projects/${projectId}/cases/import-preview`, { cases }),
  importCases: (projectId: number, cases: CaseSavePayload[], conflict_policy: 'fail' | 'skip' | 'replace' = 'fail') =>
    http.post<unknown, CaseImportResult>(
      `/projects/${projectId}/cases/import`, { cases, conflict_policy },
    ),
  get: (id: number) => http.get<unknown, CaseDetailItem>(`/cases/${id}`),
  update: (id: number, data: CaseSavePayload) => http.patch<unknown, CaseDetailItem>(`/cases/${id}`, data),
  uploadRequestFile: (projectId: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return http.post<unknown, ApiRequestFileUploadResponse>(`/projects/${projectId}/api-request-files`, form)
  },
  delete: (id: number) => http.delete(`/cases/${id}`),
  copy: (id: number) => http.post<unknown, CaseDetailItem>(`/cases/${id}/copy`),
  submitReview: (id: number, data?: { comment?: string }) => http.post<unknown, CaseDetailItem>(`/cases/${id}/submit-review`, data ?? {}),
  approve: (id: number, data?: { comment?: string }) => http.post<unknown, CaseDetailItem>(`/cases/${id}/approve`, data ?? {}),
  reject: (id: number, data?: { comment?: string }) => http.post<unknown, CaseDetailItem>(`/cases/${id}/reject`, data ?? {}),
  deprecate: (id: number, data?: { comment?: string }) => http.post<unknown, CaseDetailItem>(`/cases/${id}/deprecate`, data ?? {}),
  reactivate: (id: number, data?: { comment?: string }) => http.post<unknown, CaseDetailItem>(`/cases/${id}/reactivate`, data ?? {}),
  run: (id: number, data?: { env_id?: number; extra_vars?: object }) =>
    http.post<unknown, CaseRunStartResponse>(`/cases/${id}/run`, data ?? {}),
  listSnapshots: (caseId: number, params?: { page?: number; page_size?: number }) =>
    http.get<unknown, { items: CaseSnapshotItem[]; total: number; page: number; page_size: number }>(
      `/cases/${caseId}/snapshots`, { params },
    ),
  rollback: (caseId: number, snapshotId: number) =>
    http.post<unknown, CaseDetailItem>(`/cases/${caseId}/rollback/${snapshotId}`),
  diffSnapshots: (caseId: number, params: { from: number; to: number }) =>
    http.get<unknown, { from_version: number; to_version: number; changes: Record<string, { from: unknown; to: unknown }> }>(
      `/cases/${caseId}/snapshots/diff`, { params },
    ),
  batchDelete: (caseIds: number[]) =>
    http.post<unknown, { requested: number; processed: number; skipped_ids: number[] }>(
      '/cases/batch/delete',
      { case_ids: caseIds },
    ),
  batchMove: (caseIds: number[], targetModuleId: number) =>
    http.post<unknown, { requested: number; processed: number; skipped_ids: number[] }>(
      '/cases/batch/move',
      { case_ids: caseIds, target_module_id: targetModuleId },
    ),
  batchExportCsv: (caseIds: number[]) =>
    http.get<unknown, Blob>('/cases/batch/export', {
      params: { case_ids: caseIds.join(',') },
      responseType: 'blob',
    }),
  batchExportZip: (caseIds: number[]) =>
    http.get<unknown, Blob>('/cases/batch/export-zip', {
      params: { case_ids: caseIds.join(',') },
      responseType: 'blob',
    }),
  downloadImportTemplate: () =>
    http.get<unknown, Blob>('/cases/batch/import-template', {
      responseType: 'blob',
    }),
  previewImportZip: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return http.post<unknown, {
      total: number
      valid_count: number
      invalid_count: number
      preview_cases: Array<{ row: number; name: string; case_type: string; priority: string; step_count: number }>
      errors: string[]
    }>('/cases/batch/import-preview', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  batchImportZip: (file: File, targetModuleId: number) => {
    const form = new FormData()
    form.append('file', file)
    return http.post<unknown, {
      imported: number
      skipped_count: number
      target_module_id: number
      created_ids: number[]
      errors: string[]
    }>('/cases/batch/import-zip', form, {
      params: { target_module_id: targetModuleId },
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

export interface ApiContractChange {
  severity: 'breaking' | 'warning'
  location: string
  message: string
}

export interface ApiContractCompareResult {
  compatible: boolean
  breaking_changes: ApiContractChange[]
  warnings: ApiContractChange[]
  summary: string
}

export const apiContractApi = {
  compare: (projectId: number, baseline: Record<string, unknown>, current: Record<string, unknown>) =>
    http.post<unknown, ApiContractCompareResult>(`/projects/${projectId}/api-contracts/compare`, { baseline, current }),
  compareAssets: (projectId: number, baselineAssetId: number, currentAssetId: number) =>
    http.post<unknown, ApiContractCompareResult>(`/projects/${projectId}/api-contracts/compare-assets`, {
      baseline_asset_id: baselineAssetId,
      current_asset_id: currentAssetId,
  }),
}

export const caseReviewApi = {
  list: (params?: {
    project_id?: number
    module_id?: number
    review_status?: 'all' | ReviewStatus
    keyword?: string
    page?: number
    page_size?: number
  }) => http.get<unknown, CaseReviewQueueResult>('/case-reviews', { params }),
  batch: (data: { case_ids: number[]; action: 'approve' | 'reject'; comment?: string }) =>
    http.post<unknown, CaseReviewBatchResult>('/case-reviews/batch', data),
  history: (caseId: number) => http.get<unknown, CaseReviewHistoryItem[]>(`/case-reviews/${caseId}/history`),
}

export interface ApiContractAssetItem {
  id: number
  project_id: number
  name: string
  role: 'provider' | 'consumer'
  format: 'openapi' | 'swagger' | 'json_schema'
  description?: string | null
  definition: Record<string, unknown>
  version: number
  owner_id?: number | null
  created_at: string
  updated_at: string
}

export const apiContractAssetApi = {
  list: (projectId: number, role?: 'provider' | 'consumer') =>
    http.get<unknown, ApiContractAssetItem[]>(`/projects/${projectId}/api-contract-assets`, { params: { role } }),
  create: (
    projectId: number,
    body: {
      name: string
      role: 'provider' | 'consumer'
      format: 'openapi' | 'swagger' | 'json_schema'
      description?: string
      definition: Record<string, unknown>
    },
  ) => http.post<unknown, ApiContractAssetItem>(`/projects/${projectId}/api-contract-assets`, body),
  update: (id: number, body: Record<string, unknown>) =>
    http.patch<unknown, ApiContractAssetItem>(`/api-contract-assets/${id}`, body),
  delete: (id: number) => http.delete<unknown, void>(`/api-contract-assets/${id}`),
}

export interface ApiSchemaAssetItem {
  id: number
  project_id: number
  name: string
  description?: string | null
  definition: Record<string, unknown>
  version: number
  owner_id?: number | null
  created_at: string
  updated_at: string
}

export const apiSchemaAssetApi = {
  list: (projectId: number) =>
    http.get<unknown, ApiSchemaAssetItem[]>(`/projects/${projectId}/api-schema-assets`),
  create: (projectId: number, body: { name: string; description?: string; definition: Record<string, unknown> }) =>
    http.post<unknown, ApiSchemaAssetItem>(`/projects/${projectId}/api-schema-assets`, body),
  update: (id: number, body: Record<string, unknown>) =>
    http.patch<unknown, ApiSchemaAssetItem>(`/api-schema-assets/${id}`, body),
  delete: (id: number) => http.delete<unknown, void>(`/api-schema-assets/${id}`),
}

export const runApi = {
  list: (params?: { case_id?: number; page?: number; page_size?: number }) =>
    http.get<unknown, { items: RunDetailItem[]; total: number; page: number; page_size: number }>('/runs', { params }),
  get: (id: number) => http.get<unknown, RunDetailItem>(`/runs/${id}`),
  generateFailureDiagnosis: (id: number) =>
    http.post<unknown, FailureDiagnosisResult>(`/runs/${id}/failure-diagnosis`),
  exportHtml: (id: number) =>
    http.get<unknown, Blob>(`/runs/${id}/export/html`, { responseType: 'blob' }),
  exportPdf: (id: number) =>
    http.get<unknown, Blob>(`/runs/${id}/export/pdf`, { responseType: 'blob' }),
  submitHealingFeedback: (runId: number, stepId: number, action: 'adopted' | 'rejected') =>
    http.post<unknown, void>(`/runs/${runId}/steps/${stepId}/healing/feedback`, { action }),
}

export const workbenchApi = {
  overview: (params?: { project_id?: number; todo_limit?: number; task_limit?: number }) =>
    http.get<unknown, WorkbenchOverviewItem>('/workbench/overview', { params }),
  tasks: (params?: { project_id?: number; status?: string; task_type?: WorkbenchTaskType; limit?: number }) =>
    http.get<unknown, WorkbenchTaskPage>('/workbench/tasks', { params }),
  retry: (taskType: WorkbenchTaskType, runId: number) =>
    http.post<unknown, WorkbenchTaskActionResult>(`/workbench/tasks/${taskType}/${runId}/retry`),
  stop: (taskType: WorkbenchTaskType, runId: number) =>
    http.post<unknown, WorkbenchTaskActionResult>(`/workbench/tasks/${taskType}/${runId}/stop`),
  batchAction: (action: WorkbenchAction, tasks: Array<{ task_type: WorkbenchTaskType; run_id: number }>) =>
    http.post<unknown, WorkbenchBatchActionResult>('/workbench/tasks/batch-action', { action, tasks }),
}

export const scriptApi = {
  upload: (caseId: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return http.post<unknown, ScriptUploadResponse>(`/cases/${caseId}/script`, form)
  },
  get: (caseId: number) =>
    http.get<unknown, { content: string; exists: boolean; script_path?: string }>(`/cases/${caseId}/script`),
  saveContent: (caseId: number, content: string) => {
    const blob = new Blob([content], { type: 'text/x-python' })
    const file = new File([blob], 'test_case.py', { type: 'text/x-python' })
    const form = new FormData()
    form.append('file', file)
    return http.post<unknown, ScriptUploadResponse>(`/cases/${caseId}/script`, form)
  },
  delete: (caseId: number) => http.delete(`/cases/${caseId}/script`),
}

export const webRecordingApi = {
  workers: () => http.get<unknown, WebRecordingWorkersResponse>('/web-recordings/workers'),
  start: (data: { start_url: string; project_id: number; browser?: 'chromium' | 'firefox' | 'webkit'; viewport_width?: number; viewport_height?: number }) =>
    http.post<unknown, WebRecordingItem>('/web-recordings', data),
  get: (id: string) => http.get<unknown, WebRecordingItem>(`/web-recordings/${id}`),
  screenshot: (id: string) => http.post<unknown, Blob>(`/web-recordings/${id}/screenshot`, undefined, { responseType: 'blob' }),
  stop: (id: string) => http.post<unknown, WebRecordingItem>(`/web-recordings/${id}/stop`),
}

export const environmentApi = {
  list: (projectId: number) =>
    http.get<unknown, EnvironmentItem[]>('/environments', { params: { project_id: projectId } }),
  create: (data: { name: string; description?: string; project_id: number }) =>
    http.post('/environments', data),
  update: (id: number, data: { name?: string; description?: string }) =>
    http.patch(`/environments/${id}`, data),
  delete: (id: number) => http.delete(`/environments/${id}`),
  getVariables: (id: number) => http.get<unknown, EnvVariableItem[]>(`/environments/${id}/variables`),
  saveVariables: (id: number, data: { variables: Array<{ key: string; value: string; is_secret: boolean }> }) =>
    http.put(`/environments/${id}/variables`, data),
}

export const configurationCenterApi = {
  overview: (projectId?: number | null) =>
    http.get<unknown, ConfigurationCenterOverview>('/configuration-center/overview', {
      params: projectId ? { project_id: projectId } : undefined,
    }),
  revisions: (params: { domain: string; resource_id: number; project_id?: number | null; limit?: number }) =>
    http.get<unknown, ConfigurationRevisionItem[]>('/configuration-center/revisions', { params }),
  diff: (revisionId: number) =>
    http.get<unknown, ConfigurationRevisionDiff>(`/configuration-center/revisions/${revisionId}/diff`),
  createRevision: (data: { domain: ConfigurationSnapshotDomain; resource_id: number; reason?: string }) =>
    http.post<unknown, ConfigurationRevisionItem>('/configuration-center/revisions', data),
  rollback: (revisionId: number) =>
    http.post<unknown, ConfigurationRevisionRollbackResult>(`/configuration-center/revisions/${revisionId}/rollback`, {
      confirmation: 'ROLLBACK',
    }),
}

export const deviceApi = {
  list: (params?: { status_filter?: string }) =>
    http.get<unknown, DeviceItem[]>('/devices', { params }),
  workers: () => http.get<unknown, AndroidWorkerItem[]>('/devices/workers'),
  acquireLease: (id: number, data?: { ttl_seconds?: number; owner_label?: string }) =>
    http.post<unknown, DeviceLeaseItem>(`/devices/${id}/lease`, data ?? {}),
  heartbeatLease: (id: number, leaseToken: string) =>
    http.post<unknown, DeviceLeaseItem>(`/devices/${id}/lease/heartbeat`, { lease_token: leaseToken }),
  releaseLease: (id: number, leaseToken: string) =>
    http.delete(`/devices/${id}/lease`, { data: { lease_token: leaseToken } }),
  scan: () => http.post<unknown, DeviceScanResult>('/devices/scan'),
  scanStatus: (scanId: string) => http.get<unknown, DeviceScanResult>(`/devices/scan/${scanId}`),
  get: (id: number) => http.get('/devices/' + id),
  update: (id: number, data: { name?: string; description?: string }) =>
    http.patch(`/devices/${id}`, data),
  delete: (id: number) => http.delete(`/devices/${id}`),
  screenshot: (id: number) =>
    http.get<unknown, Blob>(`/devices/${id}/screenshot`, { responseType: 'blob' }),
  tap: (id: number, data: { x: number; y: number }) =>
    http.post(`/devices/${id}/tap`, data),
  uiTarget: (id: number, data: { x: number; y: number }) =>
    http.get<unknown, { target: AndroidUiTarget | null }>(`/devices/${id}/ui-target`, { params: data }),
  swipe: (id: number, data: { x1: number; y1: number; x2: number; y2: number; duration_ms?: number }) =>
    http.post(`/devices/${id}/swipe`, data),
  screenshotUrl: (id: number) => `/api/v1/devices/${id}/screenshot`,
  screenStreamUrl: (id: number, fps?: number) =>
    `/api/v1/devices/${id}/screen${fps ? `?fps=${fps}` : ''}`,
}

export const apkApi = {
  list: (params?: { project_id?: number }) =>
    http.get<unknown, ApkItem[]>('/apks', { params }),
  get: (id: number) => http.get('/apks/' + id),
  upload: (data: FormData) => http.post('/apks', data),
  update: (id: number, data: { description?: string; package_name?: string; version_name?: string; version_code?: number }) =>
    http.patch(`/apks/${id}`, data),
  delete: (id: number) => http.delete(`/apks/${id}`),
  download: (id: number) =>
    http.get<unknown, { url: string; filename: string }>(`/apks/${id}/download`),
}

export const suiteApi = {
  list: (params?: { project_id?: number }) =>
    http.get<unknown, SuiteItem[]>('/suites', { params }),
  get: (id: number) => http.get<unknown, SuiteItem>('/suites/' + id),
  create: (data: SuiteSavePayload) => http.post<unknown, SuiteItem>('/suites', data),
  update: (id: number, data: SuiteSavePayload) => http.patch<unknown, SuiteItem>(`/suites/${id}`, data),
  delete: (id: number) => http.delete(`/suites/${id}`),
  run: (id: number, data?: { env_id?: number; extra_vars?: object }) =>
    http.post<unknown, SuiteRunItem>(`/suites/${id}/run`, data ?? {}),
  listRuns: (params?: { suite_id?: number }) =>
    http.get<unknown, SuiteRunItem[]>('/suite-runs', { params }),
  getRun: (id: number) => http.get<unknown, SuiteRunItem>('/suite-runs/' + id),
  exportRunHtml: (id: number) =>
    http.get<unknown, Blob>(`/suite-runs/${id}/export/html`, { responseType: 'blob' }),
  exportRunPdf: (id: number) =>
    http.get<unknown, Blob>(`/suite-runs/${id}/export/pdf`, { responseType: 'blob' }),
  batchDelete: (suiteIds: number[]) =>
    http.post<unknown, { requested: number; processed: number; skipped_ids: number[] }>(
      '/suites/batch/delete',
      { suite_ids: suiteIds },
    ),
  batchCopy: (suiteIds: number[], suffix = ' - 副本') =>
    http.post<unknown, { requested: number; processed: number; skipped_ids: number[]; created_ids: number[] }>(
      '/suites/batch/copy',
      { suite_ids: suiteIds, suffix },
    ),
}

export const planApi = {
  list: (params?: { project_id?: number }) =>
    http.get<unknown, PlanItem[]>('/plans', { params }),
  get: (id: number) => http.get<unknown, PlanItem>('/plans/' + id),
  create: (data: PlanSavePayload) => http.post<unknown, PlanItem>('/plans', data),
  update: (id: number, data: PlanSavePayload) => http.patch<unknown, PlanItem>(`/plans/${id}`, data),
  delete: (id: number) => http.delete(`/plans/${id}`),
  run: (id: number, data?: { env_id?: number; extra_vars?: object }) =>
    http.post<unknown, PlanRunItem>(`/plans/${id}/run`, data ?? {}),
  listRuns: (params?: { plan_id?: number }) =>
    http.get<unknown, PlanRunItem[]>('/plan-runs', { params }),
  getRun: (id: number) => http.get<unknown, PlanRunItem>('/plan-runs/' + id),
  exportRunHtml: (id: number) =>
    http.get<unknown, Blob>(`/plan-runs/${id}/export/html`, { responseType: 'blob' }),
  exportRunPdf: (id: number) =>
    http.get<unknown, Blob>(`/plan-runs/${id}/export/pdf`, { responseType: 'blob' }),
  batchDelete: (planIds: number[]) =>
    http.post<unknown, { requested: number; processed: number; skipped_ids: number[] }>(
      '/plans/batch/delete',
      { plan_ids: planIds },
    ),
  batchToggle: (planIds: number[], isEnabled: boolean) =>
    http.post<unknown, { requested: number; processed: number; skipped_ids: number[] }>(
      '/plans/batch/toggle',
      { plan_ids: planIds, is_enabled: isEnabled },
    ),
}

export const notificationApi = {
  list: (params?: { project_id?: number }) =>
    http.get<unknown, NotificationItem[]>('/notifications', { params }),
  get: (id: number) => http.get('/notifications/' + id),
  create: (data: object) => http.post('/notifications', data),
  update: (id: number, data: object) => http.patch(`/notifications/${id}`, data),
  delete: (id: number) => http.delete(`/notifications/${id}`),
  test: (id: number) => http.post(`/notifications/${id}/test`),
  deliveries: (params?: { project_id?: number; config_id?: number; status?: 'sent' | 'failed'; limit?: number }) =>
    http.get<unknown, NotificationDeliveryItem[]>('/notifications/deliveries', { params }),
}

export const statisticsApi = {
  overview: (params?: { project_id?: number; days?: number }) =>
    http.get<unknown, { total_cases: number; total_runs: number; pass_rate: number; recent_runs_7d: number }>(
      '/statistics/overview', { params },
    ),
  passRateTrend: (params?: { project_id?: number; days?: number; case_type?: string; aggregate?: 'daily' | 'weekly' }) =>
    http.get<unknown, Array<{ date: string; total: number; passed: number; rate: number }>>(
      '/statistics/pass-rate-trend', { params },
    ),
  durationTrend: (params?: { project_id?: number; days?: number; case_type?: string; aggregate?: 'daily' | 'weekly' }) =>
    http.get<unknown, Array<{ date: string; avg_duration_ms: number; max_duration_ms: number; run_count: number }>>(
      '/statistics/duration-trend', { params },
    ),
  failureTop: (params?: { project_id?: number; days?: number; top?: number; case_type?: string }) =>
    http.get<unknown, Array<{ case_id: number; project_id: number; module_id: number; case_name: string; case_type: string; failure_count: number }>>(
      '/statistics/failure-top', { params },
    ),
  executorTop: (params?: { project_id?: number; days?: number; top?: number; case_type?: string }) =>
    http.get<unknown, StatisticsExecutorTopItem[]>('/statistics/executor-top', { params }),
  triggerTypeStats: (params?: { project_id?: number; days?: number }) =>
    http.get<unknown, StatisticsTriggerTypeStatItem[]>('/statistics/trigger-type-stats', { params }),
  planTrend: (params?: { project_id?: number; days?: number; aggregate?: 'daily' | 'weekly' }) =>
    http.get<unknown, StatisticsAggregateTrendItem[]>('/statistics/plan-trend', { params }),
  suiteTrend: (params?: { project_id?: number; days?: number; aggregate?: 'daily' | 'weekly' }) =>
    http.get<unknown, StatisticsAggregateTrendItem[]>('/statistics/suite-trend', { params }),
  caseTypeDistribution: (params?: { project_id?: number; days?: number }) =>
    http.get<unknown, StatisticsCaseTypeDistributionItem[]>('/statistics/case-type-distribution', { params }),
  exportCsv: (params: { chart: string; project_id?: number; days?: number; case_type?: string; aggregate?: 'daily' | 'weekly'; top?: number }) =>
    http.get<unknown, Blob>('/statistics/export/csv', { params, responseType: 'blob' }),
}

export const reportApi = {
  overview: (params?: { project_id?: number; days?: number; recent_limit?: number }) =>
    http.get<unknown, ReportOverviewItem>('/reports/overview', { params }),
  compare: (params: { baseline_run_id: number; current_run_id: number }) =>
    http.get<unknown, ReportCompareItem>('/reports/compare', { params }),
}

export const adminRunRetentionApi = {
  preview: (days?: number) =>
    http.get<unknown, RunRetentionPreview>('/admin/runs/retention/preview', { params: days ? { days } : undefined }),
  perProjectPreview: () =>
    http.get<unknown, RunRetentionPerProjectPreview>('/admin/runs/retention/per-project-preview'),
  run: (days?: number) =>
    http.post<unknown, RunRetentionExecuteResult>('/admin/runs/retention/run', days ? { days } : {}),
}

export const mockRuleApi = {
  list: (params?: { project_id?: number }) =>
    http.get<unknown, MockRuleItem[]>('/mock-rules', { params }),
  get: (id: number) => http.get<unknown, MockRuleItem>('/mock-rules/' + id),
  create: (data: object) => http.post<unknown, MockRuleItem>('/mock-rules', data),
  update: (id: number, data: object) => http.patch<unknown, MockRuleItem>(`/mock-rules/${id}`, data),
  delete: (id: number) => http.delete(`/mock-rules/${id}`),
  logs: (projectId: number) => http.get<unknown, MockRuleLogItem[]>(`/mock-rules/logs/${projectId}`),
  exportRules: (projectId: number) => http.get<unknown, { project_id: number; rules: MockRuleItem[] }>(`/mock-rules/export/${projectId}`),
  importRules: (data: { project_id: number; rules: unknown[] }) => http.post<unknown, MockRuleItem[]>('/mock-rules/import', data),
  aiGenerate: (data: { project_id: number; rule_ids?: number[]; requirement?: string; rule_count?: number }) =>
    http.post<unknown, MockAIGenerateResult>('/mock-rules/ai-generate', data),
}

export const bugTrackerApi = {
  list: (params?: { project_id?: number }) =>
    http.get<unknown, BugTrackerItem[]>('/bug-trackers', { params }),
  get: (id: number) => http.get<unknown, BugTrackerItem>('/bug-trackers/' + id),
  create: (data: object) => http.post<unknown, BugTrackerItem>('/bug-trackers', data),
  update: (id: number, data: object) => http.patch<unknown, BugTrackerItem>(`/bug-trackers/${id}`, data),
  delete: (id: number) => http.delete(`/bug-trackers/${id}`),
  testConnection: (data: { tracker_id?: number; tracker_type: BugTrackerType; config: object }) =>
    http.post<unknown, { ok: boolean; message: string }>('/bug-trackers/test-connection', data),
  getBugStatus: (runId: number) =>
    http.get<unknown, { bug_id: string; status: string; bug_url?: string }>(`/runs/${runId}/bug-status`),
  linkBug: (runId: number, data: { tracker_id: number; bug_id: string; bug_url?: string; title?: string; status?: string }) =>
    http.post<unknown, { bug_id: string; status: string; bug_url?: string }>(`/runs/${runId}/link-bug`, data),
  createBug: (runId: number, data: { tracker_id: number; step_index?: number }) =>
    http.post<unknown, { bug_id: string; bug_url: string; title: string; duplicate_of?: string | null; attachment_uploaded?: boolean }>(`/runs/${runId}/create-bug`, data),
}

export const defectApi = {
  list: (params?: {
    project_id?: number
    case_id?: number
    run_type?: DefectRunType
    run_id?: number
    status?: DefectStatus
    priority?: DefectPriority
    severity?: DefectSeverity
    page?: number
    page_size?: number
  }) => http.get<unknown, { items: DefectItem[]; total: number; page: number; page_size: number }>('/defects', { params }),
  get: (id: number) => http.get<unknown, DefectItem>(`/defects/${id}`),
  create: (data: {
    project_id: number
    case_id?: number | null
    title: string
    description?: string | null
    priority?: DefectPriority
    severity?: DefectSeverity
    assignee_id?: number | null
    labels?: string[]
  }) => http.post<unknown, DefectMutationResult>('/defects', data),
  createFromRun: (runType: DefectRunType, runId: number, data?: {
    title?: string
    description?: string | null
    priority?: DefectPriority
    severity?: DefectSeverity
    assignee_id?: number | null
  }) => http.post<unknown, DefectMutationResult>(`/defects/from-run/${runType}/${runId}`, data ?? {}),
  update: (id: number, data: Partial<{
    title: string
    description: string | null
    status: DefectStatus
    priority: DefectPriority
    severity: DefectSeverity
    resolution: string | null
    labels: string[]
    assignee_id: number | null
  }>) => http.patch<unknown, DefectItem>(`/defects/${id}`, data),
  linkRun: (id: number, data: { run_type: DefectRunType; run_id: number; case_id?: number | null }) =>
    http.post<unknown, DefectRunLinkItem>(`/defects/${id}/links`, data),
  unlinkRun: (id: number, linkId: number) => http.delete(`/defects/${id}/links/${linkId}`),
  externalLinks: (id: number) => http.get<unknown, DefectExternalLinkItem[]>(`/defects/${id}/external-links`),
  linkExternal: (id: number, data: {
    tracker_id: number
    external_key: string
    external_url?: string
    external_title?: string
    external_status?: string
  }) => http.post<unknown, DefectExternalLinkItem>(`/defects/${id}/external-links`, data),
  createExternal: (id: number, data: { tracker_id: number }) =>
    http.post<unknown, DefectExternalLinkItem>(`/defects/${id}/external-links/create`, data),
  syncExternal: (id: number, linkId: number, data?: { apply_status?: boolean }) =>
    http.post<unknown, { link: DefectExternalLinkItem; defect_status: DefectStatus }>(
      `/defects/${id}/external-links/${linkId}/sync`, data ?? {},
    ),
  unlinkExternal: (id: number, linkId: number) => http.delete(`/defects/${id}/external-links/${linkId}`),
}

// ---- Mobile Special Testing ----
export const mobileSpecialApi = {
  // Tasks
  listTasks: (params?: { project_id?: number; task_type?: TaskType }) =>
    http.get<unknown, MobileSpecialTaskItem[]>('/mobile-special/tasks', { params }),
  getTask: (id: number) => http.get<unknown, MobileSpecialTaskItem>(`/mobile-special/tasks/${id}`),
  createTask: (data: object) => http.post<unknown, MobileSpecialTaskItem>('/mobile-special/tasks', data),
  updateTask: (id: number, data: object) => http.patch<unknown, MobileSpecialTaskItem>(`/mobile-special/tasks/${id}`, data),
  deleteTask: (id: number) => http.delete(`/mobile-special/tasks/${id}`),
  triggerTask: (id: number, data?: { device_id?: number; app_package?: string }) =>
    http.post<unknown, MobileSpecialRunItem>(`/mobile-special/tasks/${id}/run`, data ?? {}),
  // Runs
  listRuns: (params?: { task_id?: number; task_type?: TaskType; status_filter?: MobileRunStatus; project_id?: number; limit?: number; offset?: number }) =>
    http.get<unknown, MobileSpecialRunItem[]>('/mobile-special/runs', { params }),
  getRun: (id: number) => http.get<unknown, MobileSpecialRunItem>(`/mobile-special/runs/${id}`),
  getRunSummary: (id: number) => http.get<unknown, Record<string, unknown>>(`/mobile-special/runs/${id}/summary`),
  getRunSamples: (id: number, params?: { metric_type?: string; limit?: number }) =>
    http.get<unknown, MobileMetricSampleItem[]>(`/mobile-special/runs/${id}/samples`, { params }),
  getRunIncidents: (id: number) =>
    http.get<unknown, MobileIncidentItem[]>(`/mobile-special/runs/${id}/incidents`),
  getRunEvents: (id: number, params?: { limit?: number }) =>
    http.get<unknown, MobileRunEventItem[]>(`/mobile-special/runs/${id}/events`, { params }),
  getRunArtifacts: (id: number) =>
    http.get<unknown, MobileRunArtifactItem[]>(`/mobile-special/runs/${id}/artifacts`),
  getArtifactUrl: (runId: number, artifactId: number) =>
    http.get<unknown, { url: string; file_name: string }>(`/mobile-special/runs/${runId}/artifacts/${artifactId}/url`),
  stopRun: (id: number) => http.post<unknown, MobileSpecialRunItem>(`/mobile-special/runs/${id}/stop`),
  replayRun: (id: number) => http.post<unknown, MobileSpecialRunItem>(`/mobile-special/runs/${id}/replay`),
  // Export
  exportRunCsv: (runId: number) =>
    http.get<unknown, Blob>(`/mobile-special/runs/${runId}/export/csv`, { responseType: 'blob' }),
  exportRunJson: (runId: number) =>
    http.get<unknown, Blob>(`/mobile-special/runs/${runId}/export/json`, { responseType: 'blob' }),
  // Statistics
  getOverview: (params?: { project_id?: number; days?: number }) =>
    http.get<unknown, { total_runs: number; completed_runs: number; failed_runs: number; running_runs: number; pass_rate: number; avg_duration_ms: number | null; total_incidents: number; recent_runs_7d: number }>('/mobile-special/statistics/overview', { params }),
  getTrend: (params?: { project_id?: number; days?: number }) =>
    http.get<unknown, Array<{ date: string; total: number; completed: number; failed: number; pass_rate: number }>>('/mobile-special/statistics/trend', { params }),
  getTaskStats: (params?: { project_id?: number; days?: number; limit?: number }) =>
    http.get<unknown, Array<{ task_id: number; task_name: string; task_type: string; total_runs: number; completed_runs: number; failed_runs: number; pass_rate: number; last_run_at: string | null }>>('/mobile-special/statistics/task-stats', { params }),
}

export const storageApi = {
  stats: () => http.get<unknown, StorageStatsItem>('/storage/stats'),
  previewCleanup: (data?: { prefixes?: string[]; retention_days?: number }) =>
    http.post<unknown, StorageCleanupPreviewItem>('/storage/cleanup-preview', data ?? {}),
  executeCleanup: (data: { object_names: string[]; prefixes?: string[]; repair_orphan_references?: boolean }) =>
    http.post<unknown, StorageCleanupExecuteItem>('/storage/cleanup-execute', data),
  reconcileDatasetStorage: (projectId: number, purge = false) =>
    http.post<unknown, StorageDatasetReconcileItem>(`/projects/${projectId}/datasets/storage/reconcile`, { purge }),
  listPolicies: () => http.get<unknown, StoragePolicyItem[]>('/storage/policies'),
  createPolicy: (data: StoragePolicyPayload) =>
    http.post<unknown, StoragePolicyItem>('/storage/policies', data),
  updatePolicy: (id: number, data: StoragePolicyPayload) =>
    http.patch<unknown, StoragePolicyItem>(`/storage/policies/${id}`, data),
  deletePolicy: (id: number) => http.delete(`/storage/policies/${id}`),
  getAlert: () => http.get<unknown, StorageAlertResponse>('/storage/alert'),
}

export const dashboardAlertApi = {
  listRules: (params?: { project_id?: number; enabled?: boolean }) =>
    http.get<unknown, DashboardAlertRuleItem[]>('/dashboard-alert-rules', { params }),
  createRule: (data: DashboardAlertRulePayload) =>
    http.post<unknown, DashboardAlertRuleItem>('/dashboard-alert-rules', data),
  updateRule: (id: number, data: DashboardAlertRulePayload) =>
    http.patch<unknown, DashboardAlertRuleItem>(`/dashboard-alert-rules/${id}`, data),
  deleteRule: (id: number) => http.delete<unknown, void>(`/dashboard-alert-rules/${id}`),
  listEvents: (params?: { project_id?: number; rule_id?: number; limit?: number }) =>
    http.get<unknown, DashboardAlertEventItem[]>('/dashboard-alert-events', { params }),
}

// ---- Global Variables ----
export const globalVariableApi = {
  list: (params?: { project_id?: number; scope_type?: ScopeType }) =>
    http.get<unknown, GlobalVariableItem[]>('/global-variables', { params }),
  get: (id: number, params?: { reveal_secret?: boolean }) =>
    http.get<unknown, GlobalVariableItem>(`/global-variables/${id}`, { params }),
  create: (data: object) => http.post<unknown, GlobalVariableItem>('/global-variables', data),
  update: (id: number, data: object) => http.patch<unknown, GlobalVariableItem>(`/global-variables/${id}`, data),
  delete: (id: number) => http.delete(`/global-variables/${id}`),
}

// ---- AI LLM Config ----
export type LLMProvider = 'deepseek' | 'claude' | 'openai' | 'openai_compatible' | 'qwen' | 'ollama'

export interface AILLMConfigItem {
  id: number
  name: string
  provider: LLMProvider
  endpoint?: string | null
  model_name: string
  default_params: Record<string, unknown>
  enabled: boolean
  supports_vision: boolean
  description?: string | null
  has_api_key: boolean
  created_at: string
  updated_at: string
}

export interface AILLMConfigCreatePayload {
  name: string
  provider: LLMProvider
  api_key: string
  endpoint?: string | null
  model_name: string
  default_params?: Record<string, unknown>
  enabled?: boolean
  supports_vision?: boolean
  description?: string | null
}

export interface AILLMConfigUpdatePayload {
  name?: string
  provider?: LLMProvider
  api_key?: string
  endpoint?: string | null
  model_name?: string
  default_params?: Record<string, unknown>
  enabled?: boolean
  supports_vision?: boolean
  description?: string | null
}

export interface AILLMModelOption {
  id: string
  label: string
  owned_by?: string | null
  supports_vision?: boolean | null
  supports_reasoning?: boolean | null
  capability_source: string
  capabilities: string[]
}

export interface AILLMModelDiscoveryResult {
  provider: LLMProvider
  endpoint: string
  models: AILLMModelOption[]
}

export const aiLLMConfigApi = {
  list: () => http.get<unknown, AILLMConfigItem[]>('/ai/llm-configs'),
  get: (id: number) => http.get<unknown, AILLMConfigItem>(`/ai/llm-configs/${id}`),
  discoverModels: (data: { config_id?: number; provider: LLMProvider; api_key?: string; endpoint?: string | null }) =>
    http.post<unknown, AILLMModelDiscoveryResult>('/ai/llm-configs/models', data),
  create: (data: AILLMConfigCreatePayload) => http.post<unknown, AILLMConfigItem>('/ai/llm-configs', data),
  update: (id: number, data: AILLMConfigUpdatePayload) =>
    http.patch<unknown, AILLMConfigItem>(`/ai/llm-configs/${id}`, data),
  delete: (id: number) => http.delete(`/ai/llm-configs/${id}`),
}

// ---- AI Healing Prompt Examples ----
export interface HealingPromptExampleItem {
  id: number
  error_fingerprint: string
  case_type: string
  step_context_json: Record<string, unknown>
  suggestion_text: string
  source_step_result_id?: number | null
  marked_high_quality: boolean
  marked_by?: number | null
  marked_at?: string | null
  created_at: string
  updated_at: string
}

export const aiHealingExampleApi = {
  list: (params?: {
    error_fingerprint?: string
    case_type?: string
    high_quality?: boolean
    limit?: number
  }) => http.get<unknown, HealingPromptExampleItem[]>('/ai-healing/examples', { params }),
  createFromStep: (stepResultId: number) =>
    http.post<unknown, HealingPromptExampleItem>(`/ai-healing/examples/from-step/${stepResultId}`),
  update: (id: number, data: { marked_high_quality?: boolean; suggestion_text?: string }) =>
    http.patch<unknown, HealingPromptExampleItem>(`/ai-healing/examples/${id}`, data),
  delete: (id: number) => http.delete<unknown, void>(`/ai-healing/examples/${id}`),
}

export interface HealingPatchPreviewRequest {
  case_id: number
  raw_suggestion?: string
  suggestion?: Record<string, unknown>
}

export interface HealingPatchPreviewResult {
  accepted: boolean
  reasons: string[]
  normalized_patch: Record<string, unknown> | null
  preview_config: Record<string, unknown> | null
}

export interface HealingPatchApplyRequest extends HealingPatchPreviewRequest {
  trigger_regression?: boolean
  env_id?: number | null
  extra_vars?: Record<string, unknown> | null
  source_run_id?: number | null
  source_step_id?: number | null
}

export interface HealingPatchApplyResult extends HealingPatchPreviewResult {
  case_id: number
  snapshot_id?: number | null
  regression_run_id?: number | null
}

export const aiHealingPatchApi = {
  preview: (data: HealingPatchPreviewRequest) =>
    http.post<unknown, HealingPatchPreviewResult>('/ai-healing/patch-preview', data),
  apply: (data: HealingPatchApplyRequest) =>
    http.post<unknown, HealingPatchApplyResult>('/ai-healing/patch-apply', data),
}

export interface AIHealingCaseTypeStat {
  case_type: string
  total_count: number
  adopted_count: number
  rejected_count: number
  adopted_rate: number
}

export interface AIHealingTopFingerprint {
  error_fingerprint: string
  case_type: string
  total_count: number
  adopted_count: number
  rejected_count: number
  adopted_rate: number
}

export interface AIHealingTrendItem {
  date: string
  total_count: number
  adopted_count: number
  rejected_count: number
  adopted_rate: number
}

export interface AIHealingProductionFeedback {
  regression_triggered_count: number
  regression_success_count: number
  regression_success_rate: number
  latest_feedback_aggregated_at?: string | null
}

export interface AIHealingStats {
  total_feedback_count: number
  adopted_count: number
  rejected_count: number
  adopted_rate: number
  high_quality_example_count: number
  by_case_type: AIHealingCaseTypeStat[]
  top_error_fingerprints: AIHealingTopFingerprint[]
  recent_trend: AIHealingTrendItem[]
  production_feedback: AIHealingProductionFeedback
}

export const aiHealingStatsApi = {
  getStats: (params?: { days?: number }) =>
    http.get<unknown, AIHealingStats>('/ai-healing/stats', { params }),
}

// ---- AI Case Generation ----
export type SchemaSourceType = 'openapi' | 'postman' | 'curl' | 'sample'

export interface AIEndpointParameter {
  name: string
  location: 'path' | 'query' | 'header' | 'body'
  required: boolean
  schema_type?: string | null
  description?: string | null
  example?: unknown
}

export interface AIEndpointSummary {
  method: string
  path: string
  base_url?: string | null
  summary?: string | null
  description?: string | null
  operation_id?: string | null
  tags: string[]
  parameters: AIEndpointParameter[]
  request_body_example?: unknown
  response_example?: unknown
}

export interface AIParseSchemaPayload {
  source_type: SchemaSourceType
  content: string
  external_ref_policy?: 'warn' | 'reject'
}

export interface AIParseSchemaResult {
  endpoints: AIEndpointSummary[]
  warnings: string[]
}

export interface AICaseStepDraft {
  action: string
  test_data?: string | null
  expected_result?: string | null
  is_key_step?: boolean
  remarks?: string | null
}

export interface AICaseDraft {
  name: string
  summary?: string | null
  description?: string | null
  case_type: CaseType
  priority: CasePriority
  case_level: CaseLevel
  tags: string[]
  preconditions: string[]
  postconditions: string[]
  steps: AICaseStepDraft[]
  config: Record<string, unknown>
  dataset_id?: number | null
  dataset_version?: number | null
}

export interface AICaseGeneratePayload {
  project_id: number
  module_id: number
  endpoints?: AIEndpointSummary[]
  user_requirement?: string
  case_type?: CaseType
  priority?: CasePriority
  case_level?: CaseLevel
  max_cases?: number
  dataset_id?: number | null
  dataset_version?: number | null
  mock_rule_ids?: number[]
}

export interface AICaseGenerateResult {
  project_id: number
  module_id: number
  drafts: AICaseDraft[]
  raw_response?: string | null
  warnings: string[]
}

export interface AICaseFunnelStats {
  generated_sessions: number
  generated_drafts: number
  saved_drafts: number
  failed_generations: number
  warning_count: number
  save_rate: number
  latest_event_at?: string | null
}

export const aiCaseGenerationApi = {
  parseSchema: (data: AIParseSchemaPayload) =>
    http.post<unknown, AIParseSchemaResult>('/ai/cases/parse-schema', data),
  generate: (data: AICaseGeneratePayload) =>
    http.post<unknown, AICaseGenerateResult>('/ai/cases/generate', data),
  getFunnelStats: (params?: { days?: number; project_id?: number }) =>
    http.get<unknown, AICaseFunnelStats>('/ai/cases/funnel-stats', { params }),
}

export interface TracingConfig {
  jaeger_ui_url: string
}

export const tracingApi = {
  getConfig: () => http.get<unknown, TracingConfig>('/traces/config'),
}

export interface UserSettingItem {
  key: string
  value: Record<string, unknown>
  updated_at?: string | null
}

export const userSettingsApi = {
  list: () => http.get<unknown, UserSettingItem[]>('/users/me/settings'),
  get: (key: string) => http.get<unknown, UserSettingItem>(`/users/me/settings/${encodeURIComponent(key)}`),
  update: (key: string, value: Record<string, unknown>) =>
    http.put<unknown, UserSettingItem>(`/users/me/settings/${encodeURIComponent(key)}`, { value }),
  delete: (key: string) => http.delete<unknown, void>(`/users/me/settings/${encodeURIComponent(key)}`),
}

// ---- Performance Testing ----
export type PerformanceRunStatus = 'pending' | 'running' | 'cancelling' | 'success' | 'failed' | 'cancelled'

export interface PerformanceSummary {
  executor?: string
  rps?: number | null
  p95_ms?: number | null
  p99_ms?: number | null
  error_rate?: number | null
  iterations?: number | null
  data_received?: number | null
  data_sent?: number | null
  exit_code?: number | null
  k6_error?: string | null
  locust_error?: string | null
  grpc_error?: string | null
  thresholds?: Record<string, unknown>
  [key: string]: unknown
}

export interface PerformanceTestItem {
  id: number
  project_id: number
  name: string
  description?: string | null
  executor: 'k6' | 'locust' | 'grpc' | string
  script_object_name: string
  default_options: Record<string, unknown>
  creator_id?: number | null
  baseline_run_id?: number | null
  schedule_enabled: boolean
  cron_expression?: string | null
  schedule_timezone: string
  schedule_environment_id?: number | null
  schedule_node_id?: number | null
  dataset_id?: number | null
  schedule_options: Record<string, unknown>
  last_scheduled_run_at?: string | null
  next_run_at?: string | null
  created_at: string
  updated_at: string
}

export interface PerformanceRunItem {
  id: number
  performance_test_id: number
  project_id: number
  environment_id?: number | null
  performance_node_id?: number | null
  idempotency_key?: string | null
  parent_run_id?: number | null
  dataset_id?: number | null
  dataset_version?: number | null
  status: PerformanceRunStatus | string
  triggered_by?: number | null
  started_at?: string | null
  finished_at?: string | null
  duration_ms?: number | null
  options_snapshot: Record<string, unknown>
  summary: PerformanceSummary
  raw_result_object_name?: string | null
  error_message?: string | null
  progress_percent: number
  created_at: string
  updated_at: string
}

export type PerformanceGateStatus = 'pending' | 'passed' | 'failed' | 'not_configured' | 'cancelled'

export interface PerformanceGateItem {
  status: PerformanceGateStatus
  ready: boolean
  run_status: PerformanceRunStatus | string
  total: number
  passed: number
  failed: number
}

export interface PerformanceBaselineMetricItem {
  metric: string
  preferred_direction: 'higher' | 'lower'
  baseline: number | null
  current: number | null
  delta: number | null
  delta_percent: number | null
  direction: 'improvement' | 'regression' | 'unchanged' | 'unknown'
}

export interface PerformanceBaselineComparisonItem {
  baseline_run_id: number
  run_id: number
  metrics: PerformanceBaselineMetricItem[]
}

export interface PerformanceMetricSampleItem {
  id: number
  run_id: number
  captured_at: string
  node_id: string
  source: string
  metrics: Record<string, number>
  errors: string[]
}

export interface PerformanceTrendPointItem {
  date: string
  run_count: number
  success_count: number
  failed_count: number
  cancelled_count: number
  active_count: number
  other_count: number
  avg_rps: number | null
  avg_p95_ms: number | null
  avg_p99_ms: number | null
  avg_error_rate: number | null
  max_p95_ms: number | null
}

export interface PerformanceTrendItem {
  project_id: number
  days: number
  from_at: string
  to_at: string
  run_count: number
  success_count: number
  failed_count: number
  cancelled_count: number
  active_count: number
  other_count: number
  avg_rps: number | null
  avg_p95_ms: number | null
  avg_p99_ms: number | null
  avg_error_rate: number | null
  max_p95_ms: number | null
  points: PerformanceTrendPointItem[]
}

export type PerformanceNodeStatus = 'online' | 'offline' | 'disabled' | 'draining'

export interface PerformanceNodeItem {
  id: number
  node_id: string
  name: string
  queue_name: string
  status: PerformanceNodeStatus | string
  enabled: boolean
  labels: Record<string, unknown>
  capabilities: Record<string, unknown>
  max_vus: number | null
  max_concurrency: number | null
  egress_allowlist: string[]
  last_heartbeat_at?: string | null
  last_error?: string | null
  created_at: string
  updated_at: string
}

export interface PerformanceExecutorItem {
  name: string
  label: string
  ready: boolean
  script_extensions: string[]
  supports_visual: boolean
  supports_dataset: boolean
  supports_http: boolean
  supports_grpc: boolean
  description: string
}

export interface PerformanceCapacityObservation {
  run_id: number
  load: number | null
  status: string
  error_rate: number | null
  p95_ms: number | null
  stable: boolean
  reasons: string[]
}

export interface PerformanceCapacityAnalysis {
  status: string
  max_stable_load: number | null
  max_stable_run_id: number | null
  stable_run_count: number
  observed_run_count: number
  first_unstable_load: number | null
  bottleneck: string | null
  observations: PerformanceCapacityObservation[]
}

export interface PerformanceTestPayload {
  project_id?: number
  name?: string
  description?: string | null
  executor?: 'k6' | 'locust' | 'grpc' | 'jmeter'
  script_object_name?: string
  default_options?: Record<string, unknown>
  dataset_id?: number | null
}

export interface PerformanceScriptUploadResponse {
  script_object_name: string
  filename: string
  size: number
}

export const performanceApi = {
  listExecutors: () => http.get<unknown, PerformanceExecutorItem[]>('/performance/executors'),
  listNodes: () => http.get<unknown, PerformanceNodeItem[]>('/performance/nodes'),
  createNode: (body: {
    node_id: string
    name: string
    queue_name?: string
    enabled?: boolean
    labels?: Record<string, unknown>
    capabilities?: Record<string, unknown>
    max_vus?: number | null
    max_concurrency?: number | null
    egress_allowlist?: string[]
  }) => http.post<unknown, PerformanceNodeItem>('/performance/nodes', body),
  updateNode: (id: number, body: Record<string, unknown>) =>
    http.patch<unknown, PerformanceNodeItem>(`/performance/nodes/${id}`, body),
  deleteNode: (id: number) => http.delete<unknown, void>(`/performance/nodes/${id}`),
  listTests: (projectId: number) =>
    http.get<unknown, PerformanceTestItem[]>(`/projects/${projectId}/performance/tests`),
  uploadScript: (projectId: number, file: File, executor: 'k6' | 'locust' | 'grpc' | 'jmeter' = 'k6') => {
    const form = new FormData()
    form.append('file', file)
    return http.post<unknown, PerformanceScriptUploadResponse>(`/projects/${projectId}/performance/scripts`, form, {
      params: { executor },
    })
  },
  createTest: (body: Required<Pick<PerformanceTestPayload, 'project_id' | 'name' | 'script_object_name'>> & PerformanceTestPayload) =>
    http.post<unknown, PerformanceTestItem>('/performance/tests', body),
  updateTest: (id: number, body: PerformanceTestPayload) =>
    http.patch<unknown, PerformanceTestItem>(`/performance/tests/${id}`, body),
  setBaseline: (testId: number, runId: number) =>
    http.put<unknown, PerformanceTestItem>(`/performance/tests/${testId}/baseline`, { run_id: runId }),
  clearBaseline: (testId: number) =>
    http.delete<unknown, PerformanceTestItem>(`/performance/tests/${testId}/baseline`),
  updateSchedule: (
    testId: number,
    body: {
      enabled: boolean
      cron_expression?: string | null
      timezone: string
      environment_id?: number | null
      performance_node_id?: number | null
      options?: Record<string, unknown>
    },
  ) => http.put<unknown, PerformanceTestItem>(`/performance/tests/${testId}/schedule`, body),
  triggerRun: (id: number, body?: {
    environment_id?: number | null
    performance_node_id?: number | null
    performance_node_ids?: number[]
    idempotency_key?: string
    options?: Record<string, unknown>
  }) =>
    http.post<unknown, PerformanceRunItem>(`/performance/tests/${id}/run`, body ?? {}),
  listRuns: (projectId: number) =>
    http.get<unknown, PerformanceRunItem[]>('/performance/runs', { params: { project_id: projectId } }),
  getTrend: (projectId: number, days = 30, performanceTestId?: number) =>
    http.get<unknown, PerformanceTrendItem>(`/projects/${projectId}/performance/trend`, {
      params: { days, performance_test_id: performanceTestId },
    }),
  analyzeCapacity: (projectId: number, body: { run_ids: number[]; max_error_rate?: number; max_p95_ms?: number | null; min_stable_runs?: number }) =>
    http.post<unknown, PerformanceCapacityAnalysis>(`/projects/${projectId}/performance/capacity/analyze`, body),
  getRun: (id: number) => http.get<unknown, PerformanceRunItem>(`/performance/runs/${id}`),
  stopRun: (id: number) => http.post<unknown, PerformanceRunItem>(`/performance/runs/${id}/stop`),
  getGate: (id: number) => http.get<unknown, PerformanceGateItem>(`/performance/runs/${id}/gate`),
  getBaselineComparison: (id: number) =>
    http.get<unknown, PerformanceBaselineComparisonItem>(`/performance/runs/${id}/baseline-comparison`),
  getMetrics: (id: number, limit = 2000) =>
    http.get<unknown, PerformanceMetricSampleItem[]>(`/performance/runs/${id}/metrics`, { params: { limit } }),
  exportRunJson: (id: number) =>
    http.get<unknown, Blob>(`/performance/runs/${id}/export/json`, { responseType: 'blob' }),
  exportRunCsv: (id: number) =>
    http.get<unknown, Blob>(`/performance/runs/${id}/export/csv`, { responseType: 'blob' }),
  getRawResult: (id: number) =>
    http.get<unknown, { url: string; filename: string; object_name: string }>(`/performance/runs/${id}/raw-result`),
}

// ---- Reusable Web assets ----
export interface WebElementAssetItem {
  id: number
  project_id: number
  name: string
  page_url?: string | null
  locator: Record<string, unknown>
  fallback_locators: Array<Record<string, unknown>>
  description?: string | null
  version: number
  owner_id?: number | null
  last_failed_at?: string | null
  last_failure_reason?: string | null
  created_at: string
  updated_at: string
}

export interface WebLocatorRepairCandidate {
  locator: Record<string, unknown>
  confidence: number
  reason: string
}

export interface WebPageObjectItem {
  id: number
  project_id: number
  name: string
  url_pattern?: string | null
  description?: string | null
  element_refs: Array<Record<string, unknown>>
  actions: Array<Record<string, unknown>>
  version: number
  owner_id?: number | null
  created_at: string
  updated_at: string
}

export const webAssetsApi = {
  listElements: (projectId: number) => http.get<unknown, WebElementAssetItem[]>(`/projects/${projectId}/web-elements`),
  createElement: (projectId: number, body: { name: string; page_url?: string | null; locator: Record<string, unknown>; fallback_locators?: Array<Record<string, unknown>>; description?: string }) =>
    http.post<unknown, WebElementAssetItem>(`/projects/${projectId}/web-elements`, body),
  updateElement: (id: number, body: Record<string, unknown>) => http.patch<unknown, WebElementAssetItem>(`/web-elements/${id}`, body),
  recordElementFailure: (id: number, reason: string) => http.post<unknown, WebElementAssetItem>(`/web-elements/${id}/failure`, { reason }),
  previewElementRepair: (id: number, observed_locators: Array<Record<string, unknown>> = []) =>
    http.post<unknown, { element_id: number; candidates: WebLocatorRepairCandidate[] }>(`/web-elements/${id}/repair-preview`, { observed_locators }),
  deleteElement: (id: number) => http.delete<unknown, void>(`/web-elements/${id}`),
  listPageObjects: (projectId: number) => http.get<unknown, WebPageObjectItem[]>(`/projects/${projectId}/web-page-objects`),
  createPageObject: (projectId: number, body: { name: string; url_pattern?: string | null; description?: string; element_refs?: Array<Record<string, unknown>>; actions?: Array<Record<string, unknown>> }) =>
    http.post<unknown, WebPageObjectItem>(`/projects/${projectId}/web-page-objects`, body),
  updatePageObject: (id: number, body: Record<string, unknown>) => http.patch<unknown, WebPageObjectItem>(`/web-page-objects/${id}`, body),
  deletePageObject: (id: number) => http.delete<unknown, void>(`/web-page-objects/${id}`),
}

export interface WebFileUploadResponse {
  object_name: string
  filename: string
  content_type: string
  size: number
}

export const webFilesApi = {
  upload: (projectId: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return http.post<unknown, WebFileUploadResponse>(`/projects/${projectId}/web-files`, form)
  },
}

export interface WebVisualBaselineItem {
  id: number
  project_id: number
  name: string
  page_url?: string | null
  object_name: string
  content_type: string
  width?: number | null
  height?: number | null
  threshold: number
  pixel_threshold: number
  ignore_regions: Array<Record<string, unknown>>
  version: number
  owner_id?: number | null
  created_at: string
  updated_at: string
}

export const webVisualApi = {
  listBaselines: (projectId: number) =>
    http.get<unknown, WebVisualBaselineItem[]>(`/projects/${projectId}/web-visual-baselines`),
  uploadBaseline: (projectId: number, body: {
    name: string
    page_url?: string
    threshold?: number
    pixel_threshold?: number
    ignore_regions?: Array<Record<string, unknown>>
    file: File
  }) => {
    const form = new FormData()
    form.append('name', body.name)
    if (body.page_url) form.append('page_url', body.page_url)
    form.append('threshold', String(body.threshold ?? 0.01))
    form.append('pixel_threshold', String(body.pixel_threshold ?? 10))
    form.append('ignore_regions', JSON.stringify(body.ignore_regions ?? []))
    form.append('file', body.file)
    return http.post<unknown, WebVisualBaselineItem>(`/projects/${projectId}/web-visual-baselines`, form)
  },
  updateSettings: (id: number, body: { threshold: number; pixel_threshold: number; ignore_regions: Array<Record<string, unknown>> }) =>
    http.patch<unknown, WebVisualBaselineItem>(`/web-visual-baselines/${id}`, body),
  deleteBaseline: (id: number) => http.delete<unknown, void>(`/web-visual-baselines/${id}`),
}

// ─── P3.B 测试数据集 ───────────────────────────────────────
export type DatasetFormat = 'csv' | 'json'
export type DatasetValidationPolicy = 'soft' | 'hard'
export type DatasetStorageMode = 'database' | 'minio'

export interface DatasetListItem {
  id: number
  name: string
  description: string | null
  project_id: number
  format: DatasetFormat
  storage_mode?: DatasetStorageMode
  row_count: number
  schema_field_count: number
  validation_policy: DatasetValidationPolicy
  creator_id: number
  created_at: string
  updated_at: string
}

export interface DatasetDetail {
  id: number
  name: string
  description: string | null
  project_id: number
  format: DatasetFormat
  storage_mode?: DatasetStorageMode
  row_count: number
  rows: Record<string, unknown>[]
  schema_fields: DatasetSchemaField[]
  validation_policy: DatasetValidationPolicy
  creator_id: number
  created_at: string
  updated_at: string
}

export type DatasetSchemaFieldType = 'string' | 'number' | 'integer' | 'boolean' | 'object' | 'array'

export interface DatasetSchemaField {
  name: string
  type?: DatasetSchemaFieldType
  required?: boolean
  default?: unknown
}

export interface DatasetValidationIssue {
  row_index: number
  field: string
  message: string
}

export interface DatasetValidationResult {
  valid: boolean
  row_count: number
  normalized_rows: Record<string, unknown>[]
  issues: DatasetValidationIssue[]
  validation_policy?: DatasetValidationPolicy | null
  can_upload?: boolean | null
}

export interface DatasetVersionItem {
  id: number
  dataset_id: number
  version: number
  format: DatasetFormat
  storage_mode?: DatasetStorageMode
  row_count: number
  schema_field_count: number
  validation_policy: DatasetValidationPolicy
  change_type: string
  created_by?: number | null
  created_at: string
}

export interface DatasetImpactItem {
  id: number
  name: string
  reason: string
}

export interface DatasetImpact {
  dataset_id: number
  cases: DatasetImpactItem[]
  suites: DatasetImpactItem[]
  plans: DatasetImpactItem[]
  total_count: number
}

export interface DatasetAIGenerateResult {
  project_id: number
  dataset_id?: number | null
  rows: Record<string, unknown>[]
  schema_fields: DatasetSchemaField[]
  warnings: string[]
}

export const datasetApi = {
  list: (projectId: number) =>
    http.get<unknown, DatasetListItem[]>(`/projects/${projectId}/datasets`),
  get: (id: number) => http.get<unknown, DatasetDetail>(`/datasets/${id}`),
  create: (body: { name: string; project_id: number; description?: string; format?: DatasetFormat; storage_mode?: DatasetStorageMode; rows?: Record<string, unknown>[]; schema_fields?: DatasetSchemaField[]; validation_policy?: DatasetValidationPolicy }) =>
    http.post<unknown, DatasetDetail>('/datasets', body),
  update: (id: number, body: { name?: string; description?: string; storage_mode?: DatasetStorageMode; rows?: Record<string, unknown>[]; schema_fields?: DatasetSchemaField[]; validation_policy?: DatasetValidationPolicy }) =>
    http.patch<unknown, DatasetDetail>(`/datasets/${id}`, body),
  delete: (id: number) => http.delete<unknown, void>(`/datasets/${id}`),
  getImpact: (id: number) => http.get<unknown, DatasetImpact>(`/datasets/${id}/impact`),
  listVersions: (id: number) => http.get<unknown, DatasetVersionItem[]>(`/datasets/${id}/versions`),
  rollback: (id: number, version: number) =>
    http.post<unknown, DatasetDetail>(`/datasets/${id}/rollback/${version}`),
  upload: (id: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return http.post<unknown, DatasetDetail>(`/datasets/${id}/upload`, form)
  },
  previewUpload: (id: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return http.post<unknown, DatasetValidationResult>(`/datasets/${id}/upload-preview`, form)
  },
  validate: (body: { schema_fields: DatasetSchemaField[]; rows: Record<string, unknown>[]; preview_limit?: number }) =>
    http.post<unknown, DatasetValidationResult>('/datasets/validate', body),
  aiGenerate: (body: {
    project_id: number
    dataset_id?: number | null
    requirement?: string
    row_count?: number
    schema_fields?: DatasetSchemaField[]
  }) => http.post<unknown, DatasetAIGenerateResult>('/datasets/ai-generate', body),
}

// ─── P3.C 项目成员与审计日志 ─────────────────────────────
export type ProjectRoleType = 'owner' | 'editor' | 'viewer'

export interface ProjectMemberItem {
  id: number
  user_id: number
  username: string
  email: string
  role: ProjectRoleType
  created_at: string
}

export interface AuditLogItem {
  id: number
  action: string
  resource_type: string
  resource_id: number | null
  user_id: number | null
  username: string
  detail: string | null
  ip_address: string
  project_id: number | null
  created_at: string
}

export interface PaginatedAuditLogs {
  items: AuditLogItem[]
  total: number
  page: number
  page_size: number
}

export const projectMemberApi = {
  list: (projectId: number) =>
    http.get<unknown, ProjectMemberItem[]>(`/projects/${projectId}/members`),
  add: (projectId: number, body: { user_id: number; role: ProjectRoleType }) =>
    http.post<unknown, ProjectMemberItem>(`/projects/${projectId}/members`, body),
  update: (projectId: number, userId: number, role: ProjectRoleType) =>
    http.patch<unknown, ProjectMemberItem>(`/projects/${projectId}/members/${userId}`, { role }),
  remove: (projectId: number, userId: number) =>
    http.delete<unknown, void>(`/projects/${projectId}/members/${userId}`),
}

export const auditLogApi = {
  list: (params: {
    project_id?: number
    action?: string
    user_id?: number
    created_from?: string
    created_to?: string
    page?: number
    page_size?: number
  }) => http.get<unknown, PaginatedAuditLogs>('/audit-logs', { params }),
  export: (params: {
    project_id?: number
    action?: string
    user_id?: number
    created_from?: string
    created_to?: string
    limit?: number
  }) => http.get<unknown, Blob>('/audit-logs/export', { params, responseType: 'blob' }),
}

export const requirementsApi = {
  list: (params?: {
    project_id?: number
    status?: RequirementStatusType
    keyword?: string
    page?: number
    page_size?: number
  }) => http.get<unknown, RequirementListResult>('/requirements', { params }),
  parse: (body: { project_id: number; text: string }) =>
    http.post<unknown, RequirementParseResult>('/requirements/parse', body),
  create: (body: RequirementCreatePayload) =>
    http.post<unknown, RequirementDetailItem>('/requirements', body),
  get: (id: number) => http.get<unknown, RequirementDetailItem>(`/requirements/${id}`),
  update: (id: number, body: RequirementUpdatePayload) =>
    http.patch<unknown, RequirementDetailItem>(`/requirements/${id}`, body),
  delete: (id: number) => http.delete<unknown, { deleted: boolean; id: number }>(`/requirements/${id}`),
  linkCase: (id: number, body: RequirementCaseLinkPayload) =>
    http.post<unknown, RequirementCaseLinkItem>(`/requirements/${id}/case-links`, body),
  unlinkCase: (id: number, linkId: number) =>
    http.delete<unknown, { deleted: boolean; id: number }>(`/requirements/${id}/case-links/${linkId}`),
  impact: (id: number) => http.get<unknown, RequirementImpactItem>(`/requirements/${id}/impact`),
}

export const knowledgeApi = {
  list: (params?: {
    project_id?: number
    keyword?: string
    source_type?: KnowledgeSourceType
    status?: KnowledgeStatusType
    page?: number
    page_size?: number
  }) => http.get<unknown, KnowledgeListResult>('/knowledge', { params }),
  get: (id: number) => http.get<unknown, KnowledgeDetailItem>(`/knowledge/${id}`),
  create: (body: KnowledgeSavePayload) => http.post<unknown, KnowledgeDetailItem>('/knowledge', body),
  update: (id: number, body: KnowledgeUpdatePayload) => http.patch<unknown, KnowledgeDetailItem>(`/knowledge/${id}`, body),
  delete: (id: number) => http.delete<unknown, { deleted: boolean; id: number }>(`/knowledge/${id}`),
}
