import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, nextTick, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ReportCenterView from './ReportCenterView.vue'

const { projectList, reportOverview, reportCompare, exportCsv, routerReplace, routerPush, messageError, messageSuccess, routeQuery } = vi.hoisted(() => ({
  projectList: vi.fn(),
  reportOverview: vi.fn(),
  reportCompare: vi.fn(),
  exportCsv: vi.fn(),
  routerReplace: vi.fn(),
  routerPush: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  routeQuery: { value: {} as Record<string, unknown> },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string, params?: Record<string, unknown>) => params ? `${key}:${JSON.stringify(params)}` : key }),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: routeQuery.value }),
  useRouter: () => ({ replace: routerReplace, push: routerPush }),
}))
vi.mock('ant-design-vue', () => ({
  message: { error: messageError, success: messageSuccess },
}))
vi.mock('@/utils/chartTheme', () => ({ useChartTheme: () => ({ chartTheme: ref('atp-light') }) }))
vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', render: () => null },
}))
vi.mock('@/api', () => ({
  projectApi: { list: projectList },
  reportApi: { overview: reportOverview, compare: reportCompare },
  statisticsApi: { exportCsv },
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

const buttonStub = defineComponent({
  name: 'AButton',
  props: { disabled: Boolean },
  emits: ['click'],
  setup: (props, { slots, emit }) => () => h(
    'button',
    { disabled: props.disabled, onClick: () => emit('click') },
    slots.default?.(),
  ),
})

const OVERVIEW = {
  project_id: 1,
  days: 30,
  total_cases: 10,
  executed_cases: 7,
  coverage_rate: 70,
  total_runs: 8,
  passed_runs: 6,
  failed_runs: 1,
  error_runs: 1,
  pass_rate: 75,
  avg_duration_ms: 1250,
  open_defects: 1,
  defect_health_rate: 90,
  quality_score: 76,
  trend: [{ date: '2026-08-24', total: 8, passed: 6, failed: 1, error: 1, pass_rate: 75, avg_duration_ms: 1250 }],
  case_type_stats: [{ case_type: 'api', total_runs: 8, passed_runs: 6, failed_runs: 1, error_runs: 1, pass_rate: 75 }],
  recent_runs: [
    { id: 44, project_id: 1, case_id: 9, case_name: '登录用例', case_type: 'api', status: 'passed', duration_ms: 1200, created_at: '2026-08-24T12:00:00Z' },
    { id: 43, project_id: 1, case_id: 9, case_name: '登录用例', case_type: 'api', status: 'failed', duration_ms: 1600, created_at: '2026-08-23T12:00:00Z' },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  routeQuery.value = {}
  projectList.mockResolvedValue([{ id: 1, name: '核心项目' }])
  reportOverview.mockResolvedValue(OVERVIEW)
  reportCompare.mockResolvedValue({
    project_id: 1,
    baseline: { ...OVERVIEW.recent_runs[1], total_steps: 4, passed_steps: 4, failed_steps: 0, error_steps: 0 },
    current: { ...OVERVIEW.recent_runs[0], total_steps: 4, passed_steps: 3, failed_steps: 1, error_steps: 0 },
    metrics: [{ key: 'failed_steps', label: '失败步骤', baseline: 0, current: 1, delta: 1, unit: '步' }],
    has_regression: true,
  })
  exportCsv.mockResolvedValue(new Blob(['csv']))
})

describe('ReportCenterView', () => {
  it('restores project and period from the report deep link', async () => {
    routeQuery.value = { project_id: '3', days: '90' }
    const wrapper = mount(ReportCenterView, {
      global: {
        stubs: {
          AAlert: passthrough('AAlert'),
          AButton: buttonStub,
          ACard: passthrough('ACard'),
          AEmpty: passthrough('AEmpty'),
          ASelect: passthrough('ASelect'),
          ASpin: passthrough('ASpin'),
          ATable: passthrough('ATable'),
          ATag: passthrough('ATag'),
          VChart: passthrough('VChart'),
        },
      },
    })
    await flushPromises()

    expect(reportOverview).toHaveBeenCalledWith({ project_id: 3, days: 90, recent_limit: 20 })
    expect((wrapper.vm as any).projectId).toBe(3)
    expect((wrapper.vm as any).days).toBe(90)
    wrapper.unmount()
  })

  it('loads the project-scoped report and prepares two recent runs for comparison', async () => {
    const wrapper = mount(ReportCenterView, {
      global: {
        stubs: {
          AAlert: passthrough('AAlert'),
          AButton: buttonStub,
          ACard: passthrough('ACard'),
          AEmpty: passthrough('AEmpty'),
          ASelect: passthrough('ASelect'),
          ASpin: passthrough('ASpin'),
          ATable: passthrough('ATable'),
          ATag: passthrough('ATag'),
          VChart: passthrough('VChart'),
        },
      },
    })
    await flushPromises()

    expect(projectList).toHaveBeenCalledOnce()
    expect(reportOverview).toHaveBeenCalledWith({ project_id: undefined, days: 30, recent_limit: 20 })
    expect((wrapper.vm as any).overview.quality_score).toBe(76)
    expect((wrapper.vm as any).baselineRunId).toBe(43)
    expect((wrapper.vm as any).currentRunId).toBe(44)
    expect(wrapper.text()).toContain('report_center.title')
    expect(wrapper.text()).toContain('report_center.protocol.title')
    const vm = wrapper.vm as any
    vm.days = 7
    await nextTick()
    expect(routerReplace).toHaveBeenCalledWith({ query: { days: '7' } })
    wrapper.unmount()
  })

  it('compares selected runs and reports export failures', async () => {
    const wrapper = mount(ReportCenterView, {
      global: {
        stubs: {
          AAlert: passthrough('AAlert'),
          AButton: buttonStub,
          ACard: passthrough('ACard'),
          AEmpty: passthrough('AEmpty'),
          ASelect: passthrough('ASelect'),
          ASpin: passthrough('ASpin'),
          ATable: passthrough('ATable'),
          ATag: passthrough('ATag'),
          VChart: passthrough('VChart'),
        },
      },
    })
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.compareRuns()
    expect(reportCompare).toHaveBeenCalledWith({ baseline_run_id: 43, current_run_id: 44 })
    expect(vm.comparison.has_regression).toBe(true)

    const createObjectURL = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:report')
    const revokeObjectURL = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    exportCsv.mockRejectedValueOnce(new Error('export unavailable'))
    await vm.exportTrend()
    expect(messageError).toHaveBeenCalledWith('report_center.export_failed')
    createObjectURL.mockRestore()
    revokeObjectURL.mockRestore()
    wrapper.unmount()
  })
})
