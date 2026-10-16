/**
 * 云原生弹性测试集群、多环境漂移治理、LLM 测试探索与发版门禁 API 客户端 (v4.2.0 / v4.3.0)
 */
import http from './http'

// --- Phase 1: 弹性集群与分片 ---
export interface ScalingDecision {
  decision_id: string
  action: 'SCALE_UP' | 'SCALE_DOWN' | 'NOOP' | 'QUOTA_BLOCKED'
  current_replicas: number
  desired_replicas: number
  allocated_replicas: number
  queue_depth: number
  reason: string
  arbitration_status: 'SUFFICIENT' | 'ARBITRATED_DEGRADED' | 'EXHAUSTED'
  cpu_utilization_estimate_pct: number
  memory_utilization_estimate_pct: number
  created_at: string
}

export interface ClusterStatus {
  current_active_replicas: number
  min_replicas: number
  max_replicas: number
  allocatable_cpu_cores: number
  allocatable_memory_gib: number
  used_cpu_cores: number
  used_memory_gib: number
  cpu_usage_pct: number
  memory_usage_pct: number
  last_scale_time: string | null
  total_scaling_events: number
}

export const elasticWorkerAutoscalerApi = {
  evaluate(data: {
    queue_depth: number
    current_replicas?: number
    allocatable_cpu_cores?: number
    allocatable_memory_gib?: number
    target_concurrency_per_worker?: number
  }): Promise<{ message: string; decision: ScalingDecision }> {
    return http.post('/cluster/autoscaler/evaluate', data)
  },
  apply(data: { queue_depth: number; force_replicas?: number }): Promise<{
    status: string
    decision: ScalingDecision
    active_replicas: number
    message: string
  }> {
    return http.post('/cluster/autoscaler/apply', data)
  },
  getStatus(): Promise<ClusterStatus> {
    return http.get('/cluster/autoscaler/status')
  },
  getEvents(params?: { limit?: number }): Promise<{ total: number; events: ScalingDecision[] }> {
    return http.get('/cluster/autoscaler/events', { params })
  },
  clearEvents(): Promise<{ message: string }> {
    return http.delete('/cluster/autoscaler/events')
  },
}

export interface ShardBucket {
  shard_index: number
  assigned_node_id: string
  case_ids: string[]
  case_count: number
  estimated_duration_ms: number
}

export interface ShardingPlanResult {
  plan_id: string
  total_cases: number
  total_shards: number
  total_estimated_duration_ms: number
  makespan_ms: number
  min_shard_duration_ms: number
  avg_shard_duration_ms: number
  balance_score_pct: number
  shards: ShardBucket[]
  created_at: string
}

export const testSuiteShardingApi = {
  calculatePlan(data: {
    cases: Array<{
      case_id: string
      case_name: string
      historical_duration_ms?: number
      priority?: string
      tags?: string[]
    }>
    total_shards?: number
    node_ids?: string[]
  }): Promise<{ message: string; plan: ShardingPlanResult }> {
    return http.post('/cluster/sharding/plan', data)
  },
  rebalanceDetect(data: {
    shard_progress: Array<{
      shard_index: number
      node_id: string
      elapsed_ms: number
      remaining_cases: number
      total_cases: number
    }>
  }): Promise<{
    has_straggler: boolean
    stragglers: Array<{
      shard_index: number
      node_id: string
      elapsed_ms: number
      remaining_cases: number
      reason: string
    }>
    recommendation: string
    checked_at: string
  }> {
    return http.post('/cluster/sharding/rebalance-detect', data)
  },
  listPlans(params?: { limit?: number }): Promise<{ total: number; plans: ShardingPlanResult[] }> {
    return http.get('/cluster/sharding/plans', { params })
  },
}

export interface EphemeralEnvironment {
  env_id: string
  env_name: string
  namespace: string
  branch_or_pr: string
  creator: string
  services: string[]
  cpu_limit_cores: number
  memory_limit_gib: number
  status: 'PROVISIONING' | 'READY' | 'IN_USE' | 'TEARING_DOWN' | 'DESTROYED'
  ttl_seconds: number
  remaining_ttl_seconds: number
  is_expired: boolean
  created_at: string
  expires_at: string
  destroyed_at?: string | null
  teardown_summary?: Record<string, any>
}

export const ephemeralTestEnvApi = {
  provision(data: {
    branch_or_pr: string
    services?: string[]
    cpu_limit_cores?: number
    memory_limit_gib?: number
    ttl_seconds?: number
  }): Promise<{ message: string; env: EphemeralEnvironment }> {
    return http.post('/cluster/ephemeral-env/provision', data)
  },
  extendLease(envId: string, data: { extra_seconds: number }): Promise<{ message: string; env: EphemeralEnvironment }> {
    return http.post(`/cluster/ephemeral-env/${envId}/extend-lease`, data)
  },
  teardown(envId: string): Promise<{ success: boolean; message: string; env?: EphemeralEnvironment }> {
    return http.post(`/cluster/ephemeral-env/${envId}/teardown`)
  },
  reclaimExpired(): Promise<{ message: string; result: Record<string, any> }> {
    return http.post('/cluster/ephemeral-env/reclaim-expired')
  },
  listEnvs(params?: { limit?: number; active_only?: boolean }): Promise<{ total: number; environments: EphemeralEnvironment[] }> {
    return http.get('/cluster/ephemeral-env/list', { params })
  },
  getEnv(envId: string): Promise<{ env: EphemeralEnvironment }> {
    return http.get(`/cluster/ephemeral-env/${envId}`)
  },
}

// --- Phase 2: 配置与 Schema 漂移 ---
export interface ConfigDriftItem {
  key: string
  base_value: any
  target_value: any
  drift_type: 'MISSING_IN_TARGET' | 'EXTRA_IN_TARGET' | 'VALUE_MISMATCH' | 'SECURITY_SENSITIVE_LEAK'
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'IDENTICAL'
  risk_explanation: string
  remediation_suggestion: string
}

export interface ConfigDriftReport {
  report_id: string
  service_name: string
  base_env: string
  target_env: string
  total_keys_checked: number
  identical_count: number
  drift_count: number
  highest_severity: string
  consistency_score_pct: number
  drifts: ConfigDriftItem[]
  created_at: string
}

export const multiEnvConfigDriftApi = {
  registerSnapshot(data: { env_name: string; service_name: string; configs: Record<string, any> }): Promise<any> {
    return http.post('/env-drift/config/register-snapshot', data)
  },
  compare(data: {
    service_name: string
    base_env?: string
    target_env?: string
    base_configs?: Record<string, any>
    target_configs?: Record<string, any>
  }): Promise<{ message: string; report: ConfigDriftReport }> {
    return http.post('/env-drift/config/compare', data)
  },
  listReports(params?: { limit?: number }): Promise<{ total: number; reports: ConfigDriftReport[] }> {
    return http.get('/env-drift/config/reports', { params })
  },
}

export interface SchemaDriftItem {
  table_name: string
  object_name: string
  drift_type: string
  severity: string
  base_detail?: string | null
  target_detail?: string | null
  risk_explanation: string
  remediation_ddl: string
}

export interface SchemaDriftReport {
  report_id: string
  database_name: string
  base_env: string
  target_env: string
  total_tables_checked: number
  identical_tables_count: number
  drift_items_count: number
  highest_severity: string
  compatibility_rate_pct: number
  remediation_ddl_script: string
  drifts: SchemaDriftItem[]
  created_at: string
}

export const dbSchemaDriftApi = {
  compare(data: {
    database_name: string
    base_env?: string
    target_env?: string
    base_tables?: any[]
    target_tables?: any[]
  }): Promise<{ message: string; report: SchemaDriftReport }> {
    return http.post('/env-drift/schema/compare', data)
  },
  listReports(params?: { limit?: number }): Promise<{ total: number; reports: SchemaDriftReport[] }> {
    return http.get('/env-drift/schema/reports', { params })
  },
}

export interface IaCComplianceReport {
  report_id: string
  target_name: string
  total_resources_scanned: number
  total_violations_count: number
  critical_count: number
  high_count: number
  medium_count: number
  low_count: number
  compliance_score_pct: number
  verdict: 'PASS' | 'WARNING' | 'BLOCKED'
  violations: Array<{
    rule_id: string
    rule_name: string
    severity: string
    resource_kind: string
    resource_name: string
    violation_message: string
    remediation_guidance: string
  }>
  created_at: string
}

export const iacComplianceScannerApi = {
  scan(data: { target_name?: string; manifests: any[] }): Promise<{ message: string; report: IaCComplianceReport }> {
    return http.post('/env-drift/iac-compliance/scan', data)
  },
  getRules(): Promise<{ total: number; rules: any[] }> {
    return http.get('/env-drift/iac-compliance/rules')
  },
  listReports(params?: { limit?: number }): Promise<{ total: number; reports: IaCComplianceReport[] }> {
    return http.get('/env-drift/iac-compliance/reports', { params })
  },
}

// --- Phase 3: LLM 用例生成与变异 ---
export interface SynthesizedE2ETestCase {
  case_id: string
  spec_title: string
  description: string
  steps_count: number
  steps: Array<{
    step_index: number
    step_name: string
    endpoint: string
    method: string
    request_payload: Record<string, any>
    extracted_variables: Record<string, string>
    assertions: any[]
  }>
  generated_python_script: string
  flow_completeness_score_pct: number
  created_at: string
}

export const llmSpecCaseSynthesizerApi = {
  generate(data: {
    spec_title: string
    business_flow_description?: string
    endpoints?: any[]
  }): Promise<{ message: string; case: SynthesizedE2ETestCase }> {
    return http.post('/llm-testing/synthesize-cases/generate', data)
  },
  listCases(params?: { limit?: number }): Promise<{ total: number; cases: SynthesizedE2ETestCase[] }> {
    return http.get('/llm-testing/synthesize-cases/cases', { params })
  },
}

export interface SyntheticDatasetBatch {
  batch_id: string
  dataset_name: string
  total_rows: number
  positive_count: number
  boundary_count: number
  negative_count: number
  fields_count: number
  rows: Array<{
    row_index: number
    mode: string
    data: Record<string, any>
    is_expected_valid: boolean
    anomaly_field?: string | null
    anomaly_reason?: string | null
  }>
  created_at: string
}

export const syntheticTestDataApi = {
  generate(data: {
    dataset_name?: string
    rules: Array<{
      field_name: string
      data_type?: string
      min_value?: number
      max_value?: number
      min_length?: number
      max_length?: number
      enum_values?: string[]
      nullable?: boolean
    }>
    row_count?: number
  }): Promise<{ message: string; batch: SyntheticDatasetBatch }> {
    return http.post('/llm-testing/synthetic-data/generate', data)
  },
  listBatches(params?: { limit?: number }): Promise<{ total: number; batches: SyntheticDatasetBatch[] }> {
    return http.get('/llm-testing/synthetic-data/batches', { params })
  },
}

export interface FuzzingExplorationSession {
  session_id: string
  target_endpoint: string
  target_method: string
  total_mutations_count: number
  flaws_count: number
  critical_count: number
  high_count: number
  robustness_score_pct: number
  findings: Array<{
    flaw_id: string
    strategy: string
    flaw_type: string
    severity: string
    mutated_key: string
    mutated_value: any
    status_code: number
    response_excerpt: string
    reproduction_curl: string
  }>
  created_at: string
}

export const autonomousApiFuzzingApi = {
  run(data: {
    endpoint: string
    method?: string
    base_payload?: Record<string, any>
    strategies?: string[]
  }): Promise<{ message: string; session: FuzzingExplorationSession }> {
    return http.post('/llm-testing/fuzzing-explore/run', data)
  },
  getStrategies(): Promise<{ strategies: Array<{ strategy: string; name: string }> }> {
    return http.get('/llm-testing/fuzzing-explore/strategies')
  },
  listSessions(params?: { limit?: number }): Promise<{ total: number; sessions: FuzzingExplorationSession[] }> {
    return http.get('/llm-testing/fuzzing-explore/sessions', { params })
  },
}

// --- Phase 4: 质量健康评分与发版门禁 ---
export interface QualityHealthScoreResult {
  report_id: string
  target_name: string
  composite_score: number
  grade: 'A+' | 'A' | 'B' | 'C'
  dimension_scores: Record<string, number>
  dimension_weights: Record<string, number>
  primary_risk_factors: string[]
  optimization_recommendations: string[]
  created_at: string
}

export const qualityHealthScoreApi = {
  calculate(data: {
    target_name?: string
    test_pass_rate_pct?: number
    code_coverage_pct?: number
    mutation_score_pct?: number
    p0_defects_count?: number
    p1_defects_count?: number
    p2_defects_count?: number
    change_risk_score?: number
    compliance_score_pct?: number
  }): Promise<{ message: string; report: QualityHealthScoreResult }> {
    return http.post('/gatekeeper/health-score/calculate', data)
  },
  listReports(params?: { limit?: number }): Promise<{ total: number; reports: QualityHealthScoreResult[] }> {
    return http.get('/gatekeeper/health-score/reports', { params })
  },
}

export interface ReleaseGateVerdictRecord {
  release_id: string
  target_version: string
  verdict: 'GO' | 'CAUTION' | 'NO_GO' | 'WAIVED_GO'
  quality_score: number
  blocking_reasons: string[]
  warning_reasons: string[]
  is_waived: boolean
  waiver_info?: {
    approver: string
    waiver_reason: string
    rollback_plan: string
    waived_at: string
  } | null
  created_at: string
}

export const releaseGateVerdictApi = {
  evaluate(data: {
    target_version?: string
    quality_score: number
    p0_defects_count?: number
    p1_defects_count?: number
    critical_security_flaws_count?: number
    test_pass_rate_pct?: number
  }): Promise<{ message: string; record: ReleaseGateVerdictRecord }> {
    return http.post('/gatekeeper/release-verdict/evaluate', data)
  },
  waive(releaseId: string, data: { waiver_reason: string; rollback_plan: string }): Promise<{
    success: boolean
    message: string
    record?: ReleaseGateVerdictRecord
  }> {
    return http.post(`/gatekeeper/release-verdict/${releaseId}/waive`, data)
  },
  revokeWaiver(releaseId: string): Promise<{ success: boolean; message: string; record?: ReleaseGateVerdictRecord }> {
    return http.post(`/gatekeeper/release-verdict/${releaseId}/revoke-waiver`)
  },
  listRecords(params?: { limit?: number }): Promise<{ total: number; records: ReleaseGateVerdictRecord[] }> {
    return http.get('/gatekeeper/release-verdict/records', { params })
  },
}

export interface ComprehensiveAuditReport {
  report_id: string
  target_version: string
  project_name: string
  generated_by: string
  overall_verdict: string
  composite_health_score: number
  health_grade: string
  execution_summary: Record<string, any>
  config_and_schema_drift: Record<string, any>
  iac_compliance_summary: Record<string, any>
  fuzzing_vulnerability_summary: Record<string, any>
  gatekeeper_details: Record<string, any>
  sha256_audit_fingerprint: string
  created_at: string
}

export const comprehensiveAuditReportApi = {
  generate(data: {
    target_version?: string
    project_name?: string
    execution_data?: Record<string, any>
    health_data?: Record<string, any>
    drift_data?: Record<string, any>
    iac_data?: Record<string, any>
    fuzzing_data?: Record<string, any>
    gatekeeper_data?: Record<string, any>
  }): Promise<{ message: string; report: ComprehensiveAuditReport }> {
    return http.post('/gatekeeper/audit-report/generate', data)
  },
  verify(reportId: string, data?: { tampered_data?: Record<string, any> }): Promise<{
    valid: boolean
    message: string
    fingerprint?: string
    original_fingerprint?: string
    computed_fingerprint?: string
  }> {
    return http.post(`/gatekeeper/audit-report/${reportId}/verify`, data || {})
  },
  getMarkdown(reportId: string): Promise<string> {
    return http.get(`/gatekeeper/audit-report/reports/${reportId}/markdown`, { responseType: 'text' })
  },
  listReports(params?: { limit?: number }): Promise<{ total: number; reports: ComprehensiveAuditReport[] }> {
    return http.get('/gatekeeper/audit-report/reports', { params })
  },
}
