import { describe, expect, it } from 'vitest'

import { extractApiError } from './apiError'

describe('extractApiError', () => {
  it('extracts messages from top-level validation error arrays', () => {
    expect(extractApiError([{ msg: '字段不能为空' }, { msg: '格式非法' }], 'fallback')).toBe('字段不能为空; 格式非法')
    expect(extractApiError(['direct error'], 'fallback')).toBe('direct error')
    expect(extractApiError([], 'fallback')).toBe('fallback')
  })

  it('extracts string, Axios detail array, and Error message inputs', () => {
    expect(extractApiError('  permission denied  ', 'fallback')).toBe('permission denied')
    expect(extractApiError({ response: { data: { detail: [{ msg: 'invalid' }] } } }, 'fallback')).toBe('invalid')
    expect(extractApiError(new Error('network error'), 'fallback')).toBe('network error')
    expect(extractApiError(null, 'fallback')).toBe('fallback')
  })
})
