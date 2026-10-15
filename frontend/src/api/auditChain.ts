import http from './http'

export interface AuditChainBlock {
  index: number
  log_id: number
  timestamp: string
  previous_hash: string
  record_hash: string
  chain_hash: string
  payload_summary: {
    action: string
    resource_type: string
    resource_id?: number | null
    username: string
  }
}

export interface AuditChainIntegrityResult {
  is_valid: boolean
  tampered: boolean
  total_blocks_checked: number
  chain_head_hash: string
  tampered_at_index: number | null
  tampered_log_id?: number | null
  error_description: string
}

export interface ComplianceAuditReport {
  report_id: string
  organization: string
  generated_at: string
  compliance_standard: string
  integrity_status: 'VERIFIED_UNALTERED' | 'TAMPER_DETECTED'
  total_records: number
  chain_head_hash: string
  digital_seal_signature: string
  integrity_diagnostic: AuditChainIntegrityResult
  blocks: AuditChainBlock[]
}

export const auditChainApi = {
  verifyChain(params?: { limit?: number; project_id?: number }): Promise<AuditChainIntegrityResult> {
    return http.post('/audit/chain/verify', null, { params })
  },

  generateReport(data?: {
    organization?: string
    limit?: number
    project_id?: number
    custom_records?: any[]
  }): Promise<ComplianceAuditReport> {
    return http.post('/audit/chain/report', data || {})
  },
}
