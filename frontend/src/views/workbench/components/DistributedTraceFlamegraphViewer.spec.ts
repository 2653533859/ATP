import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import DistributedTraceFlamegraphViewer from './DistributedTraceFlamegraphViewer.vue'
import { distributedTracesApi } from '@/api/distributedTraces'

const mockTraceReport = {
  trace_id: 'trace_checkout_9988',
  root_service: 'api-gateway',
  root_operation: 'HTTP POST /api/v1/orders/checkout',
  total_spans_count: 5,
  total_duration_ms: 1450.0,
  services_involved: ['api-gateway', 'auth-service', 'order-service', 'payment-service'],
  slow_spans_count: 1,
  slow_spans: [
    {
      span_id: 'span_pay_01',
      trace_id: 'trace_checkout_9988',
      parent_span_id: 'span_order_01',
      service_name: 'payment-service',
      operation_name: 'process_card_third_party',
      kind: 'SERVER',
      start_time_us: 1700000000000,
      duration_us: 1250000,
      duration_ms: 1250.0,
      self_time_ms: 1220.0,
      status: 'OK',
      is_slow: true,
      attributes: { 'http.status_code': 200 },
    },
  ],
  flamegraph_root: {
    name: 'api-gateway: HTTP POST /api/v1/orders/checkout',
    value: 1450000,
    span_id: 'span_root_01',
    service_name: 'api-gateway',
    duration_ms: 1450.0,
    self_time_ms: 35.0,
    is_slow: false,
    status: 'OK',
    children: [
      {
        name: 'order-service: create_order_entity',
        value: 1380000,
        span_id: 'span_order_01',
        service_name: 'order-service',
        duration_ms: 1380.0,
        self_time_ms: 130.0,
        is_slow: false,
        status: 'OK',
        children: [
          {
            name: 'payment-service: process_card_third_party',
            value: 1250000,
            span_id: 'span_pay_01',
            service_name: 'payment-service',
            duration_ms: 1250.0,
            self_time_ms: 1220.0,
            is_slow: true,
            status: 'OK',
            children: [],
          },
        ],
      },
    ],
  },
  spans_flat: [
    {
      span_id: 'span_root_01',
      trace_id: 'trace_checkout_9988',
      parent_span_id: null,
      service_name: 'api-gateway',
      operation_name: 'HTTP POST /api/v1/orders/checkout',
      kind: 'SERVER',
      start_time_us: 1700000000000,
      duration_us: 1450000,
      duration_ms: 1450.0,
      self_time_ms: 35.0,
      status: 'OK',
      is_slow: false,
      attributes: {},
    },
    {
      span_id: 'span_order_01',
      trace_id: 'trace_checkout_9988',
      parent_span_id: 'span_root_01',
      service_name: 'order-service',
      operation_name: 'create_order_entity',
      kind: 'SERVER',
      start_time_us: 1700000010000,
      duration_us: 1380000,
      duration_ms: 1380.0,
      self_time_ms: 130.0,
      status: 'OK',
      is_slow: false,
      attributes: {},
    },
    {
      span_id: 'span_pay_01',
      trace_id: 'trace_checkout_9988',
      parent_span_id: 'span_order_01',
      service_name: 'payment-service',
      operation_name: 'process_card_third_party',
      kind: 'SERVER',
      start_time_us: 1700000050000,
      duration_us: 1250000,
      duration_ms: 1250.0,
      self_time_ms: 1220.0,
      status: 'OK',
      is_slow: true,
      attributes: {},
    },
  ],
  bottleneck_summary: '全链路耗时最大瓶颈位于 payment-service::process_card_third_party (1250.0ms)',
  created_at: '2026-10-16T10:00:00Z',
}

vi.mock('@/api/distributedTraces', () => ({
  distributedTracesApi: {
    listTraces: vi.fn(),
    getTrace: vi.fn(),
    ingestTrace: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('@ant-design/icons-vue', () => ({
  ApartmentOutlined: { template: '<span>Apartment</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  FireOutlined: { template: '<span>Fire</span>' },
  AlertOutlined: { template: '<span>Alert</span>' },
  CheckCircleOutlined: { template: '<span>Check</span>' },
}))

describe('DistributedTraceFlamegraphViewer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(distributedTracesApi.listTraces).mockResolvedValue({
      total: 1,
      traces: [mockTraceReport as any],
    })
    vi.mocked(distributedTracesApi.getTrace).mockResolvedValue(mockTraceReport as any)
  })

  it('renders trace overview, flamegraph blocks, and bottleneck analysis', async () => {
    const wrapper = mount(DistributedTraceFlamegraphViewer, {
      global: {
        stubs: {
          'a-spin': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-tabs': { template: '<div><slot /></div>' },
          'a-tab-pane': { template: '<div><slot /></div>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
          'a-progress': { template: '<div class="ant-progress" />' },
        },
      },
    })

    await flushPromises()

    // 验证头部与总时延
    expect(wrapper.text()).toContain('分布式追踪 TraceID 慢调用火焰图分析')
    expect(wrapper.text()).toContain('1450')
    expect(wrapper.text()).toContain('全链路总时延')

    // 验证根节点与瓶颈诊断
    expect(wrapper.text()).toContain('api-gateway :: HTTP POST /api/v1/orders/checkout')
    expect(wrapper.text()).toContain('全链路耗时最大瓶颈位于 payment-service::process_card_third_party')
    expect(wrapper.text()).toContain('慢调用 (Slow)')
    expect(wrapper.text()).toContain('1')

    // 验证火焰图 Block 渲染
    expect(wrapper.text()).toContain('process_card_third_party')

    expect(distributedTracesApi.listTraces).toHaveBeenCalled()
    expect(distributedTracesApi.getTrace).toHaveBeenCalledWith('trace_checkout_9988')
  })

  it('triggers demo trace ingestion and updates report', async () => {
    vi.mocked(distributedTracesApi.ingestTrace).mockResolvedValue({
      message: '全链路 Trace 火焰图构建成功',
      report: mockTraceReport as any,
    })

    const wrapper = mount(DistributedTraceFlamegraphViewer, {
      global: {
        stubs: {
          'a-spin': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-tabs': { template: '<div><slot /></div>' },
          'a-tab-pane': { template: '<div><slot /></div>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
          'a-progress': { template: '<div class="ant-progress" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.handleIngestDemo()

    expect(distributedTracesApi.ingestTrace).toHaveBeenCalledWith(expect.objectContaining({
      slow_span_threshold_ms: 100.0,
      spans: expect.any(Array),
    }))
  })
})
