export type PlanListExecutionMode = 'sequential' | 'parallel'
export type PlanListFailStrategy = 'continue' | 'fast-fail' | 'require-minimum-pass-rate'
export type PlanListScheduleType = 'manual' | 'cron' | 'webhook'
export type CronMode = 'daily' | 'weekly' | 'custom'
export type CronValidationErrorKey = 'required' | 'parts' | 'minute' | 'hour' | 'day' | 'month' | 'weekday'

export interface PlanListConfig {
  execution_mode?: PlanListExecutionMode | string | null
  max_workers?: number | string | null
  fail_strategy?: PlanListFailStrategy | string | null
  min_pass_rate?: number | string | null
  [key: string]: unknown
}

export interface NormalizedPlanListConfig {
  execution_mode: PlanListExecutionMode
  max_workers: number
  fail_strategy: PlanListFailStrategy
  min_pass_rate: number
  [key: string]: unknown
}

export type PlanListSuiteRunItem = { status?: string | null } & Record<string, unknown>

export interface PlanListRunItem {
  result_summary?: Record<string, unknown> | null
  suite_run_ids?: PlanListSuiteRunItem[] | null
}

export interface ParsedCronPreset {
  mode: CronMode
  hour: number
  minute: number
  weekday: number
  customExpression: string
}

export type PlanSaveValidationError = 'name' | 'suite' | 'cron' | ''

export interface PlanFormValues {
  name: string
  description: string
  schedule_type: PlanListScheduleType
  cron_expression: string
  is_enabled: boolean
  auto_create_bugs: boolean
  env_id: number | null
  config: Record<string, unknown>
}

export function getPlanSaveValidationError(
  form: Pick<PlanFormValues, 'name' | 'schedule_type'>,
  suiteIds: number[],
  cronValidationError: string,
): PlanSaveValidationError {
  if (!form.name.trim()) return 'name'
  if (suiteIds.length === 0) return 'suite'
  if (form.schedule_type === 'cron' && cronValidationError) return 'cron'
  return ''
}

export function buildPlanMutationPayload(form: PlanFormValues, suiteIds: number[]) {
  return {
    name: form.name,
    description: form.description || null,
    suite_ids: suiteIds.map((suiteId, sort) => ({ suite_id: suiteId, sort })),
    schedule_type: form.schedule_type,
    cron_expression: form.schedule_type === 'cron' ? form.cron_expression : null,
    is_enabled: form.is_enabled,
    auto_create_bugs: form.auto_create_bugs,
    env_id: form.env_id,
    config: { ...form.config },
  }
}

export function createDefaultPlanConfig(): NormalizedPlanListConfig {
  return {
    execution_mode: 'sequential',
    max_workers: 3,
    fail_strategy: 'continue',
    min_pass_rate: 0.8,
  }
}

export function normalizePlanConfig(config?: PlanListConfig | null): NormalizedPlanListConfig {
  const raw = config ?? {}
  const execution_mode: PlanListExecutionMode = raw.execution_mode === 'parallel' ? 'parallel' : 'sequential'
  const max_workersValue = Number(raw.max_workers)
  const fail_strategy: PlanListFailStrategy =
    raw.fail_strategy === 'fast-fail' ||
    raw.fail_strategy === 'require-minimum-pass-rate' ||
    raw.fail_strategy === 'continue'
      ? raw.fail_strategy
      : 'continue'
  const min_pass_rate_value = Number(raw.min_pass_rate)
  return {
    execution_mode,
    max_workers: Number.isFinite(max_workersValue) && max_workersValue > 0
      ? Math.min(Math.max(Math.trunc(max_workersValue), 1), 10)
      : 3,
    fail_strategy,
    min_pass_rate: Number.isFinite(min_pass_rate_value)
      ? Math.min(Math.max(min_pass_rate_value, 0), 1)
      : 0.8,
  }
}

export function scheduleColor(type: string): string {
  return { manual: 'default', cron: 'blue', webhook: 'orange' }[type] ?? 'default'
}

export function runStatusColor(status: string): string {
  return {
    pending: 'default',
    running: 'processing',
    passed: 'success',
    failed: 'error',
    error: 'warning',
  }[status] ?? 'default'
}

export function formatDuration(duration?: number | null): string {
  if (duration == null) return '-'
  if (duration < 1000) return `${duration} ms`
  return `${(duration / 1000).toFixed(1)}s`
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 10) / 10}%`
}

function isIntegerInRange(value: string, min: number, max: number): boolean {
  if (!/^\d+$/.test(value)) return false
  const num = Number(value)
  return num >= min && num <= max
}

export function validateCronField(field: string, min: number, max: number): boolean {
  if (field === '*') return true
  if (field.includes('/')) {
    const [base, step] = field.split('/')
    return (base === '*' || isIntegerInRange(base, min, max)) && isIntegerInRange(step, 1, max - min + 1)
  }
  if (field.includes('-')) {
    const [start, end] = field.split('-')
    return isIntegerInRange(start, min, max) && isIntegerInRange(end, min, max) && Number(start) <= Number(end)
  }
  if (field.includes(',')) {
    return field.split(',').every(part => validateCronField(part, min, max))
  }
  return isIntegerInRange(field, min, max)
}

export function getCronValidationErrorKey(expression: string): CronValidationErrorKey | '' {
  const trimmed = expression.trim()
  if (!trimmed) return 'required'

  const parts = trimmed.split(/\s+/)
  if (parts.length !== 5) return 'parts'

  const [minute, hour, dayOfMonth, month, dayOfWeek] = parts
  if (!validateCronField(minute, 0, 59)) return 'minute'
  if (!validateCronField(hour, 0, 23)) return 'hour'
  if (!validateCronField(dayOfMonth, 1, 31)) return 'day'
  if (!validateCronField(month, 1, 12)) return 'month'
  if (!validateCronField(dayOfWeek, 0, 6)) return 'weekday'
  return ''
}

export function parseCronPreset(expression: string | null | undefined): ParsedCronPreset {
  const cron = (expression ?? '').trim()
  const dailyMatch = cron.match(/^(\d{1,2})\s+(\d{1,2})\s+\*\s+\*\s+\*$/)
  if (dailyMatch) {
    return {
      mode: 'daily',
      minute: Number(dailyMatch[1]),
      hour: Number(dailyMatch[2]),
      weekday: 1,
      customExpression: cron,
    }
  }

  const weeklyMatch = cron.match(/^(\d{1,2})\s+(\d{1,2})\s+\*\s+\*\s+([0-6])$/)
  if (weeklyMatch) {
    return {
      mode: 'weekly',
      minute: Number(weeklyMatch[1]),
      hour: Number(weeklyMatch[2]),
      weekday: Number(weeklyMatch[3]),
      customExpression: cron,
    }
  }

  return {
    mode: 'custom',
    minute: 0,
    hour: 9,
    weekday: 1,
    customExpression: cron,
  }
}

export function getPlanRunTotalCount(run: PlanListRunItem): number {
  const summaryTotal = Number(run.result_summary?.total)
  if (Number.isFinite(summaryTotal) && summaryTotal > 0) {
    return summaryTotal
  }
  return run.suite_run_ids?.length ?? 0
}

export function getPlanRunPassedCount(run: PlanListRunItem): number {
  const passed = Number(run.result_summary?.passed ?? 0)
  return Number.isFinite(passed) ? passed : 0
}

export function getPlanRunFailureCount(run: PlanListRunItem): number {
  const failed = Number(run.result_summary?.failed ?? 0)
  const error = Number(run.result_summary?.error ?? 0)
  return (Number.isFinite(failed) ? failed : 0) + (Number.isFinite(error) ? error : 0)
}

export function getPlanRunPassRate(run: PlanListRunItem): number {
  const total = getPlanRunTotalCount(run)
  return total ? (getPlanRunPassedCount(run) / total) * 100 : 0
}

export function getPlanRunFailureItems(run: PlanListRunItem): PlanListSuiteRunItem[] {
  return (run.suite_run_ids ?? []).filter((item) => item.status === 'failed' || item.status === 'error')
}

export interface CronScheduleInput {
  mode: CronMode
  hour: number
  minute: number
  weekday: number
  customExpression: string
}

/** 按调度模式构造 cron 表达式：daily/weekly 由时分（周）拼装，custom 取用户输入（trim）。 */
export function buildCronExpression(input: CronScheduleInput): string {
  if (input.mode === 'daily') return `${input.minute} ${input.hour} * * *`
  if (input.mode === 'weekly') return `${input.minute} ${input.hour} * * ${input.weekday}`
  return input.customExpression.trim()
}

/** 两位补零的 HH:MM 展示串。 */
export function formatCronTime(hour: number, minute: number): string {
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
}
