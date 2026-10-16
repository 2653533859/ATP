import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ResilienceRtoRecoveryDashboardCard from './ResilienceRtoRecoveryDashboardCard.vue'
import { resilienceRtoApi } from '@/api/trafficGateway'

const mockExcellentReport = {
  report_id: 'rto_test_101',
  target_service_id: 'order-service',
  endpoint: 'POST /api/v1/orders/checkout',
  resilience_tier: 'EXCELLENT',
  breaker_trip_latency_ms: 85.0,
  fallback_success_ratio_pct: 99.2,
  rto_recovery_duration_ms: 420.0,
  total_samples_analyzed: 10,
  fault_period_requests_count: 5,
  recovery_period_requests_count: 5,
  sample_stream: [
    {
      seq: 1,
      offset_ms: 20.0,
      status_code: 200,
      duration_ms: 45.0,
      is_fault_active: false,
      is_fallback: false,
      breaker_state: 'CLOSED',
    },
    {
      seq: 2,
      offset_ms: 85.0,
      status_code: 200,
      duration_ms: 12.0,
      is_fault_active: true,
      is_fallback: true,
      breaker_state: 'OPEN',
    },
  ],
  verdict_summary: '断路器极速跳闸响应（85ms ≤ 150ms），自愈时长 420ms，系统韧性达到 EXCELLENT 卓越水准！',
  remediation_suggestions: ['继续保持当前熔断窗口滑动比例配置。'],
  evaluated_at: '2026-10-16T12:00:00Z',
}

const mockFragileReport = {
  report_id: 'rto_test_102',
  target_service_id: 'order-service',
  endpoint: 'POST /api/v1/orders/checkout',
  resilience_tier: 'FRAGILE',
  breaker_trip_latency_ms: 1800.0,
  fallback_success_ratio_pct: 45.0,
  rto_recovery_duration_ms: 6200.0,
  total_samples_analyzed: 10,
  fault_period_requests_count: 5,
  recovery_period_requests_count: 5,
  sample_stream: [],
  verdict_summary: '断路器跳闸严重滞后引发雪崩，降级率极低，系统韧性评定为 FRAGILE 脆弱！',
  remediation_suggestions: ['必须调低断路器慢调用比例阈值，补充兜底降级响应缓存。'],
  evaluated_at: '2026-10-16T12:05:00Z',
}

vi.mock('@/api/trafficGateway', () => ({
  resilienceRtoApi: {
    simulate: vi.fn(),
    analyze: vi.fn(),
    listReports: vi.fn(),
    getReport: vi.fn(),
    clearReports: vi.fn(),
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
  ClockCircleOutlined: { template: '<span>ClockCircle</span>' },
  SafetyCertificateOutlined: { template: '<span>SafetyCertificate</span>' },
  CheckCircleOutlined: { template: '<span>CheckCircle</span>' },
}))

describe('ResilienceRtoRecoveryDashboardCard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(resilienceRtoApi.simulate).mockResolvedValue({
      message: '断路器仿真演练评估完成',
      report: mockExcellentReport as any,
    })
  })

  it('renders verdict banner, KPI metrics, stage bar, and sample points table', async () => {
    const wrapper = mount(ResilienceRtoRecoveryDashboardCard, {
      global: {
        stubs: {
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.seq" class="row">
                  <span class="seq">{{ item.seq }}</span>
                  <span class="breaker-state">{{ item.breaker_state }}</span>
                </div>
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()

    // 检查调用与标题
    expect(resilienceRtoApi.simulate).toHaveBeenCalled()
    expect(wrapper.text()).toContain('服务断路器生效时延与 RTO 自愈量化评估看板')

    // 检查裁决大横幅
    expect(wrapper.text()).toContain('EXCELLENT RESILIENCE')
    expect(wrapper.text()).toContain('断路器极速跳闸响应')

    // 检查 3 大 KPI
    expect(wrapper.text()).toContain('断路器跳闸生效时延')
    expect(wrapper.text()).toContain('85 ms')
    expect(wrapper.text()).toContain('故障期降级成功率')
    expect(wrapper.text()).toContain('99.2%')
    expect(wrapper.text()).toContain('RTO 自愈恢复时长')
    expect(wrapper.text()).toContain('420 ms')

    // 检查阶段条与表格
    expect(wrapper.text()).toContain('正常常态 (CLOSED)')
    expect(wrapper.text()).toContain('故障熔断跳闸 (OPEN - 快速降级)')
    expect(wrapper.text()).toContain('自愈探测阶段 (HALF_OPEN)')
  })

  it('switches tier preset to FRAGILE and updates report', async () => {
    vi.mocked(resilienceRtoApi.simulate).mockResolvedValueOnce({
      message: '断路器仿真演练评估完成',
      report: mockExcellentReport as any,
    }).mockResolvedValueOnce({
      message: '断路器仿真演练评估完成',
      report: mockFragileReport as any,
    })

    const wrapper = mount(ResilienceRtoRecoveryDashboardCard, {
      global: {
        stubs: {
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.applyTierPreset('FRAGILE')
    await flushPromises()

    expect(resilienceRtoApi.simulate).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('FRAGILE RESILIENCE')
    expect(wrapper.text()).toContain('1800 ms')
    expect(wrapper.text()).toContain('6200 ms')
  })
})
