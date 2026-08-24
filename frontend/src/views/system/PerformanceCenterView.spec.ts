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
  triggerRun,
  testCreate,
  nodeList,
  nodeCreate,
  nodeUpdate,
  nodeDelete,
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
  triggerRun: vi.fn(),
  testCreate: vi.fn(),
  nodeList: vi.fn(),
  nodeCreate: vi.fn(),
  nodeUpdate: vi.fn(),
  nodeDelete: vi.fn(),
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
    triggerRun,
    createTest: testCreate,
    createNode: nodeCreate,
    updateNode: nodeUpdate,
    deleteNode: nodeDelete,
  },
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
    triggerRun.mockResolvedValue({ id: 10 })
    testCreate.mockResolvedValue({ id: 2 })
    nodeList.mockResolvedValue([])
    nodeCreate.mockResolvedValue({ id: 1 })
    nodeUpdate.mockResolvedValue({ id: 1 })
    nodeDelete.mockResolvedValue(undefined)
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
