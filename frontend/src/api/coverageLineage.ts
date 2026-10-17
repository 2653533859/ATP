import http from './http'

export interface CoverageLineageNodeItem {
  node_id: string
  node_name: string
  category: 'requirement' | 'api_endpoint' | 'ui_interaction' | 'business_branch'
  expected_branches: string[]
  covered_branches: string[]
  missing_branches: string[]
  coverage_rate: number
  is_gap: boolean
  risk_level: 'HIGH' | 'MEDIUM' | 'LOW' | 'NONE'
  linked_case_ids: string[]
  description?: string
  depth?: number
  children?: CoverageLineageNodeItem[]
}

export interface CoverageLineageEdgeItem {
  edge_id: string
  source_id: string
  target_id: string
  relationship: string
}

export interface CoverageLineageReportItem {
  report_id: string
  project_id: string
  total_nodes_count: number
  gap_nodes_count: number
  overall_coverage_rate: number
  high_risk_gaps_count: number
  nodes: CoverageLineageNodeItem[]
  edges: CoverageLineageEdgeItem[]
  tree_hierarchy: CoverageLineageNodeItem[]
  analyzed_at: string
}

export interface SynthesizedTestStepItem {
  step_number: number
  step_name: string
  action_type: string
  input_payload: Record<string, any>
  expected_result: string
}

export interface SynthesizedTestCaseDraftItem {
  draft_id: string
  source_node_id: string
  target_branch: string
  title: string
  case_type: string
  priority: string
  preconditions: string
  steps: SynthesizedTestStepItem[]
  expected_outcome: string
  suggested_tags: string[]
  created_at: string
}

export const coverageLineageApi = {
  analyzeLineage(payload: {
    project_id?: string
    nodes: Array<{
      node_id: string
      node_name: string
      category: string
      expected_branches: string[]
      covered_branches: string[]
      linked_case_ids?: string[]
      description?: string
    }>
    edges?: Array<{
      edge_id: string
      source_id: string
      target_id: string
      relationship?: string
    }>
  }): Promise<{ message: string; report: CoverageLineageReportItem }> {
    return http.post('/coverage/lineage/analyze', payload)
  },

  getReport(reportId: string): Promise<{ report: CoverageLineageReportItem }> {
    return http.get(`/coverage/lineage/${reportId}`)
  },

  listReports(limit: number = 50): Promise<{ total: number; reports: CoverageLineageReportItem[] }> {
    return http.get('/coverage/lineages', { params: { limit } })
  },

  synthesizeCases(payload: {
    gap_nodes: Array<{
      node_id: string
      node_name: string
      category: string
      expected_branches: string[]
      covered_branches: string[]
      linked_case_ids?: string[]
      description?: string
    }>
  }): Promise<{
    message: string
    total_synthesized: number
    drafts: SynthesizedTestCaseDraftItem[]
  }> {
    return http.post('/coverage/synthesize', payload)
  },
}
