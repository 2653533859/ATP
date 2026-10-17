import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import StepTraceTimelineDrawer from './StepTraceTimelineDrawer.vue'
import { observabilityTraceApi } from '@/api/observabilityTrace'

const mockLineage = {
  trace_id: '4bf92f3577b34da6a3ce929d0e0e4736',
  total_spans: 4,
  services_count: 3,
  max_depth_hops: 3,
  protocols_covered: ['grpc', 'http', 'postgresql'],
  root_service: 'api-gateway',
  nodes: [
    {
      service_name: 'api-gateway',
      service_type: 'gateway',
      protocol: 'http',
      span_count: 1,
      total_duration_ms: 120.0,
      avg_duration_ms: 120.0,
      error_count: 0,
      error_rate: 0,
    },
    {
      service_name: 'auth-center',
      service_type: 'rpc',
      protocol: 'grpc',
      span_count: 1,
      total_duration_ms: 30.0,
      avg_duration_ms: 30.0,
      error_count: 0,
      error_rate: 0,
    },
    {
      service_name: 'order-service',
      service_type: 'http',
      protocol: 'http',
      span_count: 2,
      total_duration_ms: 90.0,
      avg_duration_ms: 45.0,
      error_count: 0,
      error_rate: 0,
    },
  ],
  edges: [
    {
      source_service: 'api-gateway',
      target_service: 'auth-center',
      protocol: 'grpc',
      call_count: 1,
      avg_latency_ms: 30.0,
    },
  ],
  hierarchical_tree: [
    {
      span_id: 'span_gw_01',
      name: 'HTTP POST /order/checkout',
      service_name: 'api-gateway',
      service_type: 'gateway',
      protocol: 'http',
      depth: 1,
      start_time_ms: 1000.0,
      end_time_ms: 1120.0,
      duration_ms: 120.0,
      self_time_ms: 90.0,
      children: [
        {
          span_id: 'span_auth_02',
          name: 'VerifyToken',
          service_name: 'auth-center',
          service_type: 'rpc',
          protocol: 'grpc',
          depth: 2,
          start_time_ms: 1010.0,
          end_time_ms: 1040.0,
          duration_ms: 30.0,
          self_time_ms: 30.0,
          children: [],
        },
      ],
    },
  ],
  critical_path_span_ids: ['span_gw_01', 'span_auth_02'],
  built_at: '2026-10-17T12:00:00Z',
}

const mockDiagnosis = {
  trace_id: '4bf92f3577b34da6a3ce929d0e0e4736',
  step_name: '步骤 1: 提交订单',
  step_status: 'FAILED',
  attribution_type: 'DOWNSTREAM_SERVICE_ERROR',
  root_cause_service: 'payment-service',
  root_cause_span_id: 'span_pay_06',
  root_cause_span_name: 'DeductPayment',
  error_message: '银行通道超时',
  stack_trace: 'Traceback: TimeoutException',
  slow_queries: [
    {
      span_id: 'span_slow_db',
      service_name: 'order-db',
      db_system: 'postgresql',
      duration_ms: 220.0,
      statement: 'SELECT * FROM orders FOR UPDATE',
    },
  ],
  total_spans_analyzed: 4,
  error_spans_count: 1,
  diagnosis_summary: '步骤在下游微服务 [payment-service] 发生超时。',
  suggested_action: '调大 RPC 连接超时时间或检查网关。',
  diagnosed_at: '2026-10-17T12:00:00Z',
}
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, fallback?: string) => fallback || key,
  }),
}))

vi.mock('vue-router', () => ({
  createRouter: vi.fn(),
  createWebHistory: vi.fn(),
}))


vi.mock('@/api/observabilityTrace', () => ({
  observabilityTraceApi: {
    getLineage: vi.fn(),
    buildLineage: vi.fn(),
    deepDiveAnalysis: vi.fn(),
    compensateClockSkew: vi.fn(),
  },
}))

describe('StepTraceTimelineDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(observabilityTraceApi.getLineage).mockResolvedValue({ lineage: mockLineage })
    vi.mocked(observabilityTraceApi.buildLineage).mockResolvedValue({
      message: '跨协议拓扑血缘重构完成',
      lineage: mockLineage,
    })
    vi.mocked(observabilityTraceApi.deepDiveAnalysis).mockResolvedValue({
      message: '调用链深潜下钻分析完成',
      diagnosis: mockDiagnosis,
    })
  })

  function createWrapper(props = {}) {
    return mount(StepTraceTimelineDrawer, {
      props: {
        open: true,
        traceId: '4bf92f3577b34da6a3ce929d0e0e4736',
        step: {
          step_index: 0,
          name: '步骤 1: 提交订单',
          status: 'passed',
          duration_ms: 120,
        },
        ...props,
      },
      global: {
        stubs: {
          'a-drawer': {
            template: '<div v-if="open" class="ant-drawer"><slot /></div>',
            props: ['open'],
          },
          'a-button': {
            template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
          },
          'a-tag': {
            template: '<span class="ant-tag"><slot /></span>',
          },
          'a-descriptions': {
            template: '<div class="ant-descriptions"><slot /></div>',
          },
          'a-descriptions-item': {
            template: '<div class="ant-descriptions-item"><slot /></div>',
          },
          'a-spin': {
            template: '<div class="ant-spin"><slot /></div>',
          },
          'a-empty': {
            template: '<div class="ant-empty"><slot /></div>',
            props: ['description'],
          },
          'a-space': {
            template: '<div class="ant-space"><slot /></div>',
          },
        },
      },
    })
  }

  it('renders trace drawer metadata and gantt rows', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    expect(wrapper.text()).toContain('TraceID:')
    expect(wrapper.text()).toContain('4bf92f3577b34da6a3ce929d0e0e4736')
    expect(wrapper.text()).toContain('api-gateway')
    expect(wrapper.text()).toContain('HTTP POST /order/checkout')
  })

  it('allows clicking a span to select and inspect its properties', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    const rows = wrapper.findAll('.gantt-row')
    expect(rows.length).toBeGreaterThan(0)
    await rows[0].trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Span 详细属性下钻')
    expect(wrapper.text()).toContain('HTTP POST /order/checkout')
    expect(wrapper.text()).toContain('span_gw_01')
  })

  it('renders root cause diagnosis banner when triggered', async () => {
    const wrapper = createWrapper({
      step: {
        step_index: 1,
        name: '步骤 2: 扣款',
        status: 'failed',
        error_message: '504 Gateway Timeout',
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('故障根因归因: DOWNSTREAM_SERVICE_ERROR')
    expect(wrapper.text()).toContain('微服务: payment-service')
    expect(wrapper.text()).toContain('排障建议:')
    expect(wrapper.text()).toContain('检出慢 SQL')
  })
})
