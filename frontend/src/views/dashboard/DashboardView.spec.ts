import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import DashboardView from './DashboardView.vue'

const {
  caseList,
  dashboardAlertEvents,
  projectList,
  routerPush,
  runList,
  statisticsOverview,
  statisticsPassRateTrend,
  storageAlert,
  userSettingGet,
  userSettingUpdate,
} = vi.hoisted(() => ({
  caseList: vi.fn(),
  dashboardAlertEvents: vi.fn(),
  projectList: vi.fn(),
  routerPush: vi.fn(),
  runList: vi.fn(),
  statisticsOverview: vi.fn(),
  statisticsPassRateTrend: vi.fn(),
  storageAlert: vi.fn(),
  userSettingGet: vi.fn(),
  userSettingUpdate: vi.fn(),
}))

vi.mock('vue-router', () => ({ useRouter: () => ({ push: routerPush }) }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ locale: ref('zh-CN'), t: (key: string) => key }) }))
vi.mock('vue-echarts', () => ({ default: defineComponent({ name: 'VChart', setup: () => () => h('div', { 'data-test': 'chart' }) }) }))
vi.mock('vuedraggable', () => ({ default: defineComponent({ name: 'Draggable', setup: (_p, { slots }) => () => h('div', slots.default?.({ element: { key: 'pass_rate_trend', visible: true }, index: 0 })) }) }))
vi.mock('@/components/dashboard/LazyChartCard.vue', () => ({
  default: defineComponent({ name: 'LazyChartCard', emits: ['visible'], setup: (_p, { slots, emit }) => () => h('section', { 'data-test': 'lazy-card', onClick: () => emit('visible') }, slots.default?.()) }),
}))
vi.mock('@/utils/chartTheme', () => ({ useChartTheme: () => ({ chartTheme: 'light' }) }))
vi.mock('@/api', () => ({
  caseApi: { list: caseList },
  dashboardAlertApi: { listEvents: dashboardAlertEvents },
  projectApi: { list: projectList },
  runApi: { list: runList },
  statisticsApi: {
    overview: statisticsOverview,
    passRateTrend: statisticsPassRateTrend,
    durationTrend: vi.fn().mockResolvedValue([]),
    failureTop: vi.fn().mockResolvedValue([]),
    executorTop: vi.fn().mockResolvedValue([]),
    triggerTypeStats: vi.fn().mockResolvedValue([]),
    planTrend: vi.fn().mockResolvedValue([]),
    suiteTrend: vi.fn().mockResolvedValue([]),
    caseTypeDistribution: vi.fn().mockResolvedValue([]),
    exportCsv: vi.fn(),
  },
  storageApi: { getAlert: storageAlert },
  userSettingsApi: { get: userSettingGet, update: userSettingUpdate },
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_p, { slots }) => () => h('div', slots.default?.()) })

function mountDashboard() {
  return mount(DashboardView, {
    global: {
      stubs: {
        AAlert: passthrough('AAlert'),
        AButton: defineComponent({ name: 'AButton', emits: ['click'], setup: (_p, { slots, emit }) => () => h('button', { onClick: () => emit('click') }, slots.default?.()) }),
        ACard: passthrough('ACard'),
        ACheckbox: passthrough('ACheckbox'),
        ACol: passthrough('ACol'),
        ADropdown: passthrough('ADropdown'),
        AEmpty: passthrough('AEmpty'),
        AMenu: passthrough('AMenu'),
        AMenuItem: passthrough('AMenuItem'),
        AModal: passthrough('AModal'),
        ARow: passthrough('ARow'),
        ASegmented: passthrough('ASegmented'),
        ASelect: passthrough('ASelect'),
        ASkeleton: passthrough('ASkeleton'),
        ASpace: passthrough('ASpace'),
        ASpin: passthrough('ASpin'),
        ATag: passthrough('ATag'),
        AlertOutlined: true,
        CheckCircleOutlined: true,
        ClockCircleOutlined: true,
        DownloadOutlined: true,
        ExclamationCircleOutlined: true,
        FileSearchOutlined: true,
        PlayCircleOutlined: true,
        ProfileOutlined: true,
        SettingOutlined: true,
        ThunderboltOutlined: true,
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  projectList.mockResolvedValue([{ id: 10, name: 'Core' }])
  statisticsOverview.mockResolvedValue({ total_cases: 4, total_runs: 8, pass_rate: 75, recent_runs_7d: 3 })
  statisticsPassRateTrend.mockResolvedValue([{ date: '2026-07-11', total: 5, passed: 4, rate: 80 }])
  storageAlert.mockResolvedValue({ alert: null })
  dashboardAlertEvents.mockResolvedValue([])
  caseList.mockResolvedValue([{ id: 1 }])
  runList.mockResolvedValue({ items: [{ id: 99, case_id: 1, status: 'failed', created_at: '2026-07-11T01:00:00Z', duration_ms: 123 }] })
  userSettingGet.mockResolvedValue(null)
  userSettingUpdate.mockResolvedValue({})
})

describe('DashboardView mount', () => {
  it('loads first-screen metrics and workbench data', async () => {
    const wrapper = mountDashboard()
    await flushPromises()

    expect(projectList).toHaveBeenCalledOnce()
    expect(statisticsOverview).toHaveBeenCalledWith({ project_id: undefined, days: 30 })
    expect(statisticsPassRateTrend).toHaveBeenCalled()
    expect(runList).toHaveBeenCalledWith({ page: 1, page_size: 5 })
    expect(wrapper.text()).toContain('8')
    expect(wrapper.text()).toContain('75.0')
  })

  it('navigates to runs from the workbench card', async () => {
    const wrapper = mountDashboard()
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text().includes('dashboard.workbench.open_runs'))!.trigger('click')

    expect(routerPush).toHaveBeenCalledWith({ name: 'runs' })
  })

  it('exposes iOS in the case type filter when iOS cases are supported', async () => {
    const wrapper = mountDashboard()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.caseTypeOptions).toEqual(expect.arrayContaining([
      expect.objectContaining({ value: 'ios', label: 'dashboard.case_types.ios' }),
    ]))
  })
})
