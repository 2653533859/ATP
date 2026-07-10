import { describe, expect, it } from 'vitest'

import {
  addMobileRunTaskFallback,
  buildMobileRunQuery,
  filterMobileRunsByDateRange,
  summarizeMobileTrend,
} from './mobileReport'

function run(id: number, startedAt: string | null, taskName = '') {
  return {
    id,
    task_id: id + 100,
    task_name: taskName,
    task_type: 'performance' as const,
    status: 'completed' as const,
    started_at: startedAt,
    summary_json: {},
    config_snapshot: {},
    trigger_type: 'manual' as const,
    created_at: '2026-07-01T00:00:00Z',
    updated_at: '2026-07-01T00:00:00Z',
  }
}

describe('mobile report helpers', () => {
  it('builds list queries only from active filters', () => {
    expect(buildMobileRunQuery({})).toEqual({ limit: 100 })
    expect(buildMobileRunQuery({ projectId: 4, taskType: 'stability', status: 'failed', limit: 25 })).toEqual({
      project_id: 4,
      task_type: 'stability',
      status_filter: 'failed',
      limit: 25,
    })
  })

  it('uses an inclusive start and exclusive next-day date boundary', () => {
    const runs = [
      run(1, '2026-07-01T00:00:00Z'),
      run(2, '2026-07-02T23:59:59Z'),
      run(3, '2026-07-03T00:00:00Z'),
      run(4, null),
    ]

    expect(filterMobileRunsByDateRange(runs, ['2026-07-01T00:00:00Z', '2026-07-02T00:00:00Z']).map((item) => item.id)).toEqual([1, 2])
    expect(filterMobileRunsByDateRange(runs, null)).toBe(runs)
  })

  it('accepts date-picker-like values and fills missing task names', () => {
    const start = { valueOf: () => Date.parse('2026-07-01T00:00:00Z') }
    const end = { valueOf: () => Date.parse('2026-07-01T00:00:00Z') }
    const filtered = filterMobileRunsByDateRange([run(1, '2026-07-01T12:00:00Z')], [start, end])

    expect(addMobileRunTaskFallback(filtered, (taskId) => `Task ${taskId}`)[0].task_name).toBe('Task 101')
    expect(addMobileRunTaskFallback([run(2, '2026-07-01T12:00:00Z', 'Existing')], () => 'Fallback')[0].task_name).toBe('Existing')
  })

  it('summarizes completed and failed trend totals', () => {
    expect(summarizeMobileTrend([
      { completed: 3, failed: 1 },
      { completed: 2, failed: 4 },
    ])).toEqual({ completed: 5, failed: 5 })
  })
})
