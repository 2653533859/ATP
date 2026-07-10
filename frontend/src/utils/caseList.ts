import type { CaseFlakyStats, CaseSummaryItem, ModuleTreeItem } from '@/api'

// CaseList 工作台的可测纯逻辑：筛选统计、工作流守卫、flaky 提示参数、模块树扁平化。
// i18n 文案包装留在视图层。

export function filterCasesByLevel(cases: CaseSummaryItem[], level: string | null | undefined): CaseSummaryItem[] {
  return cases.filter((testCase) => !level || testCase.case_level === level)
}

export function countPendingReviews(cases: CaseSummaryItem[]): number {
  return cases.filter((testCase) => testCase.review_status === 'pending').length
}

export function countFlakyCases(cases: CaseSummaryItem[]): number {
  return cases.filter((testCase) => testCase.flaky_stats?.is_flaky).length
}

export interface CaseListFilterValues {
  keyword: string
  type?: string | null
  priority?: string | null
  level?: string | null
  status?: string | null
  review_status?: string | null
  automation_status?: string | null
}

export type CaseListFilterKey = keyof CaseListFilterValues

/** 收集非空筛选器的 key 与原始值（keyword 先 trim）；标签文案由视图用 i18n 生成。 */
export function collectActiveFilters(filters: CaseListFilterValues): Array<{ key: CaseListFilterKey; value: string }> {
  const active: Array<{ key: CaseListFilterKey; value: string }> = []
  const keyword = filters.keyword.trim()
  if (keyword) active.push({ key: 'keyword', value: keyword })
  for (const key of ['type', 'priority', 'level', 'status', 'review_status', 'automation_status'] as const) {
    const value = filters[key]
    if (value) active.push({ key, value })
  }
  return active
}

export interface CaseWorkflowAbility {
  canModify: boolean
  canApprove: boolean
}

/** 评审工作流按钮的可见性守卫（与后端状态机一致的前端预判）。 */
export function caseWorkflowGuards(
  testCase: Pick<CaseSummaryItem, 'status' | 'review_status'>,
  ability: CaseWorkflowAbility,
) {
  const notDeprecated = testCase.status !== 'deprecated'
  return {
    submitReview: ability.canModify && notDeprecated && testCase.review_status !== 'pending',
    approve: ability.canApprove && notDeprecated && testCase.review_status === 'pending',
    reject: ability.canApprove && testCase.review_status === 'pending',
    deprecate: ability.canModify && notDeprecated,
    reactivate: ability.canModify && testCase.status === 'deprecated' && testCase.review_status === 'approved',
  }
}

/** flaky 提示参数：无样本返回 null（视图显示 no_runs 文案）。 */
export function flakyTooltipParams(stats: CaseFlakyStats | null | undefined) {
  if (!stats || stats.total_runs === 0) return null
  return {
    total: stats.total_runs,
    passed: stats.passed_runs,
    failed: stats.failed_runs + stats.error_runs,
    rate: stats.failure_rate,
  }
}

export function flattenModules(nodes: ModuleTreeItem[], acc: Record<number, string> = {}): Record<number, string> {
  for (const node of nodes) {
    acc[node.id] = node.name
    if (Array.isArray(node.children) && node.children.length) {
      flattenModules(node.children, acc)
    }
  }
  return acc
}
