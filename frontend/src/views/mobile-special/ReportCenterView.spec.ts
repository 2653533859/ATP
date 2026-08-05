import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, nextTick, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ReportCenterView from './ReportCenterView.vue'

const {
  projectList,
  overview,
  runList,
  trend,
  exportCsv,
  exportJson,
  stopRun,
  chartInit,
  routerPush,
  messageError,
  messageSuccess,
} = vi.hoisted(() => ({
  projectList: vi.fn(),
  overview: vi.fn(),
  runList: vi.fn(),
  trend: vi.fn(),
  exportCsv: vi.fn(),
  exportJson: vi.fn(),
  stopRun: vi.fn(),
  chartInit: vi.fn(),
  routerPush: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
}))

const chartTheme = ref('atp-light')
const chartInstances: Array<{ setOption: ReturnType<typeof vi.fn>; resize: ReturnType<typeof vi.fn>; dispose: ReturnType<typeof vi.fn> }> = []

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key, locale: ref('zh-CN') }),
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: routerPush }) }))
vi.mock('ant-design-vue', () => ({
  message: { error: messageError, success: messageSuccess },
}))
vi.mock('echarts/core', () => ({ init: chartInit }))
vi.mock('@/utils/chartTheme', () => ({ useChartTheme: () => ({ chartTheme }) }))
vi.mock('@/api', () => ({
  projectApi: { list: projectList },
  mobileSpecialApi: {
    getOverview: overview,
    listRuns: runList,
    getTrend: trend,
    exportRunCsv: exportCsv,
    exportRunJson: exportJson,
    stopRun,
  },
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

const buttonStub = defineComponent({
  name: 'AButton',
  props: { disabled: Boolean },
  emits: ['click'],
  setup: (props, { slots, emit }) => () => h('button', { disabled: props.disabled, onClick: () => emit('click') }, slots.default?.()),
})

const tableStub = defineComponent({
  name: 'ATable',
  props: ['dataSource'],
  setup: (props, { slots }) => () => h(
    'div',
    { 'data-test': 'report-table' },
    (props.dataSource || []).map((record: Record<string, unknown>) => h(
      'div',
      { class: 'report-row', key: String(record.id) },
      slots.bodyCell?.({ column: { key: 'action' }, record }),
    )),
  ),
})

const mountedWrappers: Array<{ unmount: () => void }> = []

function mountPage() {
  const wrapper = mount(ReportCenterView, {
    global: {
      stubs: {
        AButton: buttonStub,
        ACard: passthrough('ACard'),
        ADropdown: passthrough('ADropdown'),
        AMenu: passthrough('AMenu'),
        AMenuItem: passthrough('AMenuItem'),
        ARangePicker: passthrough('ARangePicker'),
        ASelect: passthrough('ASelect'),
        ASpin: passthrough('ASpin'),
        ATable: tableStub,
        ATag: passthrough('ATag'),
      },
    },
  })
  mountedWrappers.push(wrapper)
  return wrapper
}

afterEach(() => {
  mountedWrappers.splice(0).forEach((wrapper) => wrapper.unmount())
})

const PROJECTS = [{ id: 4, name: 'Mobile' }]
const RUNS = [
  { id: 20, task_id: 3, task_name: 'Perf', task_type: 'performance', status: 'completed', device_serial: 'emulator', app_package: 'com.acme', duration_ms: 1500, started_at: '2026-08-01T10:00:00Z' },
  { id: 21, task_id: 4, task_name: null, task_type: 'stability', status: 'running', device_serial: 'emulator', app_package: 'com.acme', duration_ms: null, started_at: null },
]
const OVERVIEW = { total_runs: 2, completed_runs: 1, failed_runs: 0, running_runs: 1, pass_rate: 50, avg_duration_ms: 1500, total_incidents: 0, recent_runs_7d: 2 }
const TREND = [{ date: '2026-08-01', total: 2, completed: 1, failed: 0, pass_rate: 50 }]

beforeEach(() => {
  vi.clearAllMocks()
  chartTheme.value = 'atp-light'
  chartInstances.length = 0
  projectList.mockResolvedValue(PROJECTS)
  overview.mockResolvedValue(OVERVIEW)
  runList.mockResolvedValue(RUNS)
  trend.mockResolvedValue(TREND)
  exportCsv.mockResolvedValue(new Blob(['csv']))
  exportJson.mockResolvedValue(new Blob(['{}']))
  stopRun.mockResolvedValue({})
  chartInit.mockImplementation(() => {
    const chart = { setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() }
    chartInstances.push(chart)
    return chart
  })
})

describe('ReportCenterView mount', () => {
  it('loads the default project, overview, runs, trend, and initializes the chart', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(projectList).toHaveBeenCalledOnce()
    expect(overview).toHaveBeenCalledWith({ project_id: 4, days: 30 })
    expect(runList).toHaveBeenCalledWith({ project_id: 4, limit: 100 })
    expect(trend).toHaveBeenCalledWith({ project_id: 4, days: 14 })
    expect(chartInit).toHaveBeenCalledOnce()
    expect((wrapper.vm as any).overview.total_runs).toBe(2)
  })

  it('builds filtered run queries and preserves a fallback task name', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedTaskType = 'stability'
    vm.selectedStatus = 'running'
    await vm.loadRuns()

    expect(runList).toHaveBeenLastCalledWith({ project_id: 4, task_type: 'stability', status_filter: 'running', limit: 100 })
    expect(vm.runs[1].task_name).toContain('mobile_special.reports.task_fallback')
  })

  it('navigates, exports both formats, and stops a running run', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    const createObjectURL = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:report')
    const revokeObjectURL = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)

    await wrapper.findAll('button').find((button) => button.text() === 'case.actions.detail')!.trigger('click')
    expect(routerPush).toHaveBeenCalledWith('/mobile-special/reports/20')
    await vm.exportCsv(RUNS[0])
    await vm.exportJson(RUNS[0])
    expect(exportCsv).toHaveBeenCalledWith(20)
    expect(exportJson).toHaveBeenCalledWith(20)
    expect(messageSuccess).toHaveBeenCalled()

    await wrapper.findAll('button').find((button) => button.text() === 'mobile_special.reports.stop')!.trigger('click')
    expect(stopRun).toHaveBeenCalledWith(21)
    expect(messageSuccess).toHaveBeenCalledWith('mobile_special.reports.msg.stopped')

    createObjectURL.mockRestore()
    revokeObjectURL.mockRestore()
    anchorClick.mockRestore()
  })

  it('reports run loading and export failures', async () => {
    runList.mockRejectedValueOnce(new Error('reports unavailable'))
    const wrapper = mountPage()
    await flushPromises()
    expect(messageError).toHaveBeenCalledWith('reports unavailable')

    const vm = wrapper.vm as any
    exportCsv.mockRejectedValueOnce(new Error('download failed'))
    await vm.exportCsv(RUNS[0])
    expect(messageError).toHaveBeenCalledWith('download failed')
  })

  it('recreates the chart when the theme changes and disposes it on unmount', async () => {
    const addEventListener = vi.spyOn(window, 'addEventListener')
    const removeEventListener = vi.spyOn(window, 'removeEventListener')
    const wrapper = mountPage()
    await flushPromises()

    expect(chartInstances).toHaveLength(1)
    chartTheme.value = 'atp-dark'
    await nextTick()

    expect(chartInstances[0].dispose).toHaveBeenCalledOnce()
    expect(chartInstances).toHaveLength(2)
    expect(chartInit).toHaveBeenNthCalledWith(2, expect.any(HTMLElement), 'atp-dark')

    wrapper.unmount()

    expect(chartInstances[1].dispose).toHaveBeenCalledOnce()
    const resizeRegistration = addEventListener.mock.calls.find(([eventName]) => eventName === 'resize')
    expect(resizeRegistration).toBeDefined()
    expect(removeEventListener).toHaveBeenCalledWith('resize', resizeRegistration?.[1])
    addEventListener.mockRestore()
    removeEventListener.mockRestore()
  })
})
