import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import QualityHealthCompositeScoreCard from './QualityHealthCompositeScoreCard.vue'
import { qualityHealthScoreApi } from '@/api/cloudNativeCluster'

const mockReportAPlus = {
  report_id: 'health_v430_1001',
  target_name: 'release-v4.3.0',
  composite_score: 93.5,
  grade: 'A+' as const,
  dimension_scores: {
    test_execution: 100.0,
    code_coverage: 92.0,
    mutation_score: 88.0,
    defect_density: 100.0,
    change_risk: 95.0,
    env_compliance: 100.0,
  },
  dimension_weights: {
    test_execution: 0.25,
    code_coverage: 0.2,
    mutation_score: 0.15,
    defect_density: 0.2,
    change_risk: 0.1,
    env_compliance: 0.1,
  },
  primary_risk_factors: ['系统各项核心质量指标均表现卓越，无显著扣分项。'],
  optimization_recommendations: ['保持当前高水平的测试覆盖率与自动化防护体系。'],
  created_at: '2026-10-17T12:00:00Z',
}

const mockReportP0Veto = {
  report_id: 'health_p0_1002',
  target_name: 'release-with-p0',
  composite_score: 65.0,
  grade: 'C' as const,
  dimension_scores: {
    test_execution: 100.0,
    code_coverage: 95.0,
    mutation_score: 90.0,
    defect_density: 70.0,
    change_risk: 95.0,
    env_compliance: 100.0,
  },
  dimension_weights: {},
  primary_risk_factors: ['存在 1 个未修复的 P0 核心阻塞级缺陷，触发一票否决限制'],
  optimization_recommendations: ['优先闭环修复未完成的 P0 核心阻塞缺陷。'],
  created_at: '2026-10-17T12:05:00Z',
}

vi.mock('@/api/cloudNativeCluster', () => ({
  qualityHealthScoreApi: {
    calculate: vi.fn(),
    listReports: vi.fn(),
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
  DashboardOutlined: { template: '<span>Dashboard</span>' },
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
  BarChartOutlined: { template: '<span>BarChart</span>' },
  FileTextOutlined: { template: '<span>FileText</span>' },
}))

describe('QualityHealthCompositeScoreCard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(qualityHealthScoreApi.calculate).mockResolvedValue({
      message: '计算完成',
      report: mockReportAPlus as any,
    })
  })

  it('renders header, 4 KPI cards, 6-dimension scores, and recommendations', async () => {
    const wrapper = mount(QualityHealthCompositeScoreCard, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-progress': { template: '<div class="ant-progress" />' },
          'a-alert': { props: ['message', 'description'], template: '<div class="ant-alert"><span>{{ message }}</span><span>{{ description }}</span><slot /></div>' },
        },
      },
    })

    await flushPromises()

    expect(qualityHealthScoreApi.calculate).toHaveBeenCalled()

    // 检查标题与 KPI
    expect(wrapper.text()).toContain('多维质量健康加权融合模型与 P0 缺陷一票否决引擎')
    expect(wrapper.text()).toContain('93.5')
    expect(wrapper.text()).toContain('A+')
    expect(wrapper.text()).toContain('未触发')

    // 切换到 P0 否决预设
    vi.mocked(qualityHealthScoreApi.calculate).mockResolvedValueOnce({
      message: '计算完成',
      report: mockReportP0Veto as any,
    })

    const vm = wrapper.vm as any
    vm.selectedPreset = 'p0_veto'
    await vm.handlePresetChange()
    await flushPromises()

    expect(qualityHealthScoreApi.calculate).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('65')
    expect(wrapper.text()).toContain('C')
    expect(wrapper.text()).toContain('触发否决')
  })
})
