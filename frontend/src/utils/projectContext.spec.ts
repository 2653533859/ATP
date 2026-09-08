import { describe, expect, it } from 'vitest'

import {
  projectContextRenderKey,
  projectIdFromQuery,
  projectSelectionLocation,
  selectAvailableProjectId,
} from './projectContext'

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

  it('changes the real route project context for query and parameter routes', () => {
    expect(projectSelectionLocation({ name: 'cases', params: {}, path: '/cases', query: { keyword: 'login' } }, 7)).toEqual({
      path: '/cases',
      query: { keyword: 'login', project_id: '7' },
    })
    expect(projectSelectionLocation({ name: 'project-cases', params: { projectId: '3' }, path: '/projects/3/cases', query: {} }, 7)).toEqual({
      name: 'project-cases',
      params: { projectId: '7' },
      query: { project_id: '7' },
    })
  })

  it('changes the routed page key when the selected project changes', () => {
    expect(projectContextRenderKey({ name: 'hermes', params: {}, path: '/hermes', query: { project_id: '3' } })).toBe('hermes:3')
    expect(projectContextRenderKey({ name: 'hermes', params: {}, path: '/hermes', query: { project_id: '7' } })).toBe('hermes:7')
    expect(projectContextRenderKey({ name: 'project-cases', params: { projectId: '5' }, path: '/projects/5/cases', query: {} })).toBe('project-cases:5')
  })
})
