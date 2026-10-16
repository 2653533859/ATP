import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import CriticalPathFlamegraphDashboardView from './CriticalPathFlamegraphDashboardView.vue'
import { traceFlamegraphApi } from '@/api/traceObservability'

const mockExternalReport = {
  trace_id: 'trace_preset_external_101',
  total_trace_duration_ms: 420.0,
  critical_path_duration_ms: 420.0,
  critical_path_spans_count: 3,
  critical_path: [
    {
      span_id: 's_gw',
      parent_span_id: null,
      name: 'POST /checkout',
      service_name: 'api-gateway',
      duration_ms: 420.0,
      self_time_ms: 40.0,
      critical_path_ratio_pct: 9.5,
      is_bottleneck: false,
      bottleneck_category: 'NONE',
    },
    {
      span_id: 's_order',
      parent_span_id: 's_gw',
      name: 'create_order_flow',
      service_name: 'order-service',
      duration_ms: 380.0,
      self_time_ms: 80.0,
      critical_path_ratio_pct: 19.0,
      is_bottleneck: false,
      bottleneck_category: 'NONE',
    },
    {
      span_id: 's_pay',
      parent_span_id: 's_order',
      name: 'call_alipay_gateway',
      service_name: 'pay-service',
      duration_ms: 300.0,
      self_time_ms: 300.0,
      critical_path_ratio_pct: 71.4,
      is_bottleneck: true,
      bottleneck_category: 'EXTERNAL_HTTP_LATENCY',
    },
  ],
  primary_bottleneck: {
    span_id: 's_pay',
    parent_span_id: 's_order',
    name: 'call_alipay_gateway',
    service_name: 'pay-service',
    duration_ms: 300.0,
    self_time_ms: 300.0,
    critical_path_ratio_pct: 71.4,
    is_bottleneck: true,
    bottleneck_category: 'EXTERNAL_HTTP_LATENCY',
  },
  flamegraph_root: {
    name: 'POST /checkout',
    value: 420.0,
    self_value: 40.0,
    service_name: 'api-gateway',
    span_id: 's_gw',
    is_critical_path: true,
    is_bottleneck: false,
    bottleneck_category: 'NONE',
    children: [
      {
        name: 'create_order_flow',
        value: 380.0,
        self_value: 80.0,
        service_name: 'order-service',
        span_id: 's_order',
        is_critical_path: true,
        is_bottleneck: false,
        bottleneck_category: 'NONE',
        children: [
          {
            name: 'call_alipay_gateway',
            value: 300.0,
            self_value: 300.0,
            service_name: 'pay-service',
            span_id: 's_pay',
            is_critical_path: true,
            is_bottleneck: true,
            bottleneck_category: 'EXTERNAL_HTTP_LATENCY',
            children: [],
          },
        ],
      },
    ],
  },
  diagnosis_summary: '关键路径总时延 420ms，首要瓶颈为 [pay-service] 的 call_alipay_gateway (71.4%)。',
  profiled_at: '2026-10-16T12:00:00Z',
}

const mockDbReport = {
  ...mockExternalReport,
  primary_bottleneck: {
    span_id: 's_sql_slow',
    parent_span_id: 's_root_user',
    name: 'SELECT * FROM users',
    service_name: 'user-service',
    duration_ms: 250.0,
    self_time_ms: 250.0,
    critical_path_ratio_pct: 78.1,
    is_bottleneck: true,
    bottleneck_category: 'DATABASE_SLOW_QUERY',
  },
  diagnosis_summary: '关键路径首要瓶颈为 [user-service] 数据库慢查询 (DATABASE_SLOW_QUERY)。',
}

vi.mock('@/api/traceObservability', () => ({
  traceFlamegraphApi: {
    profileById: vi.fn(),
    profileSpans: vi.fn(),
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
  FireOutlined: { template: '<span>Fire</span>' },
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
}))

describe('CriticalPathFlamegraphDashboardView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(traceFlamegraphApi.profileSpans).mockResolvedValue(mockExternalReport as any)
  })

  it('renders page hero, bottleneck banner, flamegraph rows, and critical path table', async () => {
    const wrapper = mount(CriticalPathFlamegraphDashboardView, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
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
    expect(traceFlamegraphApi.profileSpans).toHaveBeenCalled()
    expect(wrapper.text()).toContain('跨微服务关键路径时延分析与火焰图性能瓶颈大盘')

    // 检查瓶颈横幅
    expect(wrapper.text()).toContain('EXTERNAL_HTTP_LATENCY')
    expect(wrapper.text()).toContain('420 ms')
    expect(wrapper.text()).toContain('300 ms')
    expect(wrapper.text()).toContain('71.4%')

    // 检查火焰图
    expect(wrapper.text()).toContain('分层性能火焰图 (Interactive Flamegraph)')
    expect(wrapper.text()).toContain('call_alipay_gateway')

    // 检查表格
    expect(wrapper.text()).toContain('关键路径执行序列与时延贡献矩阵')
  })

  it('switches preset to database and updates bottleneck banner', async () => {
    vi.mocked(traceFlamegraphApi.profileSpans).mockResolvedValueOnce(mockExternalReport as any).mockResolvedValueOnce(mockDbReport as any)

    const wrapper = mount(CriticalPathFlamegraphDashboardView, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-progress': { template: '<div class="progress" />' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.applyPreset('database')
    await flushPromises()

    expect(traceFlamegraphApi.profileSpans).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('DATABASE_SLOW_QUERY')
  })
})
