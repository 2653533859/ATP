import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import DistributedTraceAlignmentDashboardView from './DistributedTraceAlignmentDashboardView.vue'
import { observabilityTraceApi } from '@/api/observabilityTrace'

const mockLineages = [
  {
    trace_id: '4bf92f3577b34da6a3ce929d0e0e4736',
    root_service: 'api-gateway',
    total_spans: 6,
    services_count: 5,
    max_depth_hops: 4,
    protocols_covered: ['http', 'grpc', 'postgresql', 'redis', 'kafka'],
    nodes: [],
    edges: [],
    hierarchical_tree: [],
    critical_path_span_ids: [],
    built_at: '2026-10-17 12:30:00',
  },
  {
    trace_id: '7ca6473577b34da6a3ce929d0e0e9988',
    root_service: 'report-worker',
    total_spans: 4,
    services_count: 3,
    max_depth_hops: 3,
    protocols_covered: ['http', 'postgresql'],
    nodes: [],
    edges: [],
    hierarchical_tree: [],
    critical_path_span_ids: [],
    built_at: '2026-10-17 12:25:00',
  },
]

vi.mock('@/api/observabilityTrace', () => ({
  observabilityTraceApi: {
    listLineages: vi.fn(),
    getLineage: vi.fn(),
    buildLineage: vi.fn(),
    compensateClockSkew: vi.fn(),
    deepDiveAnalysis: vi.fn(),
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, fallback?: string) => fallback || key,
  }),
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
}))

describe('DistributedTraceAlignmentDashboardView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(observabilityTraceApi.listLineages).mockResolvedValue({
      total: 2,
      lineages: mockLineages,
    })
  })

  function createWrapper() {
    return mount(DistributedTraceAlignmentDashboardView, {
      global: {
        stubs: {
          'a-card': {
            template: '<div class="ant-card"><div class="ant-card-head-title">{{ title }}</div><slot /><slot name="extra" /></div>',
            props: ['title'],
          },
          'a-tag': {
            template: '<span class="ant-tag"><slot /></span>',
          },
          'a-space': {
            template: '<div class="ant-space"><slot /></div>',
          },
          'a-input-search': {
            template: '<input class="ant-input-search" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
            props: ['value'],
          },
          'a-table': {
            template: `
              <div class="ant-table">
                <div v-for="item in dataSource" :key="item.trace_id" class="table-row">
                  <span class="row-trace-id">{{ item.trace_id }}</span>
                  <span class="row-root-svc">{{ item.root_service }}</span>
                  <button class="open-gantt-btn" @click="$emit('open-gantt', item)">甘特时序</button>
                </div>
              </div>
            `,
            props: ['dataSource', 'columns'],
          },
          StepTraceTimelineDrawer: {
            template: '<div v-if="open" class="step-trace-drawer-stub" />',
            props: ['open', 'traceId'],
          },
        },
      },
    })
  }

  it('renders dashboard title and 4 KPI metrics cards', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    expect(wrapper.text()).toContain('全局测试执行分布式追踪贯通全景大盘')
    expect(wrapper.text()).toContain('全站用例 Trace 对齐率')
    expect(wrapper.text()).toContain('100%')
    expect(wrapper.text()).toContain('微服务平均调用跳数')
    expect(wrapper.text()).toContain('慢跨度告警数')
    expect(wrapper.text()).toContain('异构通讯协议覆盖')
  })

  it('renders topology matrix nodes and protocol stats', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    expect(wrapper.text()).toContain('微服务跨协议拓扑与血缘依赖矩阵')
    expect(wrapper.text()).toContain('api-gateway')
    expect(wrapper.text()).toContain('auth-center')
    expect(wrapper.text()).toContain('order-service')

    expect(wrapper.text()).toContain('通讯协议调用占比与时延分布')
    expect(wrapper.text()).toContain('REST API 接口网关')
    expect(wrapper.text()).toContain('微服务内部 RPC')
  })

  it('renders table data rows', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    expect(wrapper.text()).toContain('4bf92f3577b34da6a3ce929d0e0e4736')
    expect(wrapper.text()).toContain('7ca6473577b34da6a3ce929d0e0e9988')
  })
})
