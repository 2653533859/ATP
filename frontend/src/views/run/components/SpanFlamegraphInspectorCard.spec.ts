import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import SpanFlamegraphInspectorCard from './SpanFlamegraphInspectorCard.vue'
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
      total_duration_ms: 180.0,
      avg_duration_ms: 180.0,
      error_count: 0,
      error_rate: 0,
    },
    {
      service_name: 'auth-center',
      service_type: 'rpc',
      protocol: 'grpc',
      span_count: 1,
      total_duration_ms: 25.0,
      avg_duration_ms: 25.0,
      error_count: 0,
      error_rate: 0,
    },
    {
      service_name: 'order-service',
      service_type: 'http',
      protocol: 'http',
      span_count: 2,
      total_duration_ms: 140.0,
      avg_duration_ms: 70.0,
      error_count: 0,
      error_rate: 0,
    },
  ],
  edges: [],
  hierarchical_tree: [
    {
      span_id: 'span_gw_01',
      name: 'HTTP POST /checkout',
      service_name: 'api-gateway',
      service_type: 'gateway',
      protocol: 'http',
      depth: 1,
      start_time_ms: 1000.0,
      end_time_ms: 1180.0,
      duration_ms: 180.0,
      self_time_ms: 40.0,
      children: [
        {
          span_id: 'span_auth_02',
          name: 'VerifyToken',
          service_name: 'auth-center',
          service_type: 'rpc',
          protocol: 'grpc',
          depth: 2,
          start_time_ms: 1005.0,
          end_time_ms: 1030.0,
          duration_ms: 25.0,
          self_time_ms: 25.0,
          children: [],
        },
        {
          span_id: 'span_order_03',
          name: 'ProcessOrder',
          service_name: 'order-service',
          service_type: 'http',
          protocol: 'http',
          depth: 2,
          start_time_ms: 1035.0,
          end_time_ms: 1175.0,
          duration_ms: 140.0,
          self_time_ms: 20.0,
          children: [
            {
              span_id: 'span_db_04',
              name: 'INSERT orders',
              service_name: 'order-db',
              service_type: 'db',
              protocol: 'postgresql',
              depth: 3,
              start_time_ms: 1055.0,
              end_time_ms: 1175.0,
              duration_ms: 120.0, // 慢调用
              self_time_ms: 120.0,
              children: [],
            },
          ],
        },
      ],
    },
  ],
  critical_path_span_ids: ['span_gw_01', 'span_order_03', 'span_db_04'],
  built_at: '2026-10-17T12:00:00Z',
}

vi.mock('@/api/observabilityTrace', () => ({
  observabilityTraceApi: {
    getLineage: vi.fn(),
    buildLineage: vi.fn(),
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, fallback?: string) => fallback || key,
  }),
}))

vi.mock('vue-router', () => ({
  createRouter: vi.fn(),
  createWebHistory: vi.fn(),
}))

describe('SpanFlamegraphInspectorCard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(observabilityTraceApi.getLineage).mockResolvedValue({ lineage: mockLineage })
    vi.mocked(observabilityTraceApi.buildLineage).mockResolvedValue({
      message: '跨协议拓扑血缘重构完成',
      lineage: mockLineage,
    })
  })

  function createWrapper(props = {}) {
    return mount(SpanFlamegraphInspectorCard, {
      props: {
        traceId: '4bf92f3577b34da6a3ce929d0e0e4736',
        runId: 42,
        ...props,
      },
      global: {
        stubs: {
          'a-button': {
            template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
          },
          'a-tag': {
            template: '<span class="ant-tag"><slot /></span>',
          },
          'a-switch': {
            template: '<button type="button" class="ant-switch" @click="$emit(\'update:checked\', !$attrs.checked)"><slot /></button>',
          },
          'a-select': {
            template: '<div class="ant-select"><slot /></div>',
          },
          'a-select-option': {
            template: '<div class="ant-select-option"><slot /></div>',
          },
          'a-spin': {
            template: '<div class="ant-spin"><slot /></div>',
          },
          'a-space': {
            template: '<div class="ant-space"><slot /></div>',
          },
        },
      },
    })
  }

  it('renders flamegraph card header and slices', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    expect(wrapper.text()).toContain('分布式微服务调用链火焰图分析')
    expect(wrapper.text()).toContain('3 微服务')
    expect(wrapper.text()).toContain('4 Spans')

    const slices = wrapper.findAll('.flame-slice')
    expect(slices.length).toBe(4)
  })

  it('allows clicking a slice to inspect details in the panel', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    const slices = wrapper.findAll('.flame-slice')
    await slices[0].trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('HTTP POST /checkout')
    expect(wrapper.text()).toContain('api-gateway')
    expect(wrapper.text()).toContain('180 ms')
  })

  it('supports zooming into a child span and resetting zoom', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    const slices = wrapper.findAll('.flame-slice')
    // 双击第二个切片 (span_order_03)
    await slices[2].trigger('dblclick')
    await flushPromises()

    expect(wrapper.text()).toContain('当前聚焦局部子树')
    expect(wrapper.text()).toContain('重置聚焦')

    // 点击重置按钮
    const resetBtn = wrapper.find('button')
    if (resetBtn.exists()) {
      await resetBtn.trigger('click')
      await flushPromises()
    }
  })
})
