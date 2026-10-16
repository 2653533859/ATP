import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import DistributedTraceSpanTreeDrawer from './DistributedTraceSpanTreeDrawer.vue'
import { traceTelemetryApi } from '@/api/traceObservability'

const mockTraceTree = {
  trace_id: '4bf92f3577b34da6a3ce929d0e0e4736',
  root_span_id: '00f067aa0ba902b7',
  total_spans_count: 4,
  total_duration_ms: 550.0,
  services_involved: ['api-gateway', 'order-service', 'pay-service', 'inventory-service'],
  has_error: true,
  root_nodes: [
    {
      trace_id: '4bf92f3577b34da6a3ce929d0e0e4736',
      span_id: '00f067aa0ba902b7',
      parent_span_id: null,
      name: 'POST /api/v1/orders/checkout',
      service_name: 'api-gateway',
      kind: 'SERVER',
      duration_ms: 550.0,
      status_code: 'ERROR',
      attributes: { 'http.status_code': 504 },
      children: [
        {
          trace_id: '4bf92f3577b34da6a3ce929d0e0e4736',
          span_id: '11a067aa0ba902b8',
          parent_span_id: '00f067aa0ba902b7',
          name: 'create_order_flow',
          service_name: 'order-service',
          kind: 'INTERNAL',
          duration_ms: 500.0,
          status_code: 'ERROR',
          attributes: { 'order.id': 1001 },
          children: [
            {
              trace_id: '4bf92f3577b34da6a3ce929d0e0e4736',
              span_id: '22b067aa0ba902b9',
              parent_span_id: '11a067aa0ba902b8',
              name: 'call_payment_gateway',
              service_name: 'pay-service',
              kind: 'CLIENT',
              duration_ms: 450.0,
              status_code: 'ERROR',
              status_message: 'HTTPSConnectionPool: Read timed out (504)',
              attributes: { 'http.status_code': 504 },
              children: [],
            },
          ],
        },
      ],
    },
  ],
  extracted_at: '2026-10-16T12:00:00Z',
}

const mockSummary = {
  trace_id: '4bf92f3577b34da6a3ce929d0e0e4736',
  root_span_id: '00f067aa0ba902b7',
  root_operation: 'POST /api/v1/orders/checkout',
  root_service: 'api-gateway',
  total_spans_count: 4,
  total_duration_ms: 550.0,
  services_involved: ['api-gateway', 'order-service', 'pay-service', 'inventory-service'],
  has_error: true,
  extracted_at: '2026-10-16T12:00:00Z',
}

vi.mock('@/api/traceObservability', () => ({
  traceTelemetryApi: {
    ingestSpans: vi.fn(),
    listTraces: vi.fn(),
    getTraceTree: vi.fn(),
    clearTraces: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}))

vi.mock('@ant-design/icons-vue', () => ({
  ClusterOutlined: { template: '<span>Cluster</span>' },
  CopyOutlined: { template: '<span>Copy</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
}))

describe('DistributedTraceSpanTreeDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(traceTelemetryApi.ingestSpans).mockResolvedValue({
      message: 'Span 采集中继成功',
      ingested_count: 4,
      traces_updated_count: 1,
      trace_ids: ['4bf92f3577b34da6a3ce929d0e0e4736'],
    })
    vi.mocked(traceTelemetryApi.listTraces).mockResolvedValue({
      total: 1,
      traces: [mockSummary as any],
    })
    vi.mocked(traceTelemetryApi.getTraceTree).mockResolvedValue(mockTraceTree as any)
  })

  it('renders W3C traceparent header, trace chips, and hierarchical span tree table', async () => {
    const wrapper = mount(DistributedTraceSpanTreeDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-switch': { template: '<input type="checkbox" />' },
          'a-progress': { template: '<div class="progress" />' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.span_id" class="row">
                  <span class="svc">{{ item.service_name }}</span>
                  <span class="name">{{ item.name }}</span>
                  <span class="dur">{{ item.duration_ms }} ms</span>
                </div>
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()

    // 检查调用与标题
    expect(traceTelemetryApi.ingestSpans).toHaveBeenCalled()
    expect(traceTelemetryApi.listTraces).toHaveBeenCalled()
    expect(traceTelemetryApi.getTraceTree).toHaveBeenCalled()
    expect(wrapper.text()).toContain('OpenTelemetry / W3C TraceContext 全链路调用树追踪')

    // 检查 W3C traceparent
    expect(wrapper.text()).toContain('00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01')

    // 检查 KPI 统计横幅
    expect(wrapper.text()).toContain('550 ms')
    expect(wrapper.text()).toContain('4 个')
    expect(wrapper.text()).toContain('存在未捕获异常')

    // 检查树形调用表格
    expect(wrapper.text()).toContain('api-gateway')
    expect(wrapper.text()).toContain('POST /api/v1/orders/checkout')
  })

  it('applies profile preset and selects the new trace', async () => {
    const wrapper = mount(DistributedTraceSpanTreeDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-switch': { template: '<input type="checkbox" />' },
          'a-progress': { template: '<div class="progress" />' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.applyPreset('profile')
    await flushPromises()

    expect(traceTelemetryApi.ingestSpans).toHaveBeenCalledTimes(2)
  })
})
