import { describe, expect, it } from 'vitest'

import {
  buildCaseDetailLocation,
  buildCasesQuery,
  buildProjectCasesLocation,
  parsePositiveInt,
  parsePositiveIntList,
  parseRouteText,
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
    expect(parsePositiveIntList('2, 3, 2, bad, -1')).toEqual([2, 3])
  })

  it('keeps only supported review status route values', () => {
    expect(parseReviewStatus('pending')).toBe('pending')
    expect(parseReviewStatus(['approved'])).toBe('approved')
    expect(parseReviewStatus('rejected')).toBe('rejected')
    expect(parseReviewStatus('draft')).toBeUndefined()
    expect(parseReviewStatus(undefined)).toBeUndefined()
  })

  it('builds compact case list and detail locations', () => {
    expect(buildCasesQuery({
      projectId: 12,
      moduleId: 34,
      keyword: '  登录  ',
      reviewStatus: 'pending',
      aiGenerate: true,
      aiDatasetId: 56,
      aiDatasetVersion: 3,
      aiMockRuleIds: [78, 79],
    })).toEqual({
      project_id: '12',
      module_id: '34',
      keyword: '登录',
      review_status: 'pending',
      ai_generate: '1',
      ai_dataset_id: '56',
      ai_dataset_version: '3',
      ai_mock_rule_ids: '78,79',
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
      query: { project_id: '11', module_id: '22', keyword: '  登录  ', review_status: 'approved' },
      params: { projectId: '33' },
    })).toEqual({
      projectId: 11,
      moduleId: 22,
      keyword: '登录',
      reviewStatus: 'approved',
      aiGenerate: false,
      aiDatasetId: null,
      aiDatasetVersion: null,
      aiMockRuleIds: [],
    })

    expect(readCaseRouteSelection({
      query: { project_id: 'bad', module_id: 'missing', review_status: 'unknown' },
      params: { projectId: '33' },
    })).toEqual({
      projectId: 33,
      moduleId: null,
      keyword: undefined,
      reviewStatus: undefined,
      aiGenerate: false,
      aiDatasetId: null,
      aiDatasetVersion: null,
      aiMockRuleIds: [],
    })

    expect(readCaseRouteSelection({
      query: { project_id: '11', ai_generate: '1', ai_dataset_id: '56', ai_mock_rule_ids: '78,79,78' },
      params: {},
    })).toMatchObject({
      keyword: undefined,
      aiGenerate: true,
      aiDatasetId: 56,
      aiDatasetVersion: null,
      aiMockRuleIds: [78, 79],
    })
  })

  it('normalizes a route keyword', () => {
    expect(parseRouteText('  登录  ')).toBe('登录')
    expect(parseRouteText(['接口', '用例'])).toBe('接口')
    expect(parseRouteText('   ')).toBeUndefined()
    expect(parseRouteText(undefined)).toBeUndefined()
  })
})
