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
  toolboxOverview,
  userRole,
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
  toolboxOverview: vi.fn(),
  userRole: { value: 'admin' as string },
  userSettingGet: vi.fn(),
  userSettingUpdate: vi.fn(),
}))

vi.mock('vue-router', () => ({ useRouter: () => ({ push: routerPush }) }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ locale: ref('zh-CN'), t: (key: string) => key }) }))
// 该视图只读取当前用户角色来决定是否展示服务状态卡，按本文件既有风格直接替掉 store，
// 而不是为一个字段引入 Pinia。
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: { role: userRole.value } }) }))
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
  remoteToolboxApi: { overview: toolboxOverview },
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
  userRole.value = 'admin'
  projectList.mockResolvedValue([{ id: 10, name: 'Core' }])
  statisticsOverview.mockResolvedValue({ total_cases: 4, total_runs: 8, pass_rate: 75, recent_runs_7d: 3 })
  statisticsPassRateTrend.mockResolvedValue([{ date: '2026-07-11', total: 5, passed: 4, rate: 80 }])
  storageAlert.mockResolvedValue({ alert: null })
  dashboardAlertEvents.mockResolvedValue([])
  caseList.mockResolvedValue([{ id: 1 }])
  runList.mockResolvedValue({ items: [{ id: 99, case_id: 1, status: 'failed', created_at: '2026-07-11T01:00:00Z', duration_ms: 123 }] })
  userSettingGet.mockResolvedValue(null)
  userSettingUpdate.mockResolvedValue({})
  toolboxOverview.mockResolvedValue({
    status: 'ok',
    checked_at: '2026-07-11T01:00:00Z',
    checks: [
      { key: 'postgres', category: 'infrastructure', status: 'ok', code: 'ok', latency_ms: 1, resources: [] },
      { key: 'redis', category: 'infrastructure', status: 'ok', code: 'ok', latency_ms: 1, resources: [] },
    ],
  })
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

describe('DashboardView workbench verdict', () => {
  it('reports a healthy platform when nothing needs attention', async () => {
    const wrapper = mountDashboard()
    await flushPromises()

    expect((wrapper.vm as any).workbenchVerdict).toEqual({ tone: 'ok', text: 'dashboard.workbench.verdict_ok' })
  })

  it("leads with today's failures instead of the healthy verdict", async () => {
    const today = new Date().toISOString().slice(0, 10)
    statisticsPassRateTrend.mockResolvedValue([{ date: today, total: 5, passed: 3, rate: 60 }])

    const wrapper = mountDashboard()
    await flushPromises()

    expect((wrapper.vm as any).workbenchVerdict).toEqual({
      tone: 'error',
      text: 'dashboard.workbench.verdict_failed',
    })
  })

  it('does not claim the platform is healthy when workbench data fails to load', async () => {
    // resetWorkbench() 会把计数归零；若结论只看计数，加载失败会被读成「没有失败任务」。
    runList.mockRejectedValue(new Error('boom'))

    const wrapper = mountDashboard()
    await flushPromises()

    expect((wrapper.vm as any).workbenchVerdict).toEqual({
      tone: 'warning',
      text: 'dashboard.workbench.verdict_unavailable',
    })
  })
})

describe('DashboardView service status', () => {
  it('sorts unhealthy services first and keeps every check visible', async () => {
    toolboxOverview.mockResolvedValue({
      status: 'degraded',
      checked_at: '2026-07-11T01:00:00Z',
      checks: [
        { key: 'postgres', category: 'infrastructure', status: 'ok', code: 'ok', latency_ms: 1, resources: [] },
        { key: 'adb', category: 'execution', status: 'error', code: 'unreachable', latency_ms: 2, resources: [] },
        { key: 'redis', category: 'infrastructure', status: 'warning', code: 'timeout', latency_ms: 3, resources: [] },
      ],
    })

    const wrapper = mountDashboard()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.serviceChecks.map((check: { key: string }) => check.key)).toEqual(['adb', 'redis', 'postgres'])
    expect(vm.degradedServiceCount).toBe(2)
    expect(wrapper.text()).toContain('dashboard.workbench.services_title')
  })

  it('degrades the verdict when services are not ready but nothing has failed', async () => {
    toolboxOverview.mockResolvedValue({
      status: 'degraded',
      checked_at: '2026-07-11T01:00:00Z',
      checks: [
        { key: 'adb', category: 'execution', status: 'warning', code: 'adb_capability_missing', latency_ms: 1, resources: [] },
      ],
    })

    const wrapper = mountDashboard()
    await flushPromises()

    expect((wrapper.vm as any).workbenchVerdict).toEqual({
      tone: 'warning',
      text: 'dashboard.workbench.verdict_services',
    })
  })

  it('keeps the card empty instead of raising when the toolbox endpoint fails', async () => {
    toolboxOverview.mockRejectedValue(new Error('403'))

    const wrapper = mountDashboard()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.serviceChecks).toEqual([])
    expect(vm.serviceOverviewStatus).toBeNull()
    expect(wrapper.text()).toContain('dashboard.workbench.services_unavailable')
  })

  it('hides the card from roles without remote toolbox access', async () => {
    // /remote-toolbox/overview 是 require_engineer，tester 会拿到 403，不该发这个请求。
    userRole.value = 'tester'

    const wrapper = mountDashboard()
    await flushPromises()

    expect(toolboxOverview).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('dashboard.workbench.services_title')
  })
})
