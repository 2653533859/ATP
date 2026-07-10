import { describe, expect, it } from 'vitest'

import {
  formatDuration,
  formatPercent,
  getSuiteRunCompletedCount,
  getSuiteRunFailureCount,
  getSuiteRunFailureItems,
  getSuiteRunPassRate,
  getSuiteRunProgressPercent,
  getSuiteRunProgressStatus,
  getSuiteRunTotalCount,
  hasActiveSuiteRuns,
  normalizeSuiteConfig,
  runStatusBadge,
  suiteExecutionModeColor,
  suiteFailStrategyColor,
} from './suiteList'

describe('suite list utilities', () => {
  it('normalizes suite execution config defensively', () => {
    expect(normalizeSuiteConfig()).toEqual({
      execution_mode: 'sequential',
      max_workers: 5,
      fail_strategy: 'continue',
      min_pass_rate: 0.8,
    })

    expect(normalizeSuiteConfig({
      execution_mode: 'parallel',
      max_workers: 25.6,
      fail_strategy: 'require-minimum-pass-rate',
      min_pass_rate: 1.2,
    })).toEqual({
      execution_mode: 'parallel',
      max_workers: 20,
      fail_strategy: 'require-minimum-pass-rate',
      min_pass_rate: 1,
    })

    expect(normalizeSuiteConfig({
      execution_mode: 'unknown',
      max_workers: 'bad',
      fail_strategy: 'stop',
      min_pass_rate: -0.5,
    })).toEqual({
      execution_mode: 'sequential',
      max_workers: 5,
      fail_strategy: 'continue',
      min_pass_rate: 0,
    })
  })

  it('maps suite strategy and run status colors', () => {
    expect(suiteExecutionModeColor('parallel')).toBe('blue')
    expect(suiteExecutionModeColor('sequential')).toBe('default')
    expect(suiteFailStrategyColor('fast-fail')).toBe('volcano')
    expect(suiteFailStrategyColor('require-minimum-pass-rate')).toBe('purple')
    expect(suiteFailStrategyColor('unknown')).toBe('default')
    expect(runStatusBadge('running')).toBe('processing')
    expect(runStatusBadge('failed')).toBe('error')
    expect(runStatusBadge('custom')).toBe('default')
  })

  it('summarizes suite run results from summary with detail fallback', () => {
    const run = {
      status: 'running',
      result_summary: { total: 5, passed: 2, failed: 1, error: 1, skipped: 1 },
      case_run_ids: [
        { status: 'passed' },
        { status: 'failed', case_id: 2 },
        { status: 'error', case_id: 3 },
      ],
    }

    expect(getSuiteRunTotalCount(run)).toBe(5)
    expect(getSuiteRunFailureCount(run)).toBe(2)
    expect(getSuiteRunPassRate(run)).toBe(40)
    expect(getSuiteRunCompletedCount(run)).toBe(5)
    expect(getSuiteRunProgressPercent(run)).toBe(100)
    expect(getSuiteRunFailureItems(run)).toEqual([
      { status: 'failed', case_id: 2 },
      { status: 'error', case_id: 3 },
    ])

    expect(getSuiteRunTotalCount({ status: 'pending', case_run_ids: [{ status: 'passed' }] })).toBe(1)
    expect(getSuiteRunPassRate({ status: 'pending' })).toBe(0)
  })

  it('formats display values and detects active runs', () => {
    expect(formatDuration(null)).toBe('-')
    expect(formatDuration(999)).toBe('999 ms')
    expect(formatDuration(1250)).toBe('1.3s')
    expect(formatPercent(33.36)).toBe('33.4%')
    expect(getSuiteRunProgressStatus({ status: 'failed' })).toBe('exception')
    expect(getSuiteRunProgressStatus({ status: 'passed' })).toBe('success')
    expect(getSuiteRunProgressStatus({ status: 'running' })).toBe('active')
    expect(hasActiveSuiteRuns([{ status: 'passed' }, { status: 'running' }])).toBe(true)
    expect(hasActiveSuiteRuns([{ status: 'passed' }, { status: 'failed' }])).toBe(false)
  })
})

import {
  buildModuleDescendantMap,
  buildModuleTreeOptions,
  caseExecutionReasonKey,
  passesSuiteCaseStructuralFilter,
  type SuiteCandidateCase,
  type SuiteModuleNode,
} from './suiteList'

const MODULE_TREE: SuiteModuleNode[] = [
  {
    id: 1,
    name: '根',
    children: [
      { id: 2, name: '子A', children: [{ id: 4, name: '孙', children: [] }] },
      { id: 3, name: '子B', children: [] },
    ],
  },
]

describe('suite list module + case selection helpers', () => {
  it('maps each module to its descendant id set', () => {
    const map = buildModuleDescendantMap(MODULE_TREE)
    expect([...(map.get(1) ?? [])].sort((a, b) => a - b)).toEqual([1, 2, 3, 4])
    expect([...(map.get(2) ?? [])].sort((a, b) => a - b)).toEqual([2, 4])
    expect([...(map.get(3) ?? [])]).toEqual([3])
    expect([...(map.get(4) ?? [])]).toEqual([4])
  })

  it('prunes empty branches from tree-select options', () => {
    // 只有模块 4 有可用用例：子A 因含 4 保留，子B 被剪掉
    const options = buildModuleTreeOptions(MODULE_TREE, new Set([4]))
    expect(options).toEqual([
      {
        title: '根',
        value: 1,
        key: 1,
        children: [
          { title: '子A', value: 2, key: 2, children: [{ title: '孙', value: 4, key: 4, children: undefined }] },
        ],
      },
    ])
    expect(buildModuleTreeOptions(MODULE_TREE, new Set())).toEqual([])
  })

  it('classifies case execution blockers by precedence', () => {
    expect(caseExecutionReasonKey({ status: 'draft', review_status: 'approved', automation_status: 'auto' })).toBe('status_not_active')
    expect(caseExecutionReasonKey({ status: 'active', review_status: 'pending', automation_status: 'auto' })).toBe('review_not_approved')
    expect(caseExecutionReasonKey({ status: 'active', review_status: 'approved', automation_status: 'manual' })).toBe('not_automation')
    expect(caseExecutionReasonKey({ status: 'active', review_status: 'approved', automation_status: 'semi_auto' })).toBeNull()
  })

  it('applies structural case filters (module/type/ready/scope)', () => {
    const descendants = buildModuleDescendantMap(MODULE_TREE)
    const cases: SuiteCandidateCase[] = [
      { id: 10, module_id: 4, case_type: 'api', is_ready_for_execution: true },
      { id: 11, module_id: 3, case_type: 'web', is_ready_for_execution: false },
      { id: 12, module_id: 2, case_type: 'api', is_ready_for_execution: true },
    ]
    const selected = new Set([12])
    const base = { moduleId: undefined, caseType: undefined, readyFilter: 'all' as const, selectionScope: 'all' as const }

    const byModule = cases.filter((c) => passesSuiteCaseStructuralFilter(c, { ...base, moduleId: 2 }, selected, descendants))
    expect(byModule.map((c) => c.id)).toEqual([10, 12]) // 模块 2 含后代 4

    const byType = cases.filter((c) => passesSuiteCaseStructuralFilter(c, { ...base, caseType: 'api' }, selected, descendants))
    expect(byType.map((c) => c.id)).toEqual([10, 12])

    const ready = cases.filter((c) => passesSuiteCaseStructuralFilter(c, { ...base, readyFilter: 'not_ready' }, selected, descendants))
    expect(ready.map((c) => c.id)).toEqual([11])

    const unselected = cases.filter((c) => passesSuiteCaseStructuralFilter(c, { ...base, selectionScope: 'unselected' }, selected, descendants))
    expect(unselected.map((c) => c.id)).toEqual([10, 11])

    const onlySelected = cases.filter((c) => passesSuiteCaseStructuralFilter(c, { ...base, selectionScope: 'selected' }, selected, descendants))
    expect(onlySelected.map((c) => c.id)).toEqual([12])
  })
})
