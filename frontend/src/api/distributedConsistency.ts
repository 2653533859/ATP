import http from './http'

export type TransactionPattern = 'TCC' | 'SAGA'
export type GlobalTxStatus = 'ACTIVE' | 'COMMITTED' | 'ROLLED_BACK' | 'HANGING' | 'INCONSISTENT' | 'TIMEOUT'
export type BranchStage = 'TRY' | 'CONFIRM' | 'CANCEL' | 'FORWARD' | 'COMPENSATE'
export type BranchStatus = 'PENDING' | 'SUCCESS' | 'FAILED' | 'TIMEOUT'
export type SagaAnomalyType = 'HANGING_TRANSACTION' | 'EMPTY_COMPENSATION' | 'TIMEOUT_PENDING' | 'PARTIAL_COMMIT_FAILURE' | 'NONE'

export interface BranchTxItem {
  branch_id: string
  global_tx_id: string
  service_name: string
  action_name: string
  stage: BranchStage
  status: BranchStatus
  duration_ms: number
  error_message: string
  retry_count: number
  payload: Record<string, any>
  recorded_at: string
}

export interface GlobalTxItem {
  global_tx_id: string
  business_key: string
  pattern: TransactionPattern
  status: GlobalTxStatus
  timeout_seconds: number
  branches_count: number
  branches: BranchTxItem[]
  started_at: string
  updated_at: string
  is_consistent?: boolean
  detected_anomaly?: SagaAnomalyType
  anomaly_description?: string
}

export interface SagaAuditReport {
  global_tx_id: string
  business_key: string
  pattern: TransactionPattern
  status: GlobalTxStatus
  is_consistent: boolean
  detected_anomaly: SagaAnomalyType
  anomaly_description: string
  branches_count: number
  branches: BranchTxItem[]
  remediation_advice: string[]
  audited_at: string
}

export interface FieldDifferenceItem {
  field_name: string
  source_value: any
  target_value: any
  is_mismatched: boolean
  description: string
}

export interface RecordDiffItem {
  join_key_value: string
  category: 'MISSING_IN_TARGET' | 'MISSING_IN_SOURCE' | 'FIELD_VALUE_MISMATCH' | 'NONE'
  field_diffs: FieldDifferenceItem[]
  remediation_sql: string
}

export interface ConsistencyAuditRuleItem {
  rule_id: string
  rule_name: string
  source_service: string
  source_table: string
  target_service: string
  target_table: string
  join_key: string
  field_mappings: Record<string, string>
  numeric_tolerance: number
  tolerance_threshold_pct: number
  created_at: string
}

export interface ConsistencyAuditReport {
  report_id: string
  rule_id: string
  rule_name: string
  verdict: 'RECONCILED' | 'WARNING' | 'CRITICAL'
  consistency_rate_pct: number
  total_records_checked: number
  consistent_records_count: number
  mismatched_records_count: number
  missing_in_target_count: number
  missing_in_source_count: number
  value_mismatches_count: number
  diff_records: RecordDiffItem[]
  verdict_summary: string
  audited_at: string
}

export interface EventMessageItem {
  message_id: string
  topic: string
  consumer_group: string
  idempotency_key: string
  payload: Record<string, any>
  status: 'PRODUCED' | 'CONSUMED' | 'RETRYING' | 'DEAD_LETTER' | 'DUPLICATE_SUPPRESSED'
  retry_count: number
  max_retries: number
  lag_ms: number
  error_message: string
  produced_at: string
  consumed_at: string | null
}

export interface TopicLagMetricItem {
  topic: string
  consumer_group: string
  current_lag: number
  lag_severity: 'HEALTHY' | 'WARNING' | 'CRITICAL_BACKLOG'
  avg_processing_time_ms: number
  oldest_unconsumed_age_sec: number
}

export interface IdempotencyVerificationReport {
  idempotency_key: string
  topic: string
  consumer_group: string
  total_deliveries: number
  state_mutations_count: number
  duplicate_suppressed_count: number
  is_idempotent: boolean
  verdict_summary: string
  verified_at: string
}

export const sagaTransactionApi = {
  createGlobalTx(data: { business_key: string; pattern?: string; timeout_seconds?: number; global_tx_id?: string }): Promise<{ message: string; transaction: GlobalTxItem }> {
    return http.post('/consistency/saga/transactions', data)
  },

  recordBranch(data: { global_tx_id: string; service_name: string; action_name: string; stage?: string; status?: string; duration_ms?: number; error_message?: string; retry_count?: number; payload?: any }): Promise<{ message: string; branch: BranchTxItem }> {
    return http.post('/consistency/saga/branches', data)
  },

  auditGlobalTx(globalTxId: string): Promise<SagaAuditReport> {
    return http.get(`/consistency/saga/transactions/${globalTxId}/audit`)
  },

  listHangingTransactions(): Promise<{ total: number; transactions: GlobalTxItem[] }> {
    return http.get('/consistency/saga/hanging')
  },

  simulateScenario(scenario_key: string): Promise<{ message: string; report: SagaAuditReport }> {
    return http.post('/consistency/saga/simulate', { scenario_key })
  },

  clearTransactions(): Promise<{ message: string; cleared_count: number }> {
    return http.delete('/consistency/saga/transactions')
  },
}

export const crossDbAuditApi = {
  registerRule(data: Partial<ConsistencyAuditRuleItem>): Promise<{ message: string; rule: ConsistencyAuditRuleItem }> {
    return http.post('/consistency/audit/rules', data)
  },

  listRules(): Promise<{ total: number; rules: ConsistencyAuditRuleItem[] }> {
    return http.get('/consistency/audit/rules')
  },

  deleteRule(ruleId: string): Promise<{ message: string; rule_id: string }> {
    return http.delete(`/consistency/audit/rules/${ruleId}`)
  },

  executeAudit(data: {
    rule_name?: string
    source_service?: string
    source_table?: string
    target_service?: string
    target_table?: string
    join_key?: string
    field_mappings?: Record<string, string>
    numeric_tolerance?: number
    tolerance_threshold_pct?: number
    source_records: any[]
    target_records: any[]
  }): Promise<{ message: string; report: ConsistencyAuditReport }> {
    return http.post('/consistency/audit/execute', data)
  },

  listReports(): Promise<{ total: number; reports: ConsistencyAuditReport[] }> {
    return http.get('/consistency/audit/reports')
  },

  getReport(reportId: string): Promise<ConsistencyAuditReport> {
    return http.get(`/consistency/audit/reports/${reportId}`)
  },

  clearStore(): Promise<{ message: string; cleared_count: number }> {
    return http.delete('/consistency/audit/clear')
  },
}

export const eventBusGuardApi = {
  produce(data: { topic: string; payload: any; idempotency_key?: string; consumer_group?: string; max_retries?: number }): Promise<{ message: string; event: EventMessageItem }> {
    return http.post('/consistency/event-bus/messages/produce', data)
  },

  consume(data: { message_id: string; consumer_group?: string; simulate_fail?: boolean; error_reason?: string }): Promise<{ success: boolean; status: string; message: string; state_mutated?: boolean }> {
    return http.post('/consistency/event-bus/messages/consume', data)
  },

  verifyIdempotency(data: { topic?: string; idempotency_key: string; delivery_times?: number; consumer_group?: string }): Promise<{ message: string; report: IdempotencyVerificationReport }> {
    return http.post('/consistency/event-bus/idempotency/verify', data)
  },

  getLag(): Promise<{ total: number; metrics: TopicLagMetricItem[] }> {
    return http.get('/consistency/event-bus/lag')
  },

  listDeadLetters(): Promise<{ total: number; dead_letters: EventMessageItem[] }> {
    return http.get('/consistency/event-bus/dead-letters')
  },

  requeueDeadLetter(messageId: string): Promise<{ message: string; message_id: string }> {
    return http.post(`/consistency/event-bus/dead-letters/${messageId}/requeue`)
  },

  clearMessages(): Promise<{ message: string; cleared_count: number }> {
    return http.delete('/consistency/event-bus/messages')
  },
}
