import { describe, expect, it } from 'vitest'

import {
  formatDuration,
  formatPercent,
  getCronValidationErrorKey,
  getPlanRunFailureCount,
  getPlanRunFailureItems,
  getPlanRunPassRate,
  getPlanRunTotalCount,
  normalizePlanConfig,
  parseCronPreset,
  runStatusColor,
  scheduleColor,
  validateCronField,
} from './planList'

describe('plan list utilities', () => {
  it('normalizes plan execution config defensively', () => {
    expect(normalizePlanConfig()).toEqual({
      execution_mode: 'sequential',
      max_workers: 3,
      fail_strategy: 'continue',
      min_pass_rate: 0.8,
    })

    expect(normalizePlanConfig({
      execution_mode: 'parallel',
      max_workers: 12.9,
      fail_strategy: 'fast-fail',
      min_pass_rate: 1.5,
    })).toEqual({
      execution_mode: 'parallel',
      max_workers: 10,
      fail_strategy: 'fast-fail',
      min_pass_rate: 1,
    })

    expect(normalizePlanConfig({
      execution_mode: 'invalid',
      max_workers: 0,
      fail_strategy: 'stop',
      min_pass_rate: -1,
    })).toEqual({
      execution_mode: 'sequential',
      max_workers: 3,
      fail_strategy: 'continue',
      min_pass_rate: 0,
    })
  })

  it('validates cron fields and full expressions', () => {
    expect(validateCronField('*', 0, 59)).toBe(true)
    expect(validateCronField('*/15', 0, 59)).toBe(true)
    expect(validateCronField('1,15,30', 0, 59)).toBe(true)
    expect(validateCronField('9-17', 0, 23)).toBe(true)
    expect(validateCronField('17-9', 0, 23)).toBe(false)
    expect(validateCronField('60', 0, 59)).toBe(false)

    expect(getCronValidationErrorKey('')).toBe('required')
    expect(getCronValidationErrorKey('* * * *')).toBe('parts')
    expect(getCronValidationErrorKey('60 * * * *')).toBe('minute')
    expect(getCronValidationErrorKey('* 24 * * *')).toBe('hour')
    expect(getCronValidationErrorKey('* * 0 * *')).toBe('day')
    expect(getCronValidationErrorKey('* * * 13 *')).toBe('month')
    expect(getCronValidationErrorKey('* * * * 7')).toBe('weekday')
    expect(getCronValidationErrorKey('*/30 9-18 * * 1,5')).toBe('')
  })

  it('parses cron presets for daily, weekly, and custom modes', () => {
    expect(parseCronPreset('30 9 * * *')).toEqual({
      mode: 'daily',
      minute: 30,
      hour: 9,
      weekday: 1,
      customExpression: '30 9 * * *',
    })
    expect(parseCronPreset('15 22 * * 5')).toEqual({
      mode: 'weekly',
      minute: 15,
      hour: 22,
      weekday: 5,
      customExpression: '15 22 * * 5',
    })
    expect(parseCronPreset('*/20 * * * *')).toEqual({
      mode: 'custom',
      minute: 0,
      hour: 9,
      weekday: 1,
      customExpression: '*/20 * * * *',
    })
  })

  it('summarizes plan run results and maps colors', () => {
    const run = {
      result_summary: { total: 4, passed: 1, failed: 1, error: 1 },
      suite_run_ids: [
        { status: 'passed', suite_id: 1 },
        { status: 'failed', suite_id: 2 },
        { status: 'error', suite_id: 3 },
      ],
    }

    expect(getPlanRunTotalCount(run)).toBe(4)
    expect(getPlanRunFailureCount(run)).toBe(2)
    expect(getPlanRunPassRate(run)).toBe(25)
    expect(getPlanRunFailureItems(run)).toEqual([
      { status: 'failed', suite_id: 2 },
      { status: 'error', suite_id: 3 },
    ])
    expect(getPlanRunTotalCount({ suite_run_ids: [{ status: 'passed' }] })).toBe(1)
    expect(scheduleColor('cron')).toBe('blue')
    expect(scheduleColor('webhook')).toBe('orange')
    expect(scheduleColor('custom')).toBe('default')
    expect(runStatusColor('passed')).toBe('success')
    expect(runStatusColor('error')).toBe('warning')
    expect(runStatusColor('custom')).toBe('default')
    expect(formatDuration(1500)).toBe('1.5s')
    expect(formatPercent(66.66)).toBe('66.7%')
  })
})
