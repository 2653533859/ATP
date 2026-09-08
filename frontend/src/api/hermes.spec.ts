import { beforeEach, describe, expect, it, vi } from 'vitest'

const httpMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}))

vi.mock('./http', () => ({ default: httpMock }))

import { hermesApi } from './hermes'

describe('hermesApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('keeps query and orchestration contracts on their dedicated endpoints', () => {
    const query = { project_id: 7, query: '查看失败任务', conversation_id: 'conversation-1' }

    hermesApi.query(query)
    hermesApi.orchestrate(query)

    expect(httpMock.post).toHaveBeenNthCalledWith(1, '/hermes/query', query)
    expect(httpMock.post).toHaveBeenNthCalledWith(2, '/hermes/orchestrate', query)
  })

  it('keeps tool catalog and tool execution contracts', () => {
    const call = {
      project_id: 7,
      conversation_id: 'conversation-1',
      tool: 'run_detail' as const,
      arguments: { task_type: 'case', run_id: 23 },
    }

    hermesApi.listTools()
    hermesApi.executeTool(call)

    expect(httpMock.get).toHaveBeenCalledWith('/hermes/tools')
    expect(httpMock.post).toHaveBeenCalledWith('/hermes/tools/execute', call)
  })

  it('keeps session, draft confirmation, feedback and governance routes stable', () => {
    hermesApi.sessions(7)
    hermesApi.createSession(7, '发布排查')
    hermesApi.createDraft(11, {
      project_id: 7,
      draft_type: 'test_plan',
      payload: { name: '回归计划' },
    })
    hermesApi.confirmDraft(11, { project_id: 7, draft_id: 'draft-1', confirmation: 'CONFIRM' })
    hermesApi.feedback(11, { project_id: 7, message_index: 3, rating: 'helpful' })
    hermesApi.governance(7)

    expect(httpMock.get).toHaveBeenNthCalledWith(1, '/hermes/sessions', { params: { project_id: 7 } })
    expect(httpMock.post).toHaveBeenNthCalledWith(1, '/hermes/sessions', { project_id: 7, title: '发布排查' })
    expect(httpMock.post).toHaveBeenNthCalledWith(2, '/hermes/sessions/11/drafts', {
      project_id: 7,
      draft_type: 'test_plan',
      payload: { name: '回归计划' },
    })
    expect(httpMock.post).toHaveBeenNthCalledWith(3, '/hermes/sessions/11/drafts/confirm', {
      project_id: 7,
      draft_id: 'draft-1',
      confirmation: 'CONFIRM',
    })
    expect(httpMock.post).toHaveBeenNthCalledWith(4, '/hermes/sessions/11/feedback', {
      project_id: 7,
      message_index: 3,
      rating: 'helpful',
    })
    expect(httpMock.get).toHaveBeenNthCalledWith(2, '/hermes/governance/summary', {
      params: { project_id: 7 },
    })
  })
})
