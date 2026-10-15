import http from './http'

export type IamResourceKind =
  | 'case'
  | 'suite'
  | 'plan'
  | 'device'
  | 'secret'
  | 'dataset'
  | 'mesh_chaos'

export type IamAction =
  | 'read'
  | 'execute'
  | 'create'
  | 'modify'
  | 'delete'
  | 'manage_permissions'

export interface IamPolicyRule {
  rule_id: string
  effect: 'allow' | 'deny'
  principals: string[]
  resources: string[]
  actions: string[]
  description: string
  enabled: boolean
}

export interface EvaluatePolicyRequest {
  resource_kind: IamResourceKind
  action: IamAction
  project_id?: number | null
  resource_project_id?: number | null
}

export interface IamEvaluationResult {
  allowed: boolean
  decision_reason: string
  matched_rule: string | null
  resource_kind: string
  action: string
}

export const iamPolicyApi = {
  evaluatePolicy(data: EvaluatePolicyRequest): Promise<IamEvaluationResult> {
    return http.post('/iam/evaluate', data)
  },

  listPolicies(): Promise<{ total: number; policies: IamPolicyRule[] }> {
    return http.get('/iam/policies')
  },

  registerPolicy(data: IamPolicyRule): Promise<{ message: string; rule_id: string }> {
    return http.post('/iam/policies', data)
  },
}
