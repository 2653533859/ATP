import { defineComponent, h } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import PerformanceCenterView from './PerformanceCenterView.vue'

const {
  projectList,
  environmentList,
  datasetList,
  executorList,
  testList,
  runList,
  trend,
  triggerRun,
  testCreate,
  nodeList,
  nodeCreate,
  nodeUpdate,
  nodeDelete,
  defectList,
  defectCreate,
  getMetrics,
  routerPush,
  messageError,
  messageSuccess,
  messageWarning,
} = vi.hoisted(() => ({
  projectList: vi.fn(),
  environmentList: vi.fn(),
  datasetList: vi.fn(),
  executorList: vi.fn(),
  testList: vi.fn(),
  runList: vi.fn(),
  trend: vi.fn(),
  triggerRun: vi.fn(),
  testCreate: vi.fn(),
  nodeList: vi.fn(),
  nodeCreate: vi.fn(),
  nodeUpdate: vi.fn(),
  nodeDelete: vi.fn(),
  defectList: vi.fn(),
  defectCreate: vi.fn(),
  getMetrics: vi.fn(),
  routerPush: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  messageWarning: vi.fn(),
}))

vi.mock('@/api', () => ({
  projectApi: { list: projectList },
  environmentApi: { list: environmentList },
  datasetApi: { list: datasetList },
  performanceApi: {
    listExecutors: executorList,
    listNodes: nodeList,
    listTests: testList,
    listRuns: runList,
    getTrend: trend,
    triggerRun,
    createTest: testCreate,
    createNode: nodeCreate,
    updateNode: nodeUpdate,
    deleteNode: nodeDelete,
    getMetrics,
    getBaselineComparison: vi.fn(),
  },
  defectApi: {
    list: defectList,
    createFromRun: defectCreate,
  },
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: routerPush }),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

vi.mock('ant-design-vue', () => ({
  message: {
    error: messageError,
    success: messageSuccess,
    warning: messageWarning,
  },
}))

vi.mock('vue-echarts', () => ({
  default: defineComponent({
    setup: (_props, { slots }) => () => h('div', slots.default?.()),
  }),
}))

vi.mock('@/utils/chartTheme', () => ({
  useChartTheme: () => ({ chartTheme: 'atp-light' }),
}))

const passthrough = defineComponent({
  setup: (_props, { slots }) => () => h('div', slots.default?.()),
})

function mountPage() {
  return mount(PerformanceCenterView, {
    global: {
      stubs: Object.fromEntries([
        'ABadge', 'AAlert', 'AButton', 'ACard', 'ACol', 'ADrawer', 'AEmpty', 'AForm', 'AFormItem',
        'AInput', 'AInputNumber', 'AModal', 'APopconfirm', 'AProgress', 'ARadioButton', 'ARadioGroup',
        'ARow', 'ASelect', 'ASpace', 'ASpaceCompact', 'ASpin', 'AStatistic', 'ASwitch', 'ATable', 'ATag',
        'ATextarea', 'ATooltip', 'AUpload', 'ADescriptions', 'ADescriptionsItem', 'KvEditor',
      ].map((name) => [name, passthrough])),
    },
  })
}

describe('PerformanceCenterView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    projectList.mockResolvedValue([{ id: 1, name: 'Demo', owner_id: 1 }])
    environmentList.mockResolvedValue([])
    datasetList.mockResolvedValue([])
    executorList.mockResolvedValue([
      {
        name: 'k6', label: 'k6', ready: true, script_extensions: ['.js'],
        supports_visual: true, supports_dataset: true, supports_http: true, supports_grpc: false, description: 'k6',
      },
      {
        name: 'jmeter', label: 'JMeter', ready: true, script_extensions: ['.jmx'],
        supports_visual: false, supports_dataset: false, supports_http: true, supports_grpc: false, description: 'JMeter',
      },
    ])
    testList.mockResolvedValue([])
    runList.mockResolvedValue([])
    trend.mockResolvedValue({
      project_id: 1,
      days: 30,
      from_at: '2026-07-26T00:00:00Z',
      to_at: '2026-08-24T12:00:00Z',
      run_count: 0,
      success_count: 0,
      failed_count: 0,
      cancelled_count: 0,
      active_count: 0,
      other_count: 0,
      avg_rps: null,
      avg_p95_ms: null,
      avg_p99_ms: null,
      avg_error_rate: null,
      max_p95_ms: null,
      points: [],
    })
    triggerRun.mockResolvedValue({ id: 10 })
    testCreate.mockResolvedValue({ id: 2 })
    nodeList.mockResolvedValue([])
    nodeCreate.mockResolvedValue({ id: 1 })
    nodeUpdate.mockResolvedValue({ id: 1 })
    nodeDelete.mockResolvedValue(undefined)
    defectList.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
    defectCreate.mockResolvedValue({ created: true, duplicate_of: null, defect: { id: 11, title: 'Load failure' } })
    getMetrics.mockResolvedValue([])
  })

  it('accepts JMeter when switching the performance executor', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const vm = wrapper.vm as any
    vm.handleExecutorChange('jmeter')

    expect(vm.testForm.executor).toBe('jmeter')
    expect(vm.testForm.mode).toBe('script')
    expect(vm.selectedExecutor.name).toBe('jmeter')
    expect(vm.scriptAccept).toBe('.jmx')
    wrapper.unmount()
  })

  it('honors the project query when opened from a project-scoped workbench', async () => {
    projectList.mockResolvedValue([
      { id: 1, name: 'Demo', owner_id: 1 },
      { id: 2, name: 'Second', owner_id: 1 },
    ])
    window.history.replaceState({}, '', '/system/performance?project_id=2')

    const wrapper = mountPage()
    await flushPromises()

    expect(testList).toHaveBeenCalledWith(2)
    expect(runList).toHaveBeenCalledWith(2)
    window.history.replaceState({}, '', '/')
    wrapper.unmount()
  })

  it('loads a bounded server-side trend instead of deriving it from the run list', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(trend).toHaveBeenCalledWith(1, 30)
    const vm = wrapper.vm as any
    vm.trendDays = 7
    await vm.loadTrend()

    expect(trend).toHaveBeenLastCalledWith(1, 7)
    wrapper.unmount()
  })

  it('creates an internal defect from a failed performance run and exposes the run filter', async () => {
    const failedRun = {
      id: 10,
      performance_test_id: 2,
      project_id: 1,
      status: 'failed',
      summary: { rps: 1, p95_ms: 200, p99_ms: 300, error_rate: 0.5 },
      options_snapshot: {},
      progress_percent: 100,
      created_at: '2026-08-25T10:00:00Z',
      updated_at: '2026-08-25T10:01:00Z',
    }
    runList.mockResolvedValue([failedRun])
    const wrapper = mountPage()
    await flushPromises()

    const vm = wrapper.vm as any
    await vm.openRunDetail(failedRun)
    expect(defectList).toHaveBeenCalledWith({ run_type: 'performance', run_id: 10, page: 1, page_size: 20 })
    expect(vm.canCreateInternalDefect(failedRun)).toBe(true)

    await vm.createInternalDefect()
    expect(defectCreate).toHaveBeenCalledWith('performance', 10)
    expect(messageSuccess).toHaveBeenCalledWith('performance.msg.defect_created')
    vm.openInternalDefects()
    expect(routerPush).toHaveBeenCalledWith({
      name: 'bugs',
      query: { project_id: '1', run_type: 'performance', run_id: '10', view: 'linked' },
    })
    wrapper.unmount()
  })

  it('does not expose defect creation for a successful performance run', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.canCreateInternalDefect({ status: 'success' })).toBe(false)
    expect(vm.canCreateInternalDefect({ status: 'running' })).toBe(false)
    wrapper.unmount()
  })

  it('ignores a stale trend response after the project changes', async () => {
    let resolveFirst: ((value: unknown) => void) | undefined
    let resolveSecond: ((value: unknown) => void) | undefined
    const payload = (projectId: number) => ({
      project_id: projectId,
      days: 30,
      from_at: '',
      to_at: '',
      run_count: 0,
      success_count: 0,
      failed_count: 0,
      cancelled_count: 0,
      active_count: 0,
      other_count: 0,
      avg_rps: null,
      avg_p95_ms: null,
      avg_p99_ms: null,
      avg_error_rate: null,
      max_p95_ms: null,
      points: [],
    })
    trend.mockReset()
    trend
      .mockReturnValueOnce(new Promise((resolve) => { resolveFirst = resolve }))
      .mockReturnValueOnce(new Promise((resolve) => { resolveSecond = resolve }))

    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(trend).toHaveBeenCalledWith(1, 30)

    vm.projectId = 2
    const latestLoad = vm.loadTrend()
    resolveFirst?.(payload(1))
    await flushPromises()
    expect(vm.trend).toBeNull()

    resolveSecond?.(payload(2))
    await latestLoad
    expect(vm.trend.project_id).toBe(2)
    wrapper.unmount()
  })

  it('saves Prometheus target metrics together with the performance definition', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const vm = wrapper.vm as any
    vm.openCreate()
    vm.testForm.mode = 'script'
    vm.testForm.executor = 'locust'
    vm.testForm.name = 'Prometheus smoke'
    vm.testForm.script_object_name = 'performance/scripts/prometheus-smoke.py'
    vm.testForm.targetMetrics.enabled = true
    vm.testForm.targetMetrics.prometheus_url = 'http://127.0.0.1:9090'
    vm.testForm.targetMetrics.queries = [
      { name: 'backend_up', query: 'up{job="atp-backend"}' },
      { name: 'request_count', query: 'sum(http_requests_total)' },
    ]

    await vm.saveTest()

    expect(testCreate).toHaveBeenCalledWith(expect.objectContaining({
      project_id: 1,
      name: 'Prometheus smoke',
      default_options: expect.objectContaining({
        target_metrics: {
          prometheus_url: 'http://127.0.0.1:9090',
          timeout_seconds: 2,
          queries: {
            backend_up: 'up{job="atp-backend"}',
            request_count: 'sum(http_requests_total)',
          },
        },
      }),
    }))
    wrapper.unmount()
  })

  it('rejects an unsafe Prometheus URL before saving', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const vm = wrapper.vm as any
    vm.openCreate()
    vm.testForm.mode = 'script'
    vm.testForm.executor = 'locust'
    vm.testForm.name = 'Invalid Prometheus'
    vm.testForm.script_object_name = 'performance/scripts/invalid.py'
    vm.testForm.targetMetrics.enabled = true
    vm.testForm.targetMetrics.prometheus_url = 'file:///tmp/prometheus'
    vm.testForm.targetMetrics.queries = [{ name: 'up', query: 'up' }]

    await vm.saveTest()

    expect(testCreate).not.toHaveBeenCalled()
    expect(messageWarning).toHaveBeenCalledWith('performance.msg.prometheus_url_invalid')
    wrapper.unmount()
  })

  it('registers a node with executor capabilities, limits, and an egress allowlist', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const vm = wrapper.vm as any
    vm.openNodeCreate()
    vm.nodeForm.node_id = 'perf-win-01'
    vm.nodeForm.name = 'Windows load node'
    vm.nodeForm.queue_name = 'performance-win'
    vm.nodeForm.executors = ['k6', 'jmeter']
    vm.nodeForm.max_vus = 100
    vm.nodeForm.max_concurrency = 2
    vm.nodeForm.egress_allowlist = 'api.example.com\n api.example.com, metrics.example.com '

    await vm.saveNode()

    expect(nodeCreate).toHaveBeenCalledWith({
      node_id: 'perf-win-01',
      name: 'Windows load node',
      queue_name: 'performance-win',
      enabled: true,
      capabilities: { executors: ['k6', 'jmeter'] },
      max_vus: 100,
      max_concurrency: 2,
      egress_allowlist: ['api.example.com', 'metrics.example.com'],
    })
    expect(messageSuccess).toHaveBeenCalledWith('performance.msg.node_create_success')
    expect(vm.nodeEditorOpen).toBe(false)
    wrapper.unmount()
  })

  it('shows the node diagnostic when a worker queue does not match', async () => {
    nodeList.mockResolvedValue([{
      id: 1,
      node_id: 'perf-win-01',
      name: 'Windows load node',
      queue_name: 'performance.worker-a',
      status: 'offline',
      enabled: true,
      labels: { managed_by: 'worker_env' },
      capabilities: { executors: ['k6'] },
      max_vus: 100,
      max_concurrency: 2,
      egress_allowlist: [],
      last_heartbeat_at: '2026-08-12T08:00:00Z',
      last_error: 'Worker 队列与节点配置不一致',
      created_at: '2026-08-12T08:00:00Z',
      updated_at: '2026-08-12T08:00:00Z',
    }])

    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('.node-error').text()).toContain('Worker 队列与节点配置不一致')
    wrapper.unmount()
  })

  it('disables nodes that do not support the selected executor before submission', async () => {
    nodeList.mockResolvedValue([
      {
        id: 1,
        node_id: 'k6-node',
        name: 'k6 node',
        queue_name: 'performance.k6',
        status: 'online',
        enabled: true,
        labels: {},
        capabilities: { executors: ['k6'] },
        max_vus: null,
        max_concurrency: null,
        egress_allowlist: [],
        last_heartbeat_at: '2026-08-12T08:00:00Z',
        last_error: null,
        created_at: '2026-08-12T08:00:00Z',
        updated_at: '2026-08-12T08:00:00Z',
      },
      {
        id: 2,
        node_id: 'jmeter-node',
        name: 'JMeter node',
        queue_name: 'performance.jmeter',
        status: 'online',
        enabled: true,
        labels: {},
        capabilities: { executors: ['jmeter'] },
        max_vus: null,
        max_concurrency: null,
        egress_allowlist: [],
        last_heartbeat_at: '2026-08-12T08:00:00Z',
        last_error: null,
        created_at: '2026-08-12T08:00:00Z',
        updated_at: '2026-08-12T08:00:00Z',
      },
    ])

    const wrapper = mountPage()
    await flushPromises()

    const vm = wrapper.vm as any
    vm.openRun({ id: 3, executor: 'jmeter' })

    expect(vm.runNodeOptions).toEqual([
      expect.objectContaining({ value: 1, disabled: true }),
      expect.objectContaining({ value: 2, disabled: false }),
    ])
    expect(vm.runNodeOptions[0].label).toContain('performance.node_executor_unavailable')
    wrapper.unmount()
  })

  it('sends a stable idempotency key for a manual run submission', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const vm = wrapper.vm as any
    vm.openRun({ id: 3 })
    await vm.triggerRun()

    expect(triggerRun).toHaveBeenCalledWith(3, expect.objectContaining({
      idempotency_key: expect.any(String),
    }))
    expect(vm.runForm.idempotency_key).toBeTruthy()
    wrapper.unmount()
  })

  it('surfaces backend run validation details', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const vm = wrapper.vm as any
    vm.openRun({ id: 3 })
    triggerRun.mockRejectedValueOnce('性能节点容量不足')

    await vm.triggerRun()

    expect(messageError).toHaveBeenCalledWith('性能节点容量不足')
    wrapper.unmount()
  })
})
