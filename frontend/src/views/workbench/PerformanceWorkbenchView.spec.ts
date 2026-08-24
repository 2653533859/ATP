import { defineComponent, h, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import PerformanceWorkbenchView from './PerformanceWorkbenchView.vue'

const {
  baselineComparison,
  environmentList,
  executorList,
  gate,
  metricList,
  nodeList,
  projectList,
  routerReplace,
  runList,
  testCreate,
  testList,
  triggerRun,
} = vi.hoisted(() => ({
  baselineComparison: vi.fn(),
  environmentList: vi.fn(),
  executorList: vi.fn(),
  gate: vi.fn(),
  metricList: vi.fn(),
  nodeList: vi.fn(),
  projectList: vi.fn(),
  routerReplace: vi.fn(),
  runList: vi.fn(),
  testCreate: vi.fn(),
  testList: vi.fn(),
  triggerRun: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: { project_id: '1' } }),
  useRouter: () => ({ push: vi.fn(), replace: routerReplace }),
}))
vi.mock('vue-i18n', () => ({
  useI18n: () => ({ locale: ref('zh-CN'), t: (key: string) => key }),
}))
vi.mock('ant-design-vue', () => ({
  message: { error: vi.fn(), success: vi.fn(), warning: vi.fn() },
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: { role: 'admin' } }),
}))
vi.mock('@/utils/chartTheme', () => ({
  useChartTheme: () => ({ chartTheme: 'atp-light' }),
}))
vi.mock('vue-echarts', () => ({
  default: defineComponent({ setup: (_props, { slots }) => () => h('div', slots.default?.()) }),
}))
vi.mock('@ant-design/icons-vue', () => ({
  LineChartOutlined: true,
  PlayCircleOutlined: true,
  PlusOutlined: true,
  ReloadOutlined: true,
  SafetyCertificateOutlined: true,
  SettingOutlined: true,
  StopOutlined: true,
}))
vi.mock('@/api', () => ({
  datasetApi: { list: vi.fn() },
  environmentApi: { list: environmentList },
  performanceApi: {
    listTests: testList,
    listRuns: runList,
    listNodes: nodeList,
    listExecutors: executorList,
    getGate: gate,
    getBaselineComparison: baselineComparison,
    getMetrics: metricList,
    triggerRun,
    createTest: testCreate,
  },
  projectApi: { list: projectList },
}))

const passthrough = defineComponent({
  setup: (_props, { slots }) => () => h('div', slots.default?.()),
})

const globalStubs = Object.fromEntries([
  'AAlert', 'AButton', 'ADrawer', 'AEmpty', 'AForm', 'AFormItem', 'AInput', 'ASelect',
  'ASpace', 'ATag', 'ATextarea',
].map((name) => [name, passthrough]))

const testItem = {
  id: 101,
  project_id: 1,
  name: '首页稳定性',
  description: '核心首页负载',
  executor: 'k6',
  script_object_name: 'performance/homepage.js',
  default_options: { vus: 10, duration: '30s' },
  baseline_run_id: 200,
  schedule_enabled: false,
  schedule_timezone: 'Asia/Shanghai',
  schedule_options: {},
  created_at: '2026-08-24T08:00:00Z',
  updated_at: '2026-08-24T09:00:00Z',
}

const runItem = {
  id: 200,
  performance_test_id: 101,
  project_id: 1,
  environment_id: 8,
  performance_node_id: 3,
  status: 'success',
  progress_percent: 100,
  options_snapshot: {},
  summary: { rps: 42.5, p95_ms: 180, p99_ms: 260, error_rate: 0.01 },
  duration_ms: 30000,
  created_at: '2026-08-24T10:00:00Z',
  updated_at: '2026-08-24T10:01:00Z',
}

function mountWorkbench() {
  return mount(PerformanceWorkbenchView, { global: { stubs: globalStubs } })
}

beforeEach(() => {
  vi.clearAllMocks()
  projectList.mockResolvedValue([{ id: 1, name: '核心项目', owner_id: 1, current_user_role: 'owner' }])
  testList.mockResolvedValue([testItem])
  runList.mockResolvedValue([runItem])
  environmentList.mockResolvedValue([{ id: 8, name: '测试环境', project_id: 1 }])
  nodeList.mockResolvedValue([{
    id: 3,
    node_id: 'perf-win-01',
    name: 'Windows 压测节点',
    queue_name: 'performance',
    status: 'online',
    enabled: true,
    capabilities: { executors: ['k6'] },
    max_vus: 100,
    max_concurrency: 2,
    egress_allowlist: [],
    created_at: '',
    updated_at: '',
  }])
  executorList.mockResolvedValue([{ name: 'k6', label: 'k6', ready: true, description: 'k6', script_extensions: ['.js'] }])
  gate.mockResolvedValue({ status: 'passed', passed: 2, total: 2 })
  baselineComparison.mockResolvedValue({ baseline_run_id: 199, run_id: 200, metrics: [{ metric: 'p95_ms', preferred_direction: 'lower', baseline: 170, current: 180, delta: 10, delta_percent: 5.88, direction: 'regression' }] })
  metricList.mockResolvedValue([{ id: 1, run_id: 200, captured_at: '2026-08-24T10:00:00Z', node_id: 'perf-win-01', source: 'performance-worker', metrics: { cpu_percent: 55 }, errors: [] }])
  triggerRun.mockResolvedValue({ ...runItem, id: 201, status: 'pending', progress_percent: 0 })
  testCreate.mockResolvedValue({ ...testItem, id: 102 })
  routerReplace.mockResolvedValue(undefined)
})

describe('PerformanceWorkbenchView', () => {
  it('loads project-scoped scenarios, nodes, runs, and run evidence', async () => {
    const wrapper = mountWorkbench()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(testList).toHaveBeenCalledWith(1)
    expect(runList).toHaveBeenCalledWith(1)
    expect(nodeList).toHaveBeenCalled()
    expect(vm.tests).toHaveLength(1)
    expect(vm.selectedTestId).toBe(101)
    expect(vm.selectedRunId).toBe(200)
    expect(gate).toHaveBeenCalledWith(200)
    expect(metricList).toHaveBeenCalledWith(200)
    expect(vm.metricSamples).toHaveLength(1)
    wrapper.unmount()
  })

  it('launches the selected scenario with environment, nodes, options, and idempotency', async () => {
    const wrapper = mountWorkbench()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.launchEnvironmentId = 8
    vm.launchNodeIds = [3]
    vm.launchOptionsText = '{"vus": 20}'

    await vm.launchRun()

    expect(triggerRun).toHaveBeenCalledWith(101, expect.objectContaining({
      environment_id: 8,
      performance_node_ids: [3],
      idempotency_key: expect.any(String),
      options: { vus: 20 },
    }))
    expect(vm.selectedRunId).toBe(201)
    wrapper.unmount()
  })

  it('clears project-scoped state when the project selection is cleared', async () => {
    const wrapper = mountWorkbench()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.handleProjectChange(null)

    expect(vm.selectedProjectId).toBeNull()
    expect(vm.tests).toHaveLength(0)
    expect(vm.runs).toHaveLength(0)
    expect(vm.nodes).toHaveLength(0)
    expect(vm.selectedRunId).toBeNull()
    wrapper.unmount()
  })

  it('keeps scenarios visible when support APIs fail but blocks launch without executor readiness', async () => {
    nodeList.mockRejectedValueOnce(new Error('node endpoint unavailable'))
    executorList.mockRejectedValueOnce(new Error('executor endpoint unavailable'))

    const wrapper = mountWorkbench()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(vm.tests).toHaveLength(1)
    expect(vm.runs).toHaveLength(1)
    expect(vm.loadError).toBe('performance_workbench.load_warning')
    expect(vm.canLaunch).toBe(false)
    wrapper.unmount()
  })
})
