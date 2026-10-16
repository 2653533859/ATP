import http from './http'

export type AssetType = 'plan' | 'suite' | 'case' | 'dataset' | 'api_endpoint' | 'device'

export interface AssetNode {
  node_id: string
  asset_type: AssetType
  asset_id: number
  name: string
  project_id: number | null
  metadata?: Record<string, any>
}

export interface ProjectAssetGraphResponse {
  project_id: number
  total_nodes: number
  total_forward_edges: number
  nodes: AssetNode[]
  forward_edges: Record<string, string[]>
  reverse_edges: Record<string, string[]>
}

export interface DownstreamDependenciesResponse {
  source_node_id: string
  max_depth: number
  visited_count: number
  downstream_nodes: AssetNode[]
}

export interface UpstreamDependenciesResponse {
  target_node_id: string
  max_depth: number
  visited_count: number
  upstream_nodes: AssetNode[]
}

export interface OrphanAssetsResponse {
  orphan_cases: AssetNode[]
  orphan_datasets: AssetNode[]
  total_orphans_count: number
}

export type ChangeSeverity = 'breaking' | 'warning' | 'compatible'

export interface ContractSchemaChange {
  change_type: ChangeSeverity
  field_path: string
  rule: string
  description: string
  baseline_value?: any
  current_value?: any
}

export interface ImpactedCaseItem {
  case_id: number
  case_name: string
  severity: ChangeSeverity
  affected_steps: string[]
  reasons: string[]
  actionable_remediation: string
}

export interface ContractImpactReport {
  method: string
  path: string
  has_breaking_changes: boolean
  diff_summary: {
    breaking_count: number
    warning_count: number
    compatible_count: number
  }
  breaking_changes: ContractSchemaChange[]
  warnings: ContractSchemaChange[]
  compatible_changes: ContractSchemaChange[]
  impacted_cases: ImpactedCaseItem[]
  total_impacted_cases_count: number
  impacted_plans_count: number
  impacted_suites_count: number
}

export interface AnalyzeContractImpactRequest {
  method?: string
  path?: string
  baseline_schema: Record<string, any>
  current_schema: Record<string, any>
  project_id?: number | null
}

export interface SynthesizeRegressionRequest {
  impacted_case_ids: number[]
  project_id?: number | null
  suite_name?: string
  is_breaking_change?: boolean
  persist?: boolean
  auto_trigger?: boolean
}

export interface TargetedRegressionResult {
  synthesis_id: string
  suite_id: number | null
  suite_name: string
  project_id: number | null
  total_cases_count: number
  included_case_ids: number[]
  task_priority: string
  auto_triggered: boolean
  dispatched_task_id: string | null
  task_preempted: boolean
  created_at: string
  message: string
}

export const assetGraphApi = {
  getProjectGraph(projectId: number): Promise<ProjectAssetGraphResponse> {
    return http.get(`/asset-graph/project/${projectId}`)
  },

  getDownstream(nodeId: string, maxDepth: number = 10): Promise<DownstreamDependenciesResponse> {
    return http.get('/asset-graph/downstream', {
      params: { node_id: nodeId, max_depth: maxDepth },
    })
  },

  getUpstream(nodeId: string, maxDepth: number = 10): Promise<UpstreamDependenciesResponse> {
    return http.get('/asset-graph/upstream', {
      params: { node_id: nodeId, max_depth: maxDepth },
    })
  },

  getOrphans(projectId?: number): Promise<OrphanAssetsResponse> {
    return http.get('/asset-graph/orphans', {
      params: { project_id: projectId },
    })
  },

  reindex(projectId?: number): Promise<{ message: string; total_nodes: number; total_forward_edges: number }> {
    return http.post('/asset-graph/reindex', null, {
      params: { project_id: projectId },
    })
  },

  analyzeContractImpact(data: AnalyzeContractImpactRequest): Promise<ContractImpactReport> {
    return http.post('/asset-graph/contract-impact/analyze', data)
  },

  synthesizeAndTriggerRegression(data: SynthesizeRegressionRequest): Promise<TargetedRegressionResult> {
    return http.post('/asset-graph/contract-impact/synthesize-and-trigger', data)
  },
}
