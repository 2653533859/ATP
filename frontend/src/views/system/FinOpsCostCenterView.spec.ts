import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import FinOpsCostCenterView from './FinOpsCostCenterView.vue'

const mockGetCostReport = vi.fn().mockResolvedValue({
  period_start: '2026-09-16T00:00:00Z',
  period_end: '2026-10-16T00:00:00Z',
  currency: 'CNY',
  rates: { cpu_hour_rate: 0.25, storage_gb_month_rate: 0.12 },
  total_projects: 2,
  total_platform_cost: 250.0,
  total_compute_cost: 180.0,
  total_storage_cost: 70.0,
  total_cpu_hours: 720.0,
  total_storage_gb: 583.33,
  highest_cost_project: '支付风控微服务',
  project_costs: [
    {
      project_id: 1,
      project_name: '支付风控微服务',
      total_runs: 120,
      total_execution_seconds: 180000.0,
      cpu_hours: 500.0,
      compute_cost: 125.0,
      storage_bytes: 429496729600,
      storage_gb: 400.0,
      storage_cost: 48.0,
      total_cost: 173.0,
      cost_share_pct: 69.2,
      optimization_tip: '存储成本占比显著偏高，建议开启自动归档策略。',
    },
    {
      project_id: 2,
      project_name: '移动端原生 APP',
      total_runs: 60,
      total_execution_seconds: 79200.0,
      cpu_hours: 220.0,
      compute_cost: 55.0,
      storage_bytes: 196884398080,
      storage_gb: 183.33,
      storage_cost: 22.0,
      total_cost: 77.0,
      cost_share_pct: 30.8,
      optimization_tip: '计算与存储配比健康。',
    },
  ],
})

const mockExportCsv = vi.fn().mockResolvedValue(new Blob(['test,csv'], { type: 'text/csv' }))

vi.mock('@/api/finops', () => ({
  finopsApi: {
    getCostReport: (params?: unknown) => mockGetCostReport(params),
    exportCostReportCsv: (params?: unknown) => mockExportCsv(params),
  },
}))

vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', template: '<div class="echarts-stub" />' },
}))

describe('FinOpsCostCenterView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.URL.createObjectURL = vi.fn().mockReturnValue('blob:mock-url')
    window.URL.revokeObjectURL = vi.fn()
  })

  it('loads FinOps cost report on mount and renders overview KPIs', async () => {
    const wrapper = mount(FinOpsCostCenterView, {
      global: {
        stubs: {
          'a-button': { template: '<button><slot /></button>' },
          'a-input-number': true,
          'a-card': { template: '<div><slot /></div>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-table': { template: '<table><slot /></table>' },
          'a-tag': { template: '<span><slot /></span>' },
        },
      },
    })

    await flushPromises()

    expect(mockGetCostReport).toHaveBeenCalled()
    expect(wrapper.text()).toContain('企业级 FinOps 资源成本中心与费用分摊')
    expect(wrapper.text()).toContain('250.00')
    expect(wrapper.text()).toContain('180.00')
    expect(wrapper.text()).toContain('70.00')
    expect(wrapper.text()).toContain('支付风控微服务')

    const vm = wrapper.vm as unknown as {
      reportData: { total_platform_cost: number } | null
    }

    expect(vm.reportData?.total_platform_cost).toBe(250.0)
  })

  it('triggers CSV bill export on button click', async () => {
    const wrapper = mount(FinOpsCostCenterView, {
      global: {
        stubs: {
          'a-button': { template: '<button><slot /></button>' },
          'a-input-number': true,
          'a-card': { template: '<div><slot /></div>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-table': true,
          'a-tag': true,
        },
      },
    })

    const vm = wrapper.vm as unknown as {
      handleExportCsv: () => Promise<void>
    }

    await vm.handleExportCsv()
    expect(mockExportCsv).toHaveBeenCalled()
    expect(window.URL.createObjectURL).toHaveBeenCalled()
  })

  it('re-evaluates costs when rates are adjusted', async () => {
    const wrapper = mount(FinOpsCostCenterView, {
      global: {
        stubs: {
          'a-button': { template: '<button><slot /></button>' },
          'a-input-number': true,
          'a-card': true,
          'a-row': true,
          'a-col': true,
          'a-table': true,
          'a-tag': true,
        },
      },
    })

    const vm = wrapper.vm as unknown as {
      queryRates: { cpu_hour_rate: number; storage_gb_month_rate: number }
      loadCostReport: () => Promise<void>
    }

    vm.queryRates.cpu_hour_rate = 0.50
    vm.queryRates.storage_gb_month_rate = 0.20
    await vm.loadCostReport()

    expect(mockGetCostReport).toHaveBeenCalledWith(
      expect.objectContaining({ cpu_hour_rate: 0.50, storage_gb_month_rate: 0.20 }),
    )
  })
})
