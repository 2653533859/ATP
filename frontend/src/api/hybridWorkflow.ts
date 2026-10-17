import http from './http'

export interface WorkflowNodeItem {
  node_id: string
  node_name: string
  node_type: string
  config: Record<string, any>
  condition_expr?: string
  x?: number
  y?: number
}

export interface WorkflowEdgeItem {
  edge_id: string
  source_node_id: string
  target_node_id: string
  branch_type?: string
}

export interface NodeExecutionRecordItem {
  node_id: string
  node_name: string
  node_type: string
  status: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'SKIPPED'
  duration_ms: number
  input_data: Record<string, any>
  output_data: Record<string, any>
  error_message?: string | null
  executed_at: string
}

export interface WorkflowExecutionReportItem {
  run_id: string
  workflow_id: string
  workflow_name: string
  total_nodes: number
  executed_nodes_count: number
  status: 'SUCCESS' | 'FAILED' | 'PARTIAL'
  node_records: NodeExecutionRecordItem[]
  context_outputs: Record<string, any>
  start_time: string
  end_time: string
  total_duration_ms: number
}

export interface WorkflowDraftItem {
  workflow_id: string
  workflow_name: string
  description?: string
  nodes: WorkflowNodeItem[]
  edges: WorkflowEdgeItem[]
}

export const hybridWorkflowApi = {
  saveDraft(payload: WorkflowDraftItem): Promise<{ message: string; workflow_id: string }> {
    return http.post('/workflow/save', payload)
  },

  listDrafts(): Promise<{ total: number; drafts: WorkflowDraftItem[] }> {
    return http.get('/workflow/drafts')
  },

  getDraft(workflowId: string): Promise<{ draft: WorkflowDraftItem }> {
    return http.get(`/workflow/draft/${workflowId}`)
  },

  executeWorkflow(payload: {
    workflow_id: string
    workflow_name?: string
    nodes: WorkflowNodeItem[]
    edges: WorkflowEdgeItem[]
    initial_variables?: Record<string, any>
  }): Promise<{ message: string; report: WorkflowExecutionReportItem }> {
    return http.post('/workflow/execute', payload)
  },

  getRun(runId: string): Promise<{ report: WorkflowExecutionReportItem }> {
    return http.get(`/workflow/run/${runId}`)
  },

  listRuns(limit: number = 50): Promise<{ total: number; runs: WorkflowExecutionReportItem[] }> {
    return http.get('/workflow/runs', { params: { limit } })
  },

  resolveVariables(payload: {
    raw_config: Record<string, any>
    context_variables: Record<string, any>
  }): Promise<{ resolved_config: Record<string, any>; variables_in_bus: Record<string, any> }> {
    return http.post('/workflow/variable/resolve', payload)
  },
}
