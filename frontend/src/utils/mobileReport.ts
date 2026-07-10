import dayjs from 'dayjs'
import type { MobileRunStatus, MobileSpecialRunItem, TaskType } from '@/api'

// antd RangePicker 产出 Dayjs；同时兼容字符串/数字/Date。dayjs() 原生接受这些形态。
export type DateRangeValue = string | number | Date | { valueOf(): number }

export function buildMobileRunQuery(filters: {
  projectId?: number | null
  taskType?: TaskType | null
  status?: MobileRunStatus | null
  limit?: number
}) {
  return {
    ...(filters.projectId ? { project_id: filters.projectId } : {}),
    ...(filters.taskType ? { task_type: filters.taskType } : {}),
    ...(filters.status ? { status_filter: filters.status } : {}),
    limit: filters.limit ?? 100,
  }
}

export function filterMobileRunsByDateRange(
  runs: MobileSpecialRunItem[],
  dateRange: [DateRangeValue, DateRangeValue] | null,
): MobileSpecialRunItem[] {
  if (!dateRange) return runs
  const start = dayjs(dateRange[0] as dayjs.ConfigType).valueOf()
  const endExclusive = dayjs(dateRange[1] as dayjs.ConfigType).valueOf() + 86_400_000
  return runs.filter((run) => {
    if (!run.started_at) return false
    const startedAt = dayjs(run.started_at).valueOf()
    return startedAt >= start && startedAt < endExclusive
  })
}

export function addMobileRunTaskFallback(
  runs: MobileSpecialRunItem[],
  fallback: (taskId: number) => string,
): MobileSpecialRunItem[] {
  return runs.map((run) => ({
    ...run,
    task_name: run.task_name || fallback(run.task_id),
  }))
}

export function summarizeMobileTrend(trend: Array<{ completed: number; failed: number }>) {
  return trend.reduce(
    (summary, item) => ({
      completed: summary.completed + item.completed,
      failed: summary.failed + item.failed,
    }),
    { completed: 0, failed: 0 },
  )
}
