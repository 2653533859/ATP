import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import TraceAnomalySlowCallClusterCard from './TraceAnomalySlowCallClusterCard.vue'
import { traceAnomalyApi } from '@/api/traceObservability'

const mockMixedReport = {
  total_spans_analyzed: 4,
  total_anomalies_detected: 3,
  clusters_count: 2,
  clusters: [
    {
      cluster_id: 'cls_pay_service_timeout',
      service_name: 'pay-service',
      operation_name: 'call_alipay_gateway',
      pattern: 'TIMEOUT_BREACH',
      occurrences_count: 1,
      avg_duration_ms: 3500.0,
      p95_duration_ms: 3500.0,
      max_duration_ms: 3500.0,
      deviation_sigma: 3.5,
      error_ratio_pct: 100.0,
      impact_score: 35.0,
      root_cause_explanation: '[pay-service] 遭遇上游/网络超时截断，最大耗时 3500ms。',
      actionable_recommendations: ['调大超时时间或配置熔断回退策略'],
      sample_trace_ids: ['t_m_3'],
    },
    {
      cluster_id: 'cls_order_service_slow_sql',
      service_name: 'order-service',
      operation_name: 'SELECT * FROM orders',
      pattern: 'SLOW_DATABASE_QUERY',
      occurrences_count: 2,
      avg_duration_ms: 320.0,
      p95_duration_ms: 360.0,
      max_duration_ms: 360.0,
      deviation_sigma: 1.8,
      error_ratio_pct: 0.0,
      impact_score: 3.2,
      root_cause_explanation: '[order-service] 频繁触发慢 SQL 查询，平均时延 320ms。',
      actionable_recommendations: ['添加复合索引避免全表扫描'],
      sample_trace_ids: ['t_m_1', 't_m_2'],
    },
  ],
  verdict_summary: '检出 2 个异常慢调用聚类簇，首要危害簇为 [pay-service] 的 call_alipay_gateway (TIMEOUT_BREACH)。',
  analyzed_at: '2026-10-16T12:00:00Z',
}

const mockHealthyReport = {
  total_spans_analyzed: 2,
  total_anomalies_detected: 0,
  clusters_count: 0,
  clusters: [],
  verdict_summary: '全链路无显著慢调用或异常波动，性能表现稳健。',
  analyzed_at: '2026-10-16T12:05:00Z',
}

vi.mock('@/api/traceObservability', () => ({
  traceAnomalyApi: {
    analyze: vi.fn(),
    telemetryDiagnose: vi.fn(),
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
  SlidersOutlined: { template: '<span>Sliders</span>' },
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
}))

describe('TraceAnomalySlowCallClusterCard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(traceAnomalyApi.analyze).mockResolvedValue(mockMixedReport as any)
    vi.mocked(traceAnomalyApi.telemetryDiagnose).mockResolvedValue(mockMixedReport as any)
  })

  it('renders verdict banner, KPI metrics, and clusters table', async () => {
    const wrapper = mount(TraceAnomalySlowCallClusterCard, {
      global: {
        stubs: {
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input-number': { template: '<input type="number" />' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.cluster_id" class="row">
                  <span class="pattern">{{ item.pattern }}</span>
                  <span class="svc">{{ item.service_name }}</span>
                  <span class="score">{{ item.impact_score }}</span>
                </div>
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()

    // 检查调用与标题
    expect(traceAnomalyApi.analyze).toHaveBeenCalled()
    expect(wrapper.text()).toContain('分布式调用链异常波动与高频慢调用智能聚类诊断引擎')

    // 检查横幅与 KPI
    expect(wrapper.text()).toContain('检出 2 个异常慢调用聚类簇')
    expect(wrapper.text()).toContain('4') // total spans
    expect(wrapper.text()).toContain('3') // anomalies count

    // 检查表格项
    expect(wrapper.text()).toContain('TIMEOUT_BREACH')
    expect(wrapper.text()).toContain('SLOW_DATABASE_QUERY')
    expect(wrapper.text()).toContain('pay-service')
    expect(wrapper.text()).toContain('order-service')
  })

  it('switches preset to healthy and triggers telemetry diagnose', async () => {
    vi.mocked(traceAnomalyApi.analyze).mockResolvedValueOnce(mockMixedReport as any).mockResolvedValueOnce(mockHealthyReport as any)

    const wrapper = mount(TraceAnomalySlowCallClusterCard, {
      global: {
        stubs: {
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input-number': { template: '<input type="number" />' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.applyPreset('healthy')
    await flushPromises()

    expect(traceAnomalyApi.analyze).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('全链路表现健康')

    // 触发全网链路诊断
    await vm.runTelemetryDiagnosis()
    expect(traceAnomalyApi.telemetryDiagnose).toHaveBeenCalled()
  })
})
