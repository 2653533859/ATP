import { describe, expect, it } from 'vitest'

import type { CaseSummaryItem, ModuleTreeItem } from '@/api'
import {
  caseWorkflowGuards,
  collectActiveFilters,
  countFlakyCases,
  countPendingReviews,
  filterCasesByLevel,
  flakyTooltipParams,
  flattenModules,
} from './caseList'

function caseItem(overrides: Partial<CaseSummaryItem> = {}): CaseSummaryItem {
  return {
    id: 1,
    name: 'case',
    case_code: 'ATP-1',
    summary: '',
    case_type: 'api',
    case_level: 'core',
    priority: 'P1',
    status: 'active',
    review_status: 'approved',
    automation_status: 'automated',
    module_id: 1,
    tags: [],
    is_ready_for_execution: true,
    created_at: '',
    updated_at: '',
    creator_id: 1,
    ...overrides,
  } as CaseSummaryItem
}

describe('case list helpers', () => {
  it('filters by level and computes summary counts', () => {
    const cases = [
      caseItem({ id: 1, case_level: 'smoke', review_status: 'pending' }),
      caseItem({ id: 2, case_level: 'core', flaky_stats: { is_flaky: true, total_runs: 8, passed_runs: 5, failed_runs: 2, error_runs: 1, failure_rate: 37.5, window_size: 10 } }),
      caseItem({ id: 3, case_level: 'core', review_status: 'pending' }),
    ]

    expect(filterCasesByLevel(cases, 'core').map((c) => c.id)).toEqual([2, 3])
    expect(filterCasesByLevel(cases, null)).toHaveLength(3)
    expect(countPendingReviews(cases)).toBe(2)
    expect(countFlakyCases(cases)).toBe(1)
  })

  it('collects only active filters with trimmed keyword', () => {
    const active = collectActiveFilters({
      keyword: '  登录  ',
      type: 'api',
      priority: null,
      level: null,
      status: 'active',
      review_status: null,
      automation_status: null,
    })

    expect(active).toEqual([
      { key: 'keyword', value: '登录' },
      { key: 'type', value: 'api' },
      { key: 'status', value: 'active' },
    ])
    expect(collectActiveFilters({ keyword: '   ', type: null, priority: null, level: null, status: null, review_status: null, automation_status: null })).toEqual([])
  })

  it('guards review workflow actions by status machine and role ability', () => {
    const ability = { canModify: true, canApprove: true }

    expect(caseWorkflowGuards({ status: 'active', review_status: 'rejected' }, ability)).toEqual({
      submitReview: true,
      approve: false,
      reject: false,
      deprecate: true,
      reactivate: false,
    })
    expect(caseWorkflowGuards({ status: 'active', review_status: 'pending' }, ability)).toMatchObject({
      submitReview: false,
      approve: true,
      reject: true,
    })
    expect(caseWorkflowGuards({ status: 'deprecated', review_status: 'approved' }, ability)).toMatchObject({
      submitReview: false,
      approve: false,
      deprecate: false,
      reactivate: true,
    })
    // 只读角色一切工作流动作隐藏
    const readonly = caseWorkflowGuards({ status: 'active', review_status: 'pending' }, { canModify: false, canApprove: false })
    expect(Object.values(readonly).every((allowed) => allowed === false)).toBe(true)
  })

  it('builds flaky tooltip params merging failed and error runs', () => {
    expect(flakyTooltipParams(undefined)).toBeNull()
    expect(flakyTooltipParams({ is_flaky: false, total_runs: 0, passed_runs: 0, failed_runs: 0, error_runs: 0, failure_rate: 0, window_size: 10 })).toBeNull()
    expect(
      flakyTooltipParams({ is_flaky: true, total_runs: 10, passed_runs: 6, failed_runs: 3, error_runs: 1, failure_rate: 40, window_size: 10 }),
    ).toEqual({ total: 10, passed: 6, failed: 4, rate: 40 })
  })

  it('flattens nested module trees into an id-name map', () => {
    const tree = [
      { id: 1, name: '根', project_id: 1, sort_order: 0, children: [
        { id: 2, name: '子', project_id: 1, sort_order: 0, children: [] },
        { id: 3, name: '兄弟', project_id: 1, sort_order: 1, children: [
          { id: 4, name: '孙', project_id: 1, sort_order: 0, children: [] },
        ] },
      ] },
    ] as unknown as ModuleTreeItem[]

    expect(flattenModules(tree)).toEqual({ 1: '根', 2: '子', 3: '兄弟', 4: '孙' })
  })
})
