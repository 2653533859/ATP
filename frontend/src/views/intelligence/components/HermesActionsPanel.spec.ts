import { flushPromises, shallowMount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import HermesActionsPanel from './HermesActionsPanel.vue'

const { getHistory } = vi.hoisted(() => ({ getHistory: vi.fn() }))

vi.mock('@/api/http', () => ({ default: { get: getHistory } }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: { id: 7 } }) }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))

beforeEach(() => {
  getHistory.mockReset()
  sessionStorage.clear()
})

describe('HermesActionsPanel history', () => {
  it('discards an old project response and loads the newly selected project', async () => {
    type HistoryRow = { command_id: string; action: string; resource_id: number; created_at: string }
    const resolvers: Array<(rows: HistoryRow[]) => void> = []
    getHistory.mockImplementation(() => new Promise<HistoryRow[]>(resolve => { resolvers.push(resolve) }))

    const wrapper = shallowMount(HermesActionsPanel, {
      props: { projectId: 1, canModify: true, latestAnswer: '' },
    })
    expect(getHistory).toHaveBeenCalledWith('/hermes/action-records', { params: { project_id: 1 } })

    await wrapper.setProps({ projectId: 2 })
    await nextTick()
    expect(getHistory).toHaveBeenCalledWith('/hermes/action-records', { params: { project_id: 2 } })
    expect(resolvers).toHaveLength(2)

    resolvers[0]([{ command_id: 'old-project', action: 'defect', resource_id: 11, created_at: '2026-10-12T00:00:00Z' }])
    await flushPromises()
    expect(sessionStorage.getItem('atp-hermes-receipts-v1:7:2')).toBeNull()

    resolvers[1]([{ command_id: 'new-project', action: 'defect', resource_id: 22, created_at: '2026-10-12T00:00:00Z' }])
    await flushPromises()
    const saved = sessionStorage.getItem('atp-hermes-receipts-v1:7:2') || ''
    expect(saved).toContain('new-project')
    expect(saved).not.toContain('old-project')

    wrapper.unmount()
  })
})
