import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import QualityMetricsDashboardView from './QualityMetricsDashboardView.vue'
import { qualityGovernanceApi } from '@/api/qualityGovernance'

const mockQualityReport = {
  project_id: 1,
  generated_at: '2026-10-16T12:00:00Z',
  dimensions: {
    coverage: {
      score: 85.0,
      weight: 0.3,
      metrics: {
        automated_cases: 85,
        total_cases: 100,
        coverage_pct: 85.0,
      },
    },
    defect_escape: {
      score: 100.0,
      weight: 0.2,
      metrics: {
        internal_defects: 40,
        prod_escapes: 0,
        escape_rate_pct: 0.0,
      },
    },
    execution_stability: {
      score: 96.0,
      weight: 0.25,
      metrics: {
        total_runs: 50,
        flaky_runs: 2,
        flaky_ratio_pct: 4.0,
      },
    },
    mttr: {
      score: 88.0,
      weight: 0.25,
      metrics: {
        mttr_hours: 3.5,
      },
    },
  },
  composite_health_score: 91.5,
  grade: 'A' as const,
  release_readiness: 'APPROVED' as const,
  actionable_recommendations: [
    '用例自动化覆盖率为 85.0%，建议针对未覆盖分支补齐自动化用例。',
    '测试执行存在 2 次 Flaky 波动，建议对不稳定用例进行重试隔离。',
  ],
}

vi.mock('@/api/qualityGovernance', () => ({
  qualityGovernanceApi: {
    getProjectMetrics: vi.fn(),
    evaluateCustomMetrics: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('vue-echarts', () => ({
  default: {
    name: 'VChart',
    template: '<div class="echarts-radar-mock" />',
    props: ['option'],
  },
}))

describe('QualityMetricsDashboardView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders page header, composite health score, grade, and verdict on mount', async () => {
    vi.mocked(qualityGovernanceApi.getProjectMetrics).mockResolvedValue(mockQualityReport)

    const wrapper = mount(QualityMetricsDashboardView, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card">{{ title }}<slot name="title" /><slot /></div>', props: ['title'] },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input-number': { template: '<input />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-row': { template: '<div class="ant-row"><slot /></div>' },
          'a-col': { template: '<div class="ant-col"><slot /></div>' },
          'a-modal': { template: '<div class="ant-modal"><slot /></div>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('全生命周期软件测试质量度量大盘')
    expect(wrapper.text()).toContain('91.5') // 综合健康评分
    expect(wrapper.text()).toContain('A') // Grade A
    expect(wrapper.text()).toContain('准予发版 (APPROVED)')
  })

  it('renders 4 dimension metric cards with scores and metrics', async () => {
    vi.mocked(qualityGovernanceApi.getProjectMetrics).mockResolvedValue(mockQualityReport)

    const wrapper = mount(QualityMetricsDashboardView, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card">{{ title }}<slot name="title" /><slot /></div>', props: ['title'] },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input-number': { template: '<input />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-row': { template: '<div class="ant-row"><slot /></div>' },
          'a-col': { template: '<div class="ant-col"><slot /></div>' },
          'a-modal': { template: '<div />' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('自动化覆盖率 (Coverage)')
    expect(wrapper.text()).toContain('85') // coverage score
    expect(wrapper.text()).toContain('缺陷逃逸 (Defect Escape)')
    expect(wrapper.text()).toContain('100') // defect escape score
    expect(wrapper.text()).toContain('执行稳定性 (Stability)')
    expect(wrapper.text()).toContain('96') // stability score
    expect(wrapper.text()).toContain('修复时效 (MTTR)')
    expect(wrapper.text()).toContain('3.5 小时')
  })

  it('renders actionable engineering recommendations', async () => {
    vi.mocked(qualityGovernanceApi.getProjectMetrics).mockResolvedValue(mockQualityReport)

    const wrapper = mount(QualityMetricsDashboardView, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card">{{ title }}<slot name="title" /><slot /></div>', props: ['title'] },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input-number': { template: '<input />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-row': { template: '<div class="ant-row"><slot /></div>' },
          'a-col': { template: '<div class="ant-col"><slot /></div>' },
          'a-modal': { template: '<div />' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('全生命周期质量改进建议 (Actionable Insights)')
    expect(wrapper.text()).toContain('用例自动化覆盖率为 85.0%')
    expect(wrapper.text()).toContain('测试执行存在 2 次 Flaky 波动')
  })

  it('evaluates custom metrics in simulation modal', async () => {
    vi.mocked(qualityGovernanceApi.getProjectMetrics).mockResolvedValue(mockQualityReport)
    vi.mocked(qualityGovernanceApi.evaluateCustomMetrics).mockResolvedValue({
      ...mockQualityReport,
      composite_health_score: 95.0,
      grade: 'A',
    })

    const wrapper = mount(QualityMetricsDashboardView, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card">{{ title }}<slot name="title" /><slot /></div>', props: ['title'] },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input-number': { template: '<input />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-row': { template: '<div class="ant-row"><slot /></div>' },
          'a-col': { template: '<div class="ant-col"><slot /></div>' },
          'a-modal': { template: '<div class="ant-modal"><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
        },
      },
    })

    await flushPromises()

    const simBtn = wrapper.findAll('button').find((b) => b.text().includes('即刻执行推演计算'))
    expect(simBtn).toBeDefined()
    await simBtn!.trigger('click')
    await flushPromises()

    expect(qualityGovernanceApi.evaluateCustomMetrics).toHaveBeenCalled()
    expect(wrapper.text()).toContain('95')
  })
})
