/**
 * 生产全链路压测、影子流量隔离、单元化调度与防雪崩熔断 API 客户端 (v4.6.0 / v4.7.0)
 */
import http from './http'

// --- Phase 1: 影子流量染色、库表防污染与 MQ 分流 ---
export interface ServiceHopRecord {
  hop_order: number
  service_name: string
  protocol: string
  received_shadow_flag: boolean
  retained_trace_id: string | null
  is_taint_lost: boolean
}

export interface ShadowTaintReport {
  report_id: string
  trace_id: string
  total_hops_count: number
  lost_hops_count: number
  verdict: 'FULL_PROPAGATION_SUCCESS' | 'TAINT_LEAKAGE_DETECTED' | 'CORRUPTED_METADATA'
  integrity_score_pct: number
  has_leakage_risk: boolean
  hops: ServiceHopRecord[]
  remediation_advice: string[]
  created_at: string
}

export interface ShadowTableMapping {
  mapping_id: string
  production_table: string
  shadow_table: string
  isolation_strategy: 'SHADOW_TABLE' | 'SHADOW_DATABASE' | 'SHADOW_SCHEMA'
  is_active: boolean
}

export interface SqlRoutingItem {
  item_id: string
  original_sql: string
  is_shadow_traffic: boolean
  is_write_operation: boolean
  detected_target_table: string
  verdict: 'ROUTED_TO_SHADOW' | 'BLOCKED_PROD_POLLUTION_ATTEMPT' | 'SAFE_PROD_PASSTHROUGH' | 'READ_ONLY_SAFE'
  rewritten_sql: string | null
  explanation: string
}

export interface DbIsolationReport {
  report_id: string
  target_cluster: string
  total_queries_checked: number
  routed_to_shadow_count: number
  blocked_pollution_count: number
  safe_passthrough_count: number
  isolation_safety_score_pct: number
  has_critical_pollution_risk: boolean
  inspections: SqlRoutingItem[]
  created_at: string
}

export interface MqRouteRule {
  rule_id: string
  production_topic: string
  shadow_topic: string
  dead_letter_queue: string
  bypass_action: 'REDIRECT_SHADOW_CONSUMER' | 'MOCK_DISPATCH' | 'DROP_SILENTLY'
  is_active: boolean
}

export interface MqRoutingDecision {
  message_id: string
  original_topic: string
  is_shadow: boolean
  routed_topic: string
  is_redirected: boolean
  bypassed_action: string | null
  explanation: string
}

export interface MqShuntingReport {
  report_id: string
  cluster_name: string
  total_messages_processed: number
  shadow_messages_count: number
  redirected_to_shadow_count: number
  bypassed_mock_count: number
  unmapped_leak_count: number
  shunting_safety_score_pct: number
  decisions: MqRoutingDecision[]
  created_at: string
}

export async function injectShadowTaint(payload: {
  protocol?: string
  headers?: Record<string, any>
  trace_id?: string
  cluster_tag?: string
}): Promise<{ message: string; protocol: string; injected_headers: Record<string, any> }> {
  const resp = await http.post('/stress/shadow-traffic/taint/inject', payload)
  return resp.data
}

export async function verifyTracePropagation(payload: {
  trace_id: string
  hop_traces: Array<{ service_name: string; protocol?: string; headers?: Record<string, any> }>
}): Promise<{ message: string; report: ShadowTaintReport }> {
  const resp = await http.post('/stress/shadow-traffic/taint/verify-propagation', payload)
  return resp.data
}

export async function listShadowTaintReports(limit = 50): Promise<{ total: number; reports: ShadowTaintReport[] }> {
  const resp = await http.get('/stress/shadow-traffic/taint/reports', { params: { limit } })
  return resp.data
}

export async function inspectSqlIsolation(payload: {
  target_cluster: string
  queries: Array<{ sql: string; is_shadow_traffic?: boolean }>
}): Promise<{ message: string; report: DbIsolationReport }> {
  const resp = await http.post('/stress/shadow-traffic/db-isolation/inspect', payload)
  return resp.data
}

export async function registerShadowMapping(payload: {
  production_table: string
  shadow_table: string
  strategy?: string
}): Promise<{ message: string; mapping: ShadowTableMapping }> {
  const resp = await http.post('/stress/shadow-traffic/db-isolation/mappings', payload)
  return resp.data
}

export async function listShadowMappings(): Promise<{ total: number; mappings: ShadowTableMapping[] }> {
  const resp = await http.get('/stress/shadow-traffic/db-isolation/mappings')
  return resp.data
}

export async function listDbIsolationReports(limit = 50): Promise<{ total: number; reports: DbIsolationReport[] }> {
  const resp = await http.get('/stress/shadow-traffic/db-isolation/reports', { params: { limit } })
  return resp.data
}

export async function routeMqMessages(payload: {
  cluster_name: string
  messages: Array<{ message_id?: string; topic: string; headers?: Record<string, any>; is_shadow_traffic?: boolean }>
}): Promise<{ message: string; report: MqShuntingReport }> {
  const resp = await http.post('/stress/shadow-traffic/mq-shunting/route', payload)
  return resp.data
}

export async function registerMqRule(payload: {
  production_topic: string
  shadow_topic: string
  dead_letter_queue: string
  bypass_action?: string
}): Promise<{ message: string; rule: MqRouteRule }> {
  const resp = await http.post('/stress/shadow-traffic/mq-shunting/rules', payload)
  return resp.data
}

export async function listMqRules(): Promise<{ total: number; rules: MqRouteRule[] }> {
  const resp = await http.get('/stress/shadow-traffic/mq-shunting/rules')
  return resp.data
}

export async function listMqShuntingReports(limit = 50): Promise<{ total: number; reports: MqShuntingReport[] }> {
  const resp = await http.get('/stress/shadow-traffic/mq-shunting/reports', { params: { limit } })
  return resp.data
}

// --- Phase 2: 单元化测试隔离与切流 ---
export interface CellDefinition {
  cell_id: string
  cell_name: string
  zone: string
  traffic_weight: number
  status: 'ACTIVE_PROD' | 'STRESS_ONLY' | 'DRAINING' | 'ISOLATED_FAILSAFE'
  allowed_shards: number[]
  is_stress_target: boolean
  active_connections_count?: number
}

export interface CellRoutingDecision {
  decision_id: string
  user_id: string | null
  is_shadow_traffic: boolean
  assigned_cell_id: string
  assigned_zone: string
  is_stress_cell: boolean
  shunting_reason: string
}

export interface CellTopologyReport {
  report_id: string
  total_cells_count: number
  active_prod_cells: number
  stress_cells_count: number
  isolated_cells_count: number
  cells: CellDefinition[]
  created_at: string
}

export interface CellEscapeReport {
  report_id: string
  topology_name: string
  total_edges_checked: number
  total_escapes_count: number
  shadow_escapes_count: number
  isolation_purity_score_pct: number
  is_strictly_cell_isolated: boolean
  violations: Array<{
    violation_id: string
    violation_type: string
    severity: string
    source_cell: string
    target_cell: string
    service_or_resource: string
    description: string
    remediation_suggestion: string
  }>
  created_at: string
}

export interface CellFailoverReport {
  drill_id: string
  failed_cell_id: string
  standby_cell_id: string
  traffic_shift_percentage: number
  total_rto_duration_ms: number
  estimated_packet_drop_pct: number
  verdict: 'FAILOVER_SUCCESS' | 'DEGRADED_FAILOVER' | 'FAILOVER_TIMEOUT'
  is_resilience_qualified: boolean
  timeline_phases: Array<{
    phase_name: string
    duration_ms: number
    status: string
    detail: string
  }>
  remediation_recommendations: string[]
  created_at: string
}

export async function routeCellDecision(payload: {
  user_id?: string
  is_shadow_traffic?: boolean
  headers?: Record<string, any>
}): Promise<{ message: string; decision: CellRoutingDecision }> {
  const resp = await http.post('/stress/cell-isolation/routing/decide', payload)
  return resp.data
}

export async function registerCell(payload: CellDefinition): Promise<{ message: string; cell: CellDefinition }> {
  const resp = await http.post('/stress/cell-isolation/routing/cells', payload)
  return resp.data
}

export async function listCells(): Promise<{ total: number; cells: CellDefinition[] }> {
  const resp = await http.get('/stress/cell-isolation/routing/cells')
  return resp.data
}

export async function updateCellWeights(weights: Record<string, number>): Promise<{ message: string; cells: CellDefinition[] }> {
  const resp = await http.post('/stress/cell-isolation/routing/weights', { weights })
  return resp.data
}

export async function getCellTopologyReport(): Promise<{ report: CellTopologyReport }> {
  const resp = await http.get('/stress/cell-isolation/routing/topology')
  return resp.data
}

export async function detectCellEscapes(payload: {
  topology_name: string
  invocation_edges: Array<{
    source_cell_id: string
    source_service: string
    target_cell_id: string
    target_service: string
    target_resource_type?: string
    is_shadow_traffic?: boolean
    is_shared_resource?: boolean
  }>
}): Promise<{ message: string; report: CellEscapeReport }> {
  const resp = await http.post('/stress/cell-isolation/escape/detect', payload)
  return resp.data
}

export async function listCellEscapeReports(limit = 50): Promise<{ total: number; reports: CellEscapeReport[] }> {
  const resp = await http.get('/stress/cell-isolation/escape/reports', { params: { limit } })
  return resp.data
}

export async function simulateCellFailover(payload: {
  failed_cell_id: string
  standby_cell_id: string
  traffic_shift_percentage?: number
  dns_switch_delay_ms?: number
  db_replication_lag_ms?: number
  route_convergence_delay_ms?: number
}): Promise<{ message: string; report: CellFailoverReport }> {
  const resp = await http.post('/stress/cell-isolation/failover/simulate', payload)
  return resp.data
}

export async function listFailoverReports(limit = 50): Promise<{ total: number; reports: CellFailoverReport[] }> {
  const resp = await http.get('/stress/cell-isolation/failover/reports', { params: { limit } })
  return resp.data
}

// --- Phase 3: 容量水位与防雪崩熔断 ---
export interface WatermarkItem {
  resource_id: string
  resource_type: string
  current_value: number
  capacity_limit: number
  utilization_rate_pct: number
  watermark_level: 'SAFE' | 'WARNING' | 'SATURATED' | 'EXHAUSTED'
  unit: string
  detail_metric_name: string
}

export interface CapacityWatermarkReport {
  report_id: string
  target_cluster_or_env: string
  total_resources_measured: number
  health_load_index_pct: number
  max_utilization_pct: number
  weakest_bottleneck_resource: string
  requires_avalanche_breaker: boolean
  watermarks: WatermarkItem[]
  remediation_actions: string[]
  created_at: string
}

export interface BottleneckReport {
  report_id: string
  scenario_name: string
  total_spans_analyzed: number
  p50_latency_ms: number
  p90_latency_ms: number
  p99_latency_ms: number
  total_bottlenecks_count: number
  primary_root_cause: string
  system_stress_health_score: number
  findings: Array<{
    finding_id: string
    cause_type: string
    severity: string
    culprit_service: string
    culprit_endpoint_or_sql: string
    measured_duration_ms: number
    impact_description: string
    optimization_recommendation: string
  }>
  created_at: string
}

export interface AvalancheBreakerReport {
  report_id: string
  scenario_name: string
  current_watermark_pct: number
  current_p99_latency_ms: number
  current_error_rate_pct: number
  is_circuit_broken: boolean
  circuit_state?: string
  final_decision: {
    decision_id: string
    breaker_state: string
    action: string
    throttle_ratio_pct: number
    trigger_reason: string
    suggested_safe_tps: number
  }
  remediation_instructions: string[]
  created_at: string
}

export async function meterCapacityWatermark(payload: {
  target_cluster_or_env: string
  metric_samples: Array<{
    resource_id: string
    resource_type?: string
    current_value: number
    capacity_limit: number
    unit?: string
    detail_metric_name?: string
  }>
}): Promise<{ message: string; report: CapacityWatermarkReport }> {
  const resp = await http.post('/stress/bottleneck-guardian/watermark/meter', payload)
  return resp.data
}

export async function listWatermarkReports(limit = 50): Promise<{ total: number; reports: CapacityWatermarkReport[] }> {
  const resp = await http.get('/stress/bottleneck-guardian/watermark/reports', { params: { limit } })
  return resp.data
}

export async function classifyBottlenecks(payload: {
  scenario_name: string
  spans: Array<{
    service_name: string
    endpoint_or_sql?: string
    duration_ms: number
    error_message?: string
    lock_wait_time_ms?: number
    thread_queue_depth?: number
    cpu_usage_pct?: number
  }>
}): Promise<{ message: string; report: BottleneckReport }> {
  const resp = await http.post('/stress/bottleneck-guardian/bottlenecks/classify', payload)
  return resp.data
}

export async function listBottleneckReports(limit = 50): Promise<{ total: number; reports: BottleneckReport[] }> {
  const resp = await http.get('/stress/bottleneck-guardian/bottlenecks/reports', { params: { limit } })
  return resp.data
}

export async function evaluateCircuitBreaker(payload: {
  scenario_name: string
  max_resource_watermark_pct: number
  p99_latency_ms?: number
  error_rate_pct?: number
  current_tps?: number
}): Promise<{ message: string; report: AvalancheBreakerReport }> {
  const resp = await http.post('/stress/bottleneck-guardian/circuit-breaker/evaluate', payload)
  return resp.data
}

export async function resetCircuitBreaker(): Promise<{ message: string; current_state: string }> {
  const resp = await http.post('/stress/bottleneck-guardian/circuit-breaker/reset')
  return resp.data
}

export async function getBreakerStatus(): Promise<{ current_state: string }> {
  const resp = await http.get('/stress/bottleneck-guardian/circuit-breaker/status')
  return resp.data
}

export async function listBreakerReports(limit = 50): Promise<{ total: number; reports: AvalancheBreakerReport[] }> {
  const resp = await http.get('/stress/bottleneck-guardian/circuit-breaker/reports', { params: { limit } })
  return resp.data
}

// --- Phase 4: 拐点分析、爆炸半径与全景复盘 ---
export interface StepLoadSamplePoint {
  step_index: number
  concurrency_threads: number
  measured_tps: number
  avg_latency_ms: number
  p99_latency_ms: number
  error_rate_pct: number
  zone: 'OPTIMAL_ZONE' | 'SATURATION_ZONE' | 'DEGRADED_OVERLOAD_ZONE'
}

export interface ThroughputKneeReport {
  report_id: string
  scenario_name: string
  total_steps_count: number
  peak_tps: number
  knee_point_concurrency: number
  knee_point_tps: number
  knee_point_latency_ms: number
  cliff_point_concurrency: number | null
  recommended_safe_concurrency: number
  step_samples: StepLoadSamplePoint[]
  capacity_planning_advice: string[]
  created_at: string
}

export interface StressBlastRadiusReport {
  report_id: string
  drill_id: string
  blast_radius_tier: 'TIER_1_ISOLATED' | 'TIER_2_CELL_BOUND' | 'TIER_3_SHARED_PERIPHERAL' | 'TIER_4_UNCONTROLLED_GLOBAL'
  safety_verdict: 'PASS_READY_FOR_STRESS' | 'CAUTION_MONITORED' | 'BLOCKED_HIGH_BLAST_RADIUS'
  safety_score_pct: number
  is_stress_approved: boolean
  audit_tamper_evident_fingerprint: string
  safety_checks: Array<{
    check_name: string
    is_passed: boolean
    risk_weight: number
    description: string
  }>
  emergency_rollback_procedures: string[]
  created_at: string
}

export interface FullLinkDrillSummaryReport {
  report_id: string
  drill_id: string
  scenario_name: string
  overall_drill_grade: 'GRADE_A_EXCELLENT' | 'GRADE_B_QUALIFIED' | 'GRADE_C_RISKY' | 'GRADE_D_REJECTED'
  is_production_approved: boolean
  composite_health_score_pct: number
  peak_concurrency_vu: number
  peak_tps: number
  p99_latency_ms: number
  error_rate_pct: number
  knee_point_concurrency: number
  knee_point_tps: number
  cliff_point_concurrency: number | null
  max_db_watermark_pct: number
  max_redis_watermark_pct: number
  max_mq_backlog: number
  circuit_breaker_triggered: boolean
  failover_rto_ms: number
  sha256_audit_fingerprint: string
  optimization_remediations: string[]
  created_at: string
}

export async function analyzeThroughputKnee(payload: {
  scenario_name: string
  samples: Array<{
    concurrency_threads: number
    measured_tps: number
    avg_latency_ms?: number
    p99_latency_ms?: number
    error_rate_pct?: number
  }>
}): Promise<{ message: string; report: ThroughputKneeReport }> {
  const resp = await http.post('/stress/drill-report/knee-detection/analyze', payload)
  return resp.data
}

export async function listThroughputKneeReports(limit = 50): Promise<{ total: number; reports: ThroughputKneeReport[] }> {
  const resp = await http.get('/stress/drill-report/knee-detection/reports', { params: { limit } })
  return resp.data
}

export async function evaluateStressBlastRadius(payload: {
  drill_id: string
  target_services?: string[]
  shadow_traffic_isolated?: boolean
  shadow_tables_ready?: boolean
  external_bypasses_ready?: boolean
  circuit_breaker_active?: boolean
  estimated_max_qps?: number
  participating_cell_ids?: string[]
}): Promise<{ message: string; report: StressBlastRadiusReport }> {
  const resp = await http.post('/stress/drill-report/blast-radius/evaluate', payload)
  return resp.data
}

export async function listBlastRadiusReports(limit = 50): Promise<{ total: number; reports: StressBlastRadiusReport[] }> {
  const resp = await http.get('/stress/drill-report/blast-radius/reports', { params: { limit } })
  return resp.data
}

export async function generateFullDrillReport(payload: {
  drill_id: string
  scenario_name: string
  peak_concurrency_vu: number
  peak_tps: number
  p99_latency_ms: number
  error_rate_pct: number
  knee_point_concurrency: number
  knee_point_tps: number
  cliff_point_concurrency?: number | null
  max_db_watermark_pct?: number
  max_redis_watermark_pct?: number
  max_mq_backlog?: number
  circuit_breaker_triggered?: boolean
  failover_rto_ms?: number
}): Promise<{ message: string; report: FullLinkDrillSummaryReport }> {
  const resp = await http.post('/stress/drill-report/summary/generate', payload)
  return resp.data
}

export async function listFullDrillReports(limit = 50): Promise<{ total: number; reports: FullLinkDrillSummaryReport[] }> {
  const resp = await http.get('/stress/drill-report/summary/reports', { params: { limit } })
  return resp.data
}

export async function getFullDrillMarkdown(reportId: string): Promise<{ report_id: string; markdown: string }> {
  const resp = await http.get(`/stress/drill-report/summary/reports/${reportId}/markdown`)
  return resp.data
}
