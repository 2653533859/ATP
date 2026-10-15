import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import MeshResilienceReportView from './MeshResilienceReportView.vue'

const mockReport = {
  report_id: 'rpt_mesh_test_881',
  experiment_id: 'exp_mesh_resilience_01',
  generated_at: '2026-10-16T10:00:00Z',
  summary: {
    resilience_score: 92.5,
    resilience_grade: 'A',
    total_services_evaluated: 4,
    lowest_sla_service: 'pay-service',
    lowest_sla_percent: 93.67,
    blast_radius_breached: false,
    emergency_aborted: false,
    recommendation: '服务网格展现卓越的高可用自愈韧性（Grade A），具备秒级故障隔离与自愈恢复能力。',
  },
  services: [
    {
      service_name: 'api-gateway',
      total_requests: 2500,
      failed_requests: 5,
      availability_sla_pct: 99.8,
      sla_baseline_target: 99.9,
      sla_drop_pct: 0.1,
      avg_latency_ms: 35.0,
      p95_latency_ms: 80.0,
      recovery_time_seconds: 1.2,
      degradation_status: 'healthy',
    },
    {
      service_name: 'order-service',
      total_requests: 2000,
      failed_requests: 12,
      availability_sla_pct: 99.4,
      sla_baseline_target: 99.9,
      sla_drop_pct: 0.5,
      avg_latency_ms: 45.0,
      p95_latency_ms: 110.0,
      recovery_time_seconds: 2.5,
      degradation_status: 'minor_degraded',
    },
    {
      service_name: 'pay-service',
      total_requests: 1500,
      failed_requests: 95,
      availability_sla_pct: 93.67,
      sla_baseline_target: 99.9,
      sla_drop_pct: 6.23,
      avg_latency_ms: 120.0,
      p95_latency_ms: 380.0,
      recovery_time_seconds: 6.8,
      degradation_status: 'severely_degraded',
    },
    {
      service_name: 'inventory-service',
      total_requests: 1800,
      failed_requests: 2,
      availability_sla_pct: 99.89,
      sla_baseline_target: 99.9,
      sla_drop_pct: 0.01,
      avg_latency_ms: 30.0,
      p95_latency_ms: 65.0,
      recovery_time_seconds: 1.0,
      degradation_status: 'healthy',
    },
  ],
}

const mockCompileResilienceReport = vi.fn().mockResolvedValue(mockReport)

vi.mock('@/api/meshChaos', () => ({
  meshChaosApi: {
    compileResilienceReport: (data: unknown) => mockCompileResilienceReport(data),
    listExperiments: vi.fn(),
    createExperiment: vi.fn(),
    getExperiment: vi.fn(),
    setExperimentStatus: vi.fn(),
    evaluateMeshRequest: vi.fn(),
    getTopology: vi.fn(),
    evaluateBlastRadius: vi.fn(),
    enforceBlastRadius: vi.fn(),
  },
}))

const globalStubs = {
  'a-card': { template: '<div class="ant-card"><h4>{{ $attrs.title }}</h4><slot /><slot name="extra" /></div>' },
  'a-button': { template: '<button class="ant-btn"><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
  'a-space': { template: '<div><slot /></div>' },
  'a-input': { template: '<input />' },
  'a-select': { template: '<select><slot /></select>' },
  'a-select-option': { template: '<option><slot /></option>' },
  'a-alert': { template: '<div class="ant-alert">{{ $attrs.message }}</div>' },
  'a-empty': { template: '<div class="ant-empty">{{ $attrs.description }}</div>' },
  'a-table': {
    props: ['dataSource'],
    template: `
      <div class="ant-table">
        <div v-for="item in dataSource" :key="item.service_name" class="table-row">
          <span class="row-svc">{{ item.service_name }}</span>
          <span class="row-sla">{{ item.availability_sla_pct }}%</span>
          <span class="row-rto">{{ item.recovery_time_seconds }} 秒自愈</span>
        </div>
      </div>
    `,
  },
}

describe('MeshResilienceReportView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('compiles and renders resilience score, grade, and weakest link', async () => {
    const wrapper = mount(MeshResilienceReportView, {
      global: {
        stubs: globalStubs,
      },
    })
    await flushPromises()

    expect(mockCompileResilienceReport).toHaveBeenCalled()
    expect(wrapper.text()).toContain('全链路微服务高可用 SLA 韧性评分报告')
    expect(wrapper.text()).toContain('92.5')
    expect(wrapper.text()).toContain('Grade A')
    expect(wrapper.text()).toContain('pay-service')
    expect(wrapper.text()).toContain('93.67%')
    expect(wrapper.text()).toContain('服务网格展现卓越的高可用自愈韧性')
  })

  it('renders four dimension weighted metrics and services table', async () => {
    const wrapper = mount(MeshResilienceReportView, {
      global: {
        stubs: globalStubs,
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('可用性 SLA 达成度 (40% 权重)')
    expect(wrapper.text()).toContain('故障自愈 RTO 时效 (30% 权重)')
    expect(wrapper.text()).toContain('爆炸半径约束控制力 (20% 权重)')
    expect(wrapper.text()).toContain('峰值错误容忍度 (10% 权重)')

    // Check table services
    expect(wrapper.text()).toContain('api-gateway')
    expect(wrapper.text()).toContain('order-service')
    expect(wrapper.text()).toContain('pay-service')
    expect(wrapper.text()).toContain('inventory-service')
    expect(wrapper.text()).toContain('99.8%')
    expect(wrapper.text()).toContain('1.2 秒自愈')
  })

  it('triggers compile report button with custom parameters', async () => {
    const wrapper = mount(MeshResilienceReportView, {
      global: {
        stubs: globalStubs,
      },
    })
    await flushPromises()

    const btn = wrapper.findAll('button').find((b) => b.text().includes('生成韧性报告'))
    expect(btn).toBeDefined()
    await btn!.trigger('click')
    await flushPromises()

    expect(mockCompileResilienceReport).toHaveBeenCalledTimes(2)
  })
})
