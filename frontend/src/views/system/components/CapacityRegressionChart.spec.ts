import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CapacityRegressionChart from './CapacityRegressionChart.vue'

const mockForecastCapacity = vi.fn().mockResolvedValue({
  status: 'ready',
  sample_count: 3,
  sla_criteria: { max_p95_ms: 400.0, max_error_rate: 0.01 },
  regression_models: {
    rps_linear: { slope: 8.0, intercept: 200.0, r_squared: 0.99, valid: true },
    p95_polynomial: { a: 0.0005, b: 0.08, c: 40.0, r_squared: 0.99, valid: true, model_type: 'polynomial_deg2' },
    confidence: 'High',
    avg_r_squared: 0.99,
  },
  capacity_limit: {
    max_safe_concurrency: 850.0,
    predicted_max_rps: 7000.0,
    knee_point: { concurrency: 600, rps: 5000 },
  },
  recommendation: '容量预测良好',
  comparison: {
    total_runs: 3,
    valid_points_count: 3,
    comparison_matrix: [
      { run_id: 201, concurrency: 100, rps: 1000, p95_ms: 50, error_rate: 0.0, scaling_efficiency: 10.0 },
      { run_id: 202, concurrency: 200, rps: 2000, p95_ms: 70, error_rate: 0.0, scaling_efficiency: 10.0 },
      { run_id: 203, concurrency: 400, rps: 3800, p95_ms: 150, error_rate: 0.002, scaling_efficiency: 9.5 },
    ],
  },
})

vi.mock('@/api', () => ({
  performanceApi: {
    forecastCapacity: (body: unknown) => mockForecastCapacity(body),
    compareRuns: vi.fn(),
  },
}))

vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', template: '<div class="echarts-stub" />' },
}))

describe('CapacityRegressionChart', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders initial sample capacity forecast and comparison matrix', async () => {
    const wrapper = mount(CapacityRegressionChart, {
      global: {
        stubs: {
          'a-input': true,
          'a-input-number': true,
          'a-button': { template: '<button><slot /></button>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span><slot /></span>' },
          'a-table': { template: '<table><slot /></table>' },
        },
      },
    })

    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('多维性能对比、回归容量预测与拐点识别')
    expect(wrapper.text()).toContain('792')
    expect(wrapper.text()).toContain('6450')
    expect(wrapper.text()).toContain('置信度 High')

    const vm = wrapper.vm as unknown as {
      forecastData: { capacity_limit?: { max_safe_concurrency: number } } | null
      comparisonRows: Array<{ concurrency: number; rps: number }>
    }

    expect(vm.forecastData?.capacity_limit?.max_safe_concurrency).toBe(792)
    expect(vm.comparisonRows.length).toBe(4)
  })

  it('triggers capacity forecast calculation on button click', async () => {
    const wrapper = mount(CapacityRegressionChart, {
      global: {
        stubs: {
          'a-input': true,
          'a-input-number': true,
          'a-button': { template: '<button><slot /></button>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span><slot /></span>' },
          'a-table': true,
        },
      },
    })

    const vm = wrapper.vm as unknown as {
      runIdsInput: string
      runForecast: () => Promise<void>
      forecastData: { capacity_limit?: { max_safe_concurrency: number } } | null
    }

    vm.runIdsInput = '201, 202, 203'
    await vm.runForecast()

    expect(mockForecastCapacity).toHaveBeenCalledWith(
      expect.objectContaining({ run_ids: [201, 202, 203] }),
    )
    expect(vm.forecastData?.capacity_limit?.max_safe_concurrency).toBe(850)
  })
})
