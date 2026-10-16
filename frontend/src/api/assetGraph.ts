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
}
