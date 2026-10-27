import { mount, flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import CloudSyncDashboard from './CloudSyncDashboard.vue'

const { getStatsMock, listRunsMock, getRunDetailMock, syncNowMock, getLocalStatusMock, currentRuntimeMode } = vi.hoisted(() => ({
  getStatsMock: vi.fn(),
  listRunsMock: vi.fn(),
  getRunDetailMock: vi.fn(),
  syncNowMock: vi.fn(),
  getLocalStatusMock: vi.fn(),
  currentRuntimeMode: { mode: 'server' },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (_k: string, fallback?: string) => fallback || _k }),
}))

vi.mock('ant-design-vue', () => ({
  message: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

vi.mock('@/api', () => ({
  cloudSyncApi: {
    getStats: getStatsMock,
    listRuns: listRunsMock,
    getRunDetail: getRunDetailMock,
    syncNow: syncNowMock,
    getLocalStatus: getLocalStatusMock,
  },
}))

vi.mock('@/runtimeMode', () => ({
  getRuntimeMode: () => currentRuntimeMode,
}))

const MOCK_STATS = {
  total_runs: 5,
  status_distribution: { passed: 4, failed: 1 },
  type_distribution: { case: 5 },
  connected_clients: [
    { client_id: 'win-client-01', machine_name: 'DESKTOP-TEST', runs_count: 5 },
  ],
}

const MOCK_RUNS = {
  items: [
    {
      id: 1,
      client_id: 'win-client-01',
      machine_name: 'DESKTOP-TEST',
      unique_key: 'win-client-01:case:101',
      run_type: 'case',
      run_id: 101,
      project_name: 'Project Alpha',
      project_code: 'ALPHA',
      title: 'Login Smoke Test',
      status: 'passed',
      duration_ms: 320,
      triggered_by: 'admin',
      metrics: { total_steps: 2, passed_steps: 2 },
      error_summary: null,
      step_count: 2,
      reported_at: '2026-10-26T12:00:00.000Z',
    },
  ],
  total: 1,
  page: 1,
  page_size: 20,
}

describe('CloudSyncDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    currentRuntimeMode.mode = 'server'
    getStatsMock.mockResolvedValue(MOCK_STATS)
    listRunsMock.mockResolvedValue(MOCK_RUNS)
    getLocalStatusMock.mockResolvedValue({
      local_mode: true,
      stats: { pending: 1, synced: 0, failed: 0, total: 1 },
      recent_items: [],
    })
  })

  it('mounts and loads stats and runs table in server mode', async () => {
    const wrapper = mount(CloudSyncDashboard, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot /><slot name="title" /></div>' },
          'a-table': {
            props: ['dataSource', 'columns'],
            template: '<div class="ant-table"><slot name="bodyCell" v-for="item in dataSource" :record="item" :column="{ key: \'title\' }" /></div>',
          },
          'a-modal': { template: '<div class="ant-modal"><slot /></div>' },
          'a-select': true,
          'a-select-option': true,
          'a-space': { template: '<div class="ant-space"><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-statistic': {
            props: ['title', 'value'],
            template: '<div class="ant-statistic">{{ title }}: {{ value }}</div>',
          },
        },
      },
    })

    await flushPromises()

    expect(getStatsMock).toHaveBeenCalledOnce()
    expect(listRunsMock).toHaveBeenCalledOnce()

    expect(wrapper.text()).toContain('跨端结果汇总中心')
    expect(wrapper.text()).toContain('DESKTOP-TEST')
    expect(wrapper.text()).toContain('Login Smoke Test')
  })

  it('triggers manual sync in local mode', async () => {
    currentRuntimeMode.mode = 'local'
    syncNowMock.mockResolvedValue({ status: 'ok', synced: 1, failed: 0, processed: 1 })

    const wrapper = mount(CloudSyncDashboard, {
      global: {
        stubs: {
          'a-card': true,
          'a-table': true,
          'a-modal': true,
          'a-select': true,
          'a-select-option': true,
          'a-space': { template: '<div class="ant-space"><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-statistic': true,
        },
      },
    })
    await flushPromises()

    const syncBtn = wrapper.findAll('button').find((b) => b.text().includes('立即同步'))
    expect(syncBtn).toBeDefined()
    await syncBtn!.trigger('click')
    await flushPromises()

    expect(syncNowMock).toHaveBeenCalledOnce()
  })
})
