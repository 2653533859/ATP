// DashboardView 的可测纯逻辑：日期区间生成、趋势缺口补零、布局归一化。
// 图表 option 构建、i18n 文案与 echarts 交互留在视图层。

export type DashboardChartKey =
  | 'pass_rate_trend'
  | 'duration_trend'
  | 'failure_top'
  | 'executor_top'
  | 'trigger_type'
  | 'plan_trend'
  | 'suite_trend'
  | 'case_type_distribution'

export interface DashboardLayoutItem {
  key: DashboardChartKey
  visible: boolean
}

export const DEFAULT_DASHBOARD_LAYOUT: DashboardLayoutItem[] = [
  { key: 'pass_rate_trend', visible: true },
  { key: 'duration_trend', visible: true },
  { key: 'failure_top', visible: true },
  { key: 'executor_top', visible: true },
  { key: 'trigger_type', visible: true },
  { key: 'plan_trend', visible: true },
  { key: 'suite_trend', visible: true },
  { key: 'case_type_distribution', visible: true },
]

export function cloneDefaultDashboardLayout(): DashboardLayoutItem[] {
  return DEFAULT_DASHBOARD_LAYOUT.map((item) => ({ ...item }))
}

/**
 * 归一化持久化的布局：丢弃未知 key / 结构错误项，保留已知项的顺序与可见性，
 * 补齐缺失的默认项；完全无有效项则回退默认。
 */
export function normalizeDashboardLayout(value: unknown): DashboardLayoutItem[] {
  if (!Array.isArray(value)) return cloneDefaultDashboardLayout()
  const parsed = value as Array<Partial<DashboardLayoutItem>>
  const seenKeys = new Set(parsed.map((item) => item.key))
  const knownKeys = new Set(DEFAULT_DASHBOARD_LAYOUT.map((item) => item.key))
  const ordered = parsed
    .filter(
      (item): item is DashboardLayoutItem =>
        Boolean(item.key && knownKeys.has(item.key) && typeof item.visible === 'boolean'),
    )
    .map((item) => ({ key: item.key, visible: item.visible }))
  for (const defaultItem of DEFAULT_DASHBOARD_LAYOUT) {
    if (!seenKeys.has(defaultItem.key)) ordered.push({ ...defaultItem })
  }
  return ordered.length ? ordered : cloneDefaultDashboardLayout()
}

/** 生成 [start, end] 闭区间内逐日的 YYYY-MM-DD 列表（含端点）。 */
export function generateDateRange(startDate: string, endDate: string): string[] {
  const dates: string[] = []
  const current = new Date(startDate)
  const end = new Date(endDate)
  while (current <= end) {
    dates.push(current.toISOString().slice(0, 10))
    current.setDate(current.getDate() + 1)
  }
  return dates
}

/**
 * 按 [today-numDays+1, today] 的每一天补齐趋势数据缺口。
 * weekly 聚合时不补零（密度低，X 轴是周一日期）；空数据直接返回空。
 * `today` 可注入以便测试（默认取当前日期）。
 */
export function fillTrendGaps<T extends { date: string }>(
  data: T[],
  numDays: number,
  makeZero: (date: string) => T,
  options: { weekly?: boolean; today?: Date } = {},
): T[] {
  if (data.length === 0) return []
  if (options.weekly) return data

  const today = options.today ?? new Date()
  const start = new Date(today)
  start.setDate(start.getDate() - numDays + 1)

  const allDates = generateDateRange(start.toISOString().slice(0, 10), today.toISOString().slice(0, 10))
  const dataMap = new Map(data.map((item) => [item.date, item]))

  return allDates.map((date) => dataMap.get(date) ?? makeZero(date))
}
