import type { FailureDiagnosisResult, RunStepItem } from '@/api'

// RunDetail 工作台的可测纯逻辑：步骤统计、展开策略、参数化迭代摘要、
// 诊断/自愈载荷归一化、错误摘要截断。i18n 文案与 DOM 聚焦留在视图层。

export interface StepStatusCounts {
  passed: number
  failed: number
  error: number
  skipped: number
}

export function summarizeStepStatuses(steps: RunStepItem[]): StepStatusCounts {
  const counts: StepStatusCounts = { passed: 0, failed: 0, error: 0, skipped: 0 }
  for (const step of steps) {
    if (step.status in counts) counts[step.status as keyof StepStatusCounts]++
  }
  return counts
}

export function failedOrErrorSteps(steps: RunStepItem[]): RunStepItem[] {
  return steps.filter((step) => step.status === 'failed' || step.status === 'error')
}

export function countScreenshotSteps(steps: RunStepItem[]): number {
  return steps.filter((step) => Boolean(step.screenshot_url)).length
}

/** 自动展开失败/异常步骤；全部通过则只展开第一步。 */
export function computeExpandedKeys(steps: RunStepItem[]): number[] {
  const problems = failedOrErrorSteps(steps).map((step) => step.step_index)
  if (problems.length > 0) return problems
  return steps.length > 0 ? [steps[0].step_index] : []
}

export interface IterationStats {
  total: number
  passed: number
  failed: number
  error: number
}

export function readIterationStats(summary: Record<string, unknown> | null | undefined): IterationStats {
  const data = summary ?? {}
  return {
    total: Number(data.iteration_total ?? 0),
    passed: Number(data.iteration_passed ?? 0),
    failed: Number(data.iteration_failed ?? 0),
    error: Number(data.iteration_error ?? 0),
  }
}

export function isParameterizedParent(summary: Record<string, unknown> | null | undefined): boolean {
  return Boolean(summary && typeof summary.iteration_total === 'number' && (summary.iteration_total as number) > 0)
}

export const RUN_STATUS_COLORS: Record<string, string> = {
  passed: 'green',
  failed: 'red',
  running: 'blue',
  error: 'orange',
  pending: 'default',
}

export function runStatusColor(status: string): string {
  return RUN_STATUS_COLORS[status] ?? 'default'
}

export const HEALING_TAG_COLORS: Record<string, string> = {
  pending: 'blue',
  done: 'green',
  failed: 'red',
  skipped: 'default',
}

export function healingTagColor(status?: string | null): string {
  return HEALING_TAG_COLORS[status ?? ''] ?? 'default'
}

export interface RunHealingPayload {
  status: 'pending' | 'done' | 'failed' | 'skipped'
  suggestion: string | null
  at: string | null
  cache_hit: boolean
}

export function normalizeRunHealing(raw: unknown): RunHealingPayload | null {
  if (!raw || typeof raw !== 'object') return null
  const h = raw as Record<string, unknown>
  if (!h.status) return null
  return {
    status: h.status as RunHealingPayload['status'],
    suggestion: typeof h.suggestion === 'string' ? h.suggestion : null,
    at: typeof h.at === 'string' ? h.at : null,
    cache_hit: Boolean(h.cache_hit),
  }
}

export function normalizeFailureDiagnosis(raw: unknown): FailureDiagnosisResult | null {
  if (!raw || typeof raw !== 'object') return null
  const data = raw as Partial<FailureDiagnosisResult>
  if (!data.summary || !data.status || !data.source) return null
  return {
    status: data.status,
    source: data.source,
    summary: data.summary,
    at: data.at ?? '',
    failed_step_count: Number(data.failed_step_count ?? 0),
    screenshot_count: Number(data.screenshot_count ?? 0),
    repair_suggestions: Array.isArray(data.repair_suggestions) ? data.repair_suggestions : [],
    error_samples: Array.isArray(data.error_samples) ? data.error_samples : [],
  }
}

/** 优先取首个带错误信息的失败步骤，其次 run 级错误；超长截断。 */
export function primaryErrorText(steps: RunStepItem[], runError: string | null | undefined, limit = 600): string | null {
  const stepError = failedOrErrorSteps(steps).find((step) => step.error_message)?.error_message
  const text = stepError || runError || ''
  if (!text) return null
  return text.length > limit ? `${text.slice(0, limit)}...` : text
}

export function truncateText(text: string | null | undefined, limit = 500): string {
  if (!text) return ''
  return text.length > limit ? `${text.slice(0, limit)}...` : text
}
