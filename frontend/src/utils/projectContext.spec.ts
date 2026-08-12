import { describe, expect, it } from 'vitest'

import { projectIdFromQuery, selectAvailableProjectId } from './projectContext'

describe('project context', () => {
  it('parses a valid project query and rejects invalid values', () => {
    expect(projectIdFromQuery('12')).toBe(12)
    expect(projectIdFromQuery(['7', '8'])).toBe(7)
    expect(projectIdFromQuery('0')).toBeUndefined()
    expect(projectIdFromQuery('bad')).toBeUndefined()
  })

  it('keeps an accessible requested project and otherwise falls back', () => {
    const projects = [{ id: 3 }, { id: 7 }]
    expect(selectAvailableProjectId(7, projects)).toBe(7)
    expect(selectAvailableProjectId(99, projects)).toBe(3)
    expect(selectAvailableProjectId(undefined, [])).toBeUndefined()
  })
})
