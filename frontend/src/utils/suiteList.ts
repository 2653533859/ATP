export type SuiteListExecutionMode = 'sequential' | 'parallel'
export type SuiteListFailStrategy = 'continue' | 'fast-fail' | 'require-minimum-pass-rate'
export type SuiteListRunStatus = 'pending' | 'running' | 'passed' | 'failed' | 'error' | string

export interface SuiteListConfig {
  execution_mode?: SuiteListExecutionMode | string | null
  max_workers?: number | string | null
  fail_strategy?: SuiteListFailStrategy | string | null
  min_pass_rate?: number | string | null
  [key: string]: unknown
}

export interface NormalizedSuiteListConfig {
  execution_mode: SuiteListExecutionMode
  max_workers: number
  fail_strategy: SuiteListFailStrategy
  min_pass_rate: number
  [key: string]: unknown
}

export type SuiteListCaseRunItem = { status?: string | null }

export interface SuiteListRunItem {
  status: SuiteListRunStatus
  result_summary?: Record<string, unknown> | null
  case_run_ids?: SuiteListCaseRunItem[] | null
}

export function createDefaultSuiteConfig(): NormalizedSuiteListConfig {
  return {
    execution_mode: 'sequential',
    max_workers: 5,
    fail_strategy: 'continue',
    min_pass_rate: 0.8,
  }
}

export function normalizeSuiteConfig(config?: SuiteListConfig | null): NormalizedSuiteListConfig {
  const raw = config ?? {}
  const execution_mode: SuiteListExecutionMode = raw.execution_mode === 'parallel' ? 'parallel' : 'sequential'
  const max_workersValue = Number(raw.max_workers)
  const fail_strategy: SuiteListFailStrategy =
    raw.fail_strategy === 'fast-fail' ||
    raw.fail_strategy === 'require-minimum-pass-rate' ||
    raw.fail_strategy === 'continue'
      ? raw.fail_strategy
      : 'continue'
  const min_pass_rate_value = Number(raw.min_pass_rate)

  return {
    execution_mode,
    max_workers:
      Number.isFinite(max_workersValue) && max_workersValue > 0
        ? Math.min(20, Math.max(1, Math.round(max_workersValue)))
        : 5,
    fail_strategy,
    min_pass_rate:
      Number.isFinite(min_pass_rate_value)
        ? Math.min(1, Math.max(0, min_pass_rate_value))
        : 0.8,
  }
}

export function suiteExecutionModeColor(mode?: SuiteListConfig['execution_mode']): string {
  return mode === 'parallel' ? 'blue' : 'default'
}

export function suiteFailStrategyColor(strategy?: SuiteListConfig['fail_strategy']): string {
  return {
    'continue': 'default',
    'fast-fail': 'volcano',
    'require-minimum-pass-rate': 'purple',
  }[strategy ?? 'continue'] ?? 'default'
}

export type RunStatusBadge = 'default' | 'processing' | 'success' | 'error' | 'warning'

export function runStatusBadge(status: string): RunStatusBadge {
  const map: Record<string, RunStatusBadge> = {
    pending: 'default',
    running: 'processing',
    passed: 'success',
    failed: 'error',
    error: 'warning',
  }
  return map[status] ?? 'default'
}

export function formatDuration(duration?: number | null): string {
  if (duration == null) return '-'
  if (duration < 1000) return `${duration} ms`
  return `${(duration / 1000).toFixed(1)}s`
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 10) / 10}%`
}

export function getSuiteRunTotalCount(run: SuiteListRunItem): number {
  const summaryTotal = Number(run.result_summary?.total)
  if (Number.isFinite(summaryTotal) && summaryTotal > 0) {
    return summaryTotal
  }
  return run.case_run_ids?.length ?? 0
}

export function getSuiteRunPassedCount(run: SuiteListRunItem): number {
  const passed = Number(run.result_summary?.passed ?? 0)
  return Number.isFinite(passed) ? passed : 0
}

export function getSuiteRunFailureCount(run: SuiteListRunItem): number {
  const failed = Number(run.result_summary?.failed ?? 0)
  const error = Number(run.result_summary?.error ?? 0)
  return (Number.isFinite(failed) ? failed : 0) + (Number.isFinite(error) ? error : 0)
}

export function getSuiteRunPassRate(run: SuiteListRunItem): number {
  const total = getSuiteRunTotalCount(run)
  return total ? (getSuiteRunPassedCount(run) / total) * 100 : 0
}

export function getSuiteRunFailureItems(run: SuiteListRunItem): SuiteListCaseRunItem[] {
  return (run.case_run_ids ?? []).filter((item) => item.status === 'failed' || item.status === 'error')
}

export function getSuiteRunCompletedCount(run: SuiteListRunItem): number {
  const summary = run.result_summary ?? {}
  const summaryCompleted = ['passed', 'failed', 'error', 'skipped']
    .map((key) => Number(summary[key] ?? 0))
    .filter((value) => Number.isFinite(value) && value > 0)
    .reduce((total, value) => total + value, 0)

  if (summaryCompleted > 0) {
    return summaryCompleted
  }
  return run.case_run_ids?.length ?? 0
}

export function getSuiteRunProgressPercent(run: SuiteListRunItem): number {
  const total = getSuiteRunTotalCount(run)
  if (total <= 0) {
    return 0
  }
  return Math.min(100, Math.round((getSuiteRunCompletedCount(run) / total) * 100))
}

export function getSuiteRunProgressStatus(run: SuiteListRunItem): 'active' | 'exception' | 'success' {
  if (run.status === 'failed' || run.status === 'error') {
    return 'exception'
  }
  if (run.status === 'passed') {
    return 'success'
  }
  return 'active'
}

export function hasActiveSuiteRuns(runs: SuiteListRunItem[]): boolean {
  return runs.some((run) => run.status === 'pending' || run.status === 'running')
}

// ── 模块树与用例选择（SuiteList 创建/编辑抽屉的可测纯逻辑）─────────

/** 最小模块树节点：只依赖 id / children，避免耦合 @/api 的完整类型。 */
export interface SuiteModuleNode {
  id: number
  name: string
  children?: SuiteModuleNode[] | null
}

export interface ModuleTreeOption {
  title: string
  value: number
  key: number
  children?: ModuleTreeOption[]
}

/** 每个模块 id → 其自身与全部后代 id 的集合（用于按模块过滤用例）。 */
export function buildModuleDescendantMap(
  nodes: SuiteModuleNode[],
  acc: Map<number, Set<number>> = new Map(),
): Map<number, Set<number>> {
  for (const node of nodes) {
    buildModuleDescendantMap(node.children ?? [], acc)
    const descendantIds = new Set<number>([node.id])
    for (const child of node.children ?? []) {
      const childIds = acc.get(child.id)
      if (!childIds) continue
      for (const childId of childIds) descendantIds.add(childId)
    }
    acc.set(node.id, descendantIds)
  }
  return acc
}

/** 构建 tree-select 选项，剪掉既无可用用例又无可用子模块的空分支。 */
export function buildModuleTreeOptions(
  nodes: SuiteModuleNode[],
  availableModuleIds: Set<number>,
): ModuleTreeOption[] {
  const options: ModuleTreeOption[] = []
  for (const node of nodes) {
    const children = buildModuleTreeOptions(node.children ?? [], availableModuleIds)
    if (!availableModuleIds.has(node.id) && children.length === 0) continue
    options.push({
      title: node.name,
      value: node.id,
      key: node.id,
      children: children.length ? children : undefined,
    })
  }
  return options
}

export type CaseSelectionScope = 'all' | 'selected' | 'unselected'
export type CaseReadyFilter = 'all' | 'ready' | 'not_ready'

export interface SuiteCaseExecutionState {
  status: string
  review_status: string
  automation_status: string
}

/** 用例不可执行的原因分类（返回 i18n key，无问题返回 null）。 */
export function caseExecutionReasonKey(item: SuiteCaseExecutionState): string | null {
  if (item.status !== 'active') return 'status_not_active'
  if (item.review_status !== 'approved') return 'review_not_approved'
  if (!['auto', 'semi_auto'].includes(item.automation_status)) return 'not_automation'
  return null
}

export interface SuiteCaseFilterInput {
  moduleId: number | undefined
  caseType: string | undefined
  readyFilter: CaseReadyFilter
  selectionScope: CaseSelectionScope
}

export interface SuiteCandidateCase {
  id: number
  module_id: number
  case_type: string
  is_ready_for_execution: boolean
}

/** 结构化筛选（模块/类型/就绪/已选范围）—— 关键词搜索由视图另做（依赖 i18n 文案）。 */
export function passesSuiteCaseStructuralFilter(
  item: SuiteCandidateCase,
  filter: SuiteCaseFilterInput,
  selectedIds: Set<number>,
  descendantMap: Map<number, Set<number>>,
): boolean {
  if (filter.moduleId !== undefined) {
    const allowed = descendantMap.get(filter.moduleId) ?? new Set<number>()
    if (!allowed.has(item.module_id)) return false
  }
  if (filter.caseType !== undefined && item.case_type !== filter.caseType) return false
  if (filter.readyFilter === 'ready' && !item.is_ready_for_execution) return false
  if (filter.readyFilter === 'not_ready' && item.is_ready_for_execution) return false
  const isSelected = selectedIds.has(item.id)
  if (filter.selectionScope === 'selected' && !isSelected) return false
  if (filter.selectionScope === 'unselected' && isSelected) return false
  return true
}
