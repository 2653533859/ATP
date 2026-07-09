import { describe, expect, it } from 'vitest'

import {
  buildCaseDetailLocation,
  buildCasesQuery,
  buildProjectCasesLocation,
  parsePositiveInt,
  parseReviewStatus,
  readCaseRouteSelection,
} from './caseNavigation'

describe('case navigation utilities', () => {
  it('parses route ids defensively', () => {
    expect(parsePositiveInt('42')).toBe(42)
    expect(parsePositiveInt(['7', '8'])).toBe(7)
    expect(parsePositiveInt(3)).toBe(3)
    expect(parsePositiveInt('0')).toBeNull()
    expect(parsePositiveInt('-1')).toBeNull()
    expect(parsePositiveInt('abc')).toBeNull()
    expect(parsePositiveInt(undefined)).toBeNull()
  })

  it('keeps only supported review status route values', () => {
    expect(parseReviewStatus('pending')).toBe('pending')
    expect(parseReviewStatus(['approved'])).toBe('approved')
    expect(parseReviewStatus('rejected')).toBe('rejected')
    expect(parseReviewStatus('draft')).toBeUndefined()
    expect(parseReviewStatus(undefined)).toBeUndefined()
  })

  it('builds compact case list and detail locations', () => {
    expect(buildCasesQuery({ projectId: 12, moduleId: 34, reviewStatus: 'pending' })).toEqual({
      project_id: '12',
      module_id: '34',
      review_status: 'pending',
    })
    expect(buildCasesQuery({ projectId: null, moduleId: 0 })).toEqual({})
    expect(buildProjectCasesLocation(9)).toEqual({
      name: 'cases',
      query: { project_id: '9' },
    })
    expect(buildCaseDetailLocation(88, { projectId: 9, moduleId: 10 })).toEqual({
      name: 'case-detail',
      params: { caseId: '88' },
      query: { project_id: '9', module_id: '10' },
    })
  })

  it('prefers project_id query over projectId params when reading selection', () => {
    expect(readCaseRouteSelection({
      query: { project_id: '11', module_id: '22', review_status: 'approved' },
      params: { projectId: '33' },
    })).toEqual({
      projectId: 11,
      moduleId: 22,
      reviewStatus: 'approved',
    })

    expect(readCaseRouteSelection({
      query: { project_id: 'bad', module_id: 'missing', review_status: 'unknown' },
      params: { projectId: '33' },
    })).toEqual({
      projectId: 33,
      moduleId: null,
      reviewStatus: undefined,
    })
  })
})
