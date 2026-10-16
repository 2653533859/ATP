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

export interface TestShardItem {
  shard_index: number
  case_ids: number[]
  cases_count: number
  estimated_duration_sec: number
  worker_assigned_id?: string | null
}

export interface DynamicShardingReportItem {
  sharding_id: string
  target_shards_count: number
  actual_shards_count: number
  total_cases_count: number
  total_estimated_duration_sec: number
  max_shard_duration_sec: number
  min_shard_duration_sec: number
  duration_variance: number
  theoretical_speedup_ratio: number
  shards: TestShardItem[]
  created_at: string
}

export interface PartitionTestsRequest {
  case_ids: number[]
  target_shards_count?: number
  case_duration_history?: Record<number, number>
  default_case_duration_sec?: number
}

export type RiskLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'

export interface RiskDimensionBreakdownItem {
  dimension_name: string
  score: number
  weight: number
  raw_metrics: Record<string, any>
  description: string
}

export interface ChangeRiskReportItem {
  risk_id: string
  overall_risk_score: number
  risk_level: RiskLevel
  dimensions: {
    volume: RiskDimensionBreakdownItem
    complexity: RiskDimensionBreakdownItem
    criticality: RiskDimensionBreakdownItem
  }
  high_risk_files: string[]
  risk_factors_summary: string[]
  recommended_action: string
  evaluated_at: string
}

export interface EvaluateChangeRiskRequest {
  diff_text: string
  file_sources?: Record<string, string>
  critical_patterns?: string[]
  weight_volume?: number
  weight_complexity?: number
  weight_criticality?: number
}

export type SuppressionAction = 'normal_passthrough' | 'retry_attached' | 'isolated_to_quarantine' | 'tagged_observation'
export type FlakyFilterMode = 'auto_adaptive' | 'quarantine_strict' | 'retry_only'

export interface CaseSuppressionEvaluationItem {
  case_id: number
  case_name: string
  is_flaky: boolean
  flakiness_score: number
  failure_rate: number
  total_runs_analyzed: number
  action: SuppressionAction
  suppression_reason: string
  retry_count_recommended: number
}

export interface FlakySuppressionReportItem {
  filter_id: string
  mode: FlakyFilterMode
  total_cases_evaluated: number
  stable_cases_count: number
  flaky_cases_count: number
  isolated_cases_count: number
  retried_cases_count: number
  suppression_ratio_pct: number
  actionable_case_ids: number[]
  quarantined_case_ids: number[]
  evaluations: CaseSuppressionEvaluationItem[]
  created_at: string
}

export interface FilterFlakyTestsRequest {
  cases: Array<{ case_id: number; case_name?: string }>
  mode?: FlakyFilterMode
  flakiness_threshold?: number
  historical_stats?: Record<number, any>
}

export interface GovernanceOverrideRequest {
  case_id: number
  action: SuppressionAction
  reason: string
  ticket_id?: string | null
}

export type MutationOperatorType = 'ROR' | 'LCR' | 'AOR' | 'RVO' | 'BVO'

export interface MutantItem {
  mutant_id: string
  file_path: string
  line_number: number
  operator_type: MutationOperatorType
  original_token: string
  mutated_token: string
  original_line: string
  mutated_line: string
  mutated_code: string
  description: string
}

export interface MutationGenerationReport {
  generation_id: string
  file_path: string
  total_mutants_generated: number
  operator_distribution: Record<string, number>
  target_lines_count: number
  mutants: MutantItem[]
  created_at: string
}

export interface GenerateMutantsRequest {
  source_code: string
  file_path?: string
  target_lines?: number[]
  max_mutants?: number
}

export type MutantStatus = 'KILLED' | 'SURVIVED' | 'TIMED_OUT' | 'ERROR'

export interface MutantExecutionResult {
  mutant_id: string
  status: MutantStatus
  killing_test_case_id: number | null
  killing_test_case_name: string | null
  execution_duration_ms: number
  error_message: string | null
  line_number: number
  operator_type: string
  description: string
}

export interface MutationExecutionRunReport {
  run_id: string
  total_mutants_tested: number
  killed_count: number
  survived_count: number
  timed_out_count: number
  error_count: number
  kill_rate_pct: number
  survived_mutant_ids: string[]
  results: MutantExecutionResult[]
  executed_at: string
}

export interface RunMutationExecutionRequest {
  mutant_ids: string[]
  test_cases?: Array<Record<string, any>>
  timeout_sec_per_mutant?: number
}

export type AssertionAdequacyLevel = 'EXCELLENT' | 'ADEQUATE' | 'INSUFFICIENT' | 'WEAK'

export interface OperatorScoreBreakdown {
  operator_type: string
  total_mutants: number
  killed_mutants: number
  survived_mutants: number
  operator_mutation_score_pct: number
}

export interface AssertionBlindspotItem {
  mutant_id: string
  file_path: string
  line_number: number
  operator_type: string
  original_line: string
  mutated_line: string
  description: string
  suggested_assertion_fix: string
}

export interface MutationScoreReport {
  score_id: string
  execution_run_id: string
  mutation_score_pct: number
  adequacy_level: AssertionAdequacyLevel
  total_mutants: number
  killed_count: number
  survived_count: number
  timed_out_count: number
  operator_breakdowns: Record<string, OperatorScoreBreakdown>
  blindspots: AssertionBlindspotItem[]
  summary_verdict: string
  calculated_at: string
}

export interface CalculateMutationScoreRequest {
  execution_run_id?: string
  mutant_execution_results?: Array<Record<string, any>>
}

export type MergeGateVerdict = 'MERGE_APPROVED' | 'MERGE_BLOCKED' | 'CONDITIONAL_PASS'

export interface GateRuleEvaluation {
  rule_id: string
  rule_name: string
  passed: boolean
  severity: 'blocking' | 'warning'
  measured_value: any
  threshold_value: any
  message: string
}

export interface PrGateVerdictReport {
  gate_id: string
  pr_id: string
  commit_sha: string
  author: string
  target_branch: string
  verdict: MergeGateVerdict
  is_mergeable: boolean
  overall_compliance_score: number
  blocking_reasons: string[]
  warning_reasons: string[]
  evaluated_rules: GateRuleEvaluation[]
  remediation_steps: string[]
  evaluated_at: string
}

export interface EvaluatePrGateRequest {
  pr_id: string
  commit_sha: string
  author?: string
  target_branch?: string
  test_pass_rate_pct?: number
  test_failed_cases_count?: number
  risk_level?: string
  mutation_score_pct?: number | null
  has_dual_approvals?: boolean
  min_pass_rate_threshold?: number
  min_mutation_score_threshold?: number
}

export type GitPlatformType = 'github' | 'gitlab' | 'gitea' | 'generic_markdown'

export interface PrCommentPayload {
  comment_id: string
  pr_id: string
  platform: GitPlatformType
  repo_name: string
  markdown_body: string
  verdict: MergeGateVerdict
  delivered_successfully: boolean
  created_at: string
}

export interface GeneratePrCommentRequest {
  gate_id: string
  bot_header_title?: string
}

export interface DispatchPrCommentRequest {
  gate_id: string
  repo_name?: string
  platform?: GitPlatformType
  bot_header_title?: string
  simulate_success?: boolean
}

export type PipelineStageStatus = 'PASSED' | 'BLOCKED' | 'WARNING'

export interface CheckpointStageResult {
  stage_name: string
  status: PipelineStageStatus
  duration_ms: number
  summary: string
  details?: Record<string, any>
}

export interface CheckpointExecutionReport {
  checkpoint_id: string
  pipeline_name: string
  commit_sha: string
  pr_id: string
  exit_code: number
  overall_status: PipelineStageStatus
  stages: CheckpointStageResult[]
  remediation_summary: string[]
  console_log_output: string
  executed_at: string
}

export interface RunPipelineCheckpointRequest {
  diff_text: string
  pipeline_name?: string
  commit_sha?: string
  pr_id?: string
  author?: string
  target_branch?: string
  file_sources?: Record<string, string>
  selection_strategy?: string
  mock_test_pass_rate_pct?: number
  mock_test_failed_cases_count?: number
  mutation_score_pct?: number | null
  has_dual_approvals?: boolean
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

  partitionShards(data: PartitionTestsRequest): Promise<{ message: string; report: DynamicShardingReportItem }> {
    return http.post('/ci-impact/sharding/partition', data)
  },

  listShardingReports(): Promise<{ total: number; reports: DynamicShardingReportItem[] }> {
    return http.get('/ci-impact/sharding/reports')
  },

  getShardingReport(shardingId: string): Promise<DynamicShardingReportItem> {
    return http.get(`/ci-impact/sharding/reports/${shardingId}`)
  },

  evaluateRisk(data: EvaluateChangeRiskRequest): Promise<{ message: string; report: ChangeRiskReportItem }> {
    return http.post('/ci-impact/risk-score/evaluate', data)
  },

  listRiskReports(): Promise<{ total: number; reports: ChangeRiskReportItem[] }> {
    return http.get('/ci-impact/risk-score/reports')
  },

  getRiskReport(riskId: string): Promise<ChangeRiskReportItem> {
    return http.get(`/ci-impact/risk-score/reports/${riskId}`)
  },

  filterFlakyTests(data: FilterFlakyTestsRequest): Promise<{ message: string; report: FlakySuppressionReportItem }> {
    return http.post('/ci-impact/flaky-filter/filter', data)
  },

  listFlakyFilterReports(): Promise<{ total: number; reports: FlakySuppressionReportItem[] }> {
    return http.get('/ci-impact/flaky-filter/reports')
  },

  getFlakyFilterReport(filterId: string): Promise<FlakySuppressionReportItem> {
    return http.get(`/ci-impact/flaky-filter/reports/${filterId}`)
  },

  setGovernanceOverride(data: GovernanceOverrideRequest): Promise<{ message: string; case_id: number; action: string }> {
    return http.post('/ci-impact/flaky-filter/governance/override', data)
  },

  generateMutants(data: GenerateMutantsRequest): Promise<{ message: string; report: MutationGenerationReport }> {
    return http.post('/ci-impact/mutations/generate', data)
  },

  listMutationReports(): Promise<{ total: number; reports: MutationGenerationReport[] }> {
    return http.get('/ci-impact/mutations/reports')
  },

  getMutationReport(generationId: string): Promise<MutationGenerationReport> {
    return http.get(`/ci-impact/mutations/reports/${generationId}`)
  },

  getMutant(mutantId: string): Promise<MutantItem> {
    return http.get(`/ci-impact/mutations/${mutantId}`)
  },

  runMutationExecution(data: RunMutationExecutionRequest): Promise<{ message: string; report: MutationExecutionRunReport }> {
    return http.post('/ci-impact/mutations/execute/run', data)
  },

  listMutationExecutionReports(): Promise<{ total: number; reports: MutationExecutionRunReport[] }> {
    return http.get('/ci-impact/mutations/execute/reports')
  },

  getMutationExecutionReport(runId: string): Promise<MutationExecutionRunReport> {
    return http.get(`/ci-impact/mutations/execute/reports/${runId}`)
  },

  calculateMutationScore(data: CalculateMutationScoreRequest): Promise<{ message: string; report: MutationScoreReport }> {
    return http.post('/ci-impact/mutations/score/calculate', data)
  },

  listMutationScoreReports(): Promise<{ total: number; reports: MutationScoreReport[] }> {
    return http.get('/ci-impact/mutations/score/reports')
  },

  getMutationScoreReport(scoreId: string): Promise<MutationScoreReport> {
    return http.get(`/ci-impact/mutations/score/reports/${scoreId}`)
  },

  evaluatePrGate(data: EvaluatePrGateRequest): Promise<{ message: string; report: PrGateVerdictReport }> {
    return http.post('/ci-impact/pr-gate/evaluate', data)
  },

  listPrGateReports(): Promise<{ total: number; reports: PrGateVerdictReport[] }> {
    return http.get('/ci-impact/pr-gate/reports')
  },

  getPrGateReport(gateId: string): Promise<PrGateVerdictReport> {
    return http.get(`/ci-impact/pr-gate/reports/${gateId}`)
  },

  generatePrComment(data: GeneratePrCommentRequest): Promise<{ message: string; gate_id: string; markdown: string }> {
    return http.post('/ci-impact/pr-bot/generate-comment', data)
  },

  dispatchPrComment(data: DispatchPrCommentRequest): Promise<{ message: string; comment: PrCommentPayload }> {
    return http.post('/ci-impact/pr-bot/dispatch', data)
  },

  listPrComments(): Promise<{ total: number; comments: PrCommentPayload[] }> {
    return http.get('/ci-impact/pr-bot/comments')
  },

  getPrComment(commentId: string): Promise<PrCommentPayload> {
    return http.get(`/ci-impact/pr-bot/comments/${commentId}`)
  },

  runPipelineCheckpoint(data: RunPipelineCheckpointRequest): Promise<{ message: string; report: CheckpointExecutionReport }> {
    return http.post('/ci-impact/checkpoint/run', data)
  },

  listCheckpointReports(): Promise<{ total: number; reports: CheckpointExecutionReport[] }> {
    return http.get('/ci-impact/checkpoint/reports')
  },

  getCheckpointReport(checkpointId: string): Promise<CheckpointExecutionReport> {
    return http.get(`/ci-impact/checkpoint/reports/${checkpointId}`)
  },
}
