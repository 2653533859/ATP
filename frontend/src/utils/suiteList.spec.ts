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
