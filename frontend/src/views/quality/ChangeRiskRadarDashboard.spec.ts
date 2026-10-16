import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ChangeRiskRadarDashboard from './ChangeRiskRadarDashboard.vue'
import { ciImpactApi } from '@/api/ciImpact'

const mockReport = {
  risk_id: 'risk_demo_123',
  overall_risk_score: 78.5,
  risk_level: 'CRITICAL',
  dimensions: {
    volume: {
      dimension_name: '变更代码规模',
      score: 70.0,
      weight: 0.30,
      raw_metrics: {
        total_added_lines: 120,
        total_deleted_lines: 30,
        changed_files_count: 3,
      },
      description: '变更体量较大 (共 150 行)',
    },
    complexity: {
      dimension_name: '圈复杂度增量',
      score: 80.0,
      weight: 0.35,
      raw_metrics: {
        complexity_delta_count: 9,
      },
      description: '引入大量控制分支与异常逻辑',
    },
    criticality: {
      dimension_name: '核心资产敏感度',
      score: 85.0,
      weight: 0.35,
      raw_metrics: {
        high_risk_files_count: 1,
      },
      description: '触及核心认证鉴权模块',
    },
  },
  high_risk_files: ['backend/app/core/auth_security.py'],
  risk_factors_summary: ['触及涉敏核心代码模块 (1 个文件)', '控制分支复杂度显著上升 (+9)'],
  recommended_action: '阻断直接合流：必须执行全量回归用例并要求至少 2 位核心研发专家双人评审',
  evaluated_at: '2026-10-16T10:00:00Z',
}

vi.mock('@/api/ciImpact', () => ({
  ciImpactApi: {
    listRiskReports: vi.fn(),
    getRiskReport: vi.fn(),
    evaluateRisk: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('@ant-design/icons-vue', () => ({
  RadarChartOutlined: { template: '<span>Radar</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  SlidersOutlined: { template: '<span>Sliders</span>' },
  AlertOutlined: { template: '<span>Alert</span>' },
  CheckCircleOutlined: { template: '<span>Check</span>' },
}))

vi.mock('@/utils/chartTheme', () => ({
  useChartTheme: () => ({ chartTheme: 'atp-light' }),
}))

vi.mock('vue-echarts', () => ({
  default: {
    name: 'VChart',
    props: ['option'],
    template: '<div class="v-chart-radar-stub" />',
  },
}))

describe('ChangeRiskRadarDashboard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(ciImpactApi.listRiskReports).mockResolvedValue({
      total: 1,
      reports: [mockReport as any],
    })
    vi.mocked(ciImpactApi.evaluateRisk).mockResolvedValue({
      message: '代码变更风险评估完成',
      report: mockReport as any,
    })
  })

  it('renders overall risk score, CRITICAL level banner, and 3 dimension cards', async () => {
    const wrapper = mount(ChangeRiskRadarDashboard, {
      global: {
        stubs: {
          'a-spin': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot /></div>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-textarea': { template: '<textarea />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
        },
      },
    })

    await flushPromises()

    // 验证页面标题与总得分
    expect(wrapper.text()).toContain('代码变更三维风险雷达大盘与准入指导')
    expect(wrapper.text()).toContain('78.5')
    expect(wrapper.text()).toContain('CRITICAL 风险等级')
    expect(wrapper.text()).toContain('阻断直接合流')

    // 验证三维指标
    expect(wrapper.text()).toContain('变更代码规模 (Volume)')
    expect(wrapper.text()).toContain('70')
    expect(wrapper.text()).toContain('圈复杂度增量 (Complexity)')
    expect(wrapper.text()).toContain('80')
    expect(wrapper.text()).toContain('核心资产涉敏度 (Criticality)')
    expect(wrapper.text()).toContain('85')

    // 验证高危文件与因子
    expect(wrapper.text()).toContain('backend/app/core/auth_security.py')
    expect(wrapper.text()).toContain('触及涉敏核心代码模块')

    expect(ciImpactApi.listRiskReports).toHaveBeenCalled()
  })

  it('triggers evaluate risk on preset click', async () => {
    const wrapper = mount(ChangeRiskRadarDashboard, {
      global: {
        stubs: {
          'a-spin': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot /></div>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-textarea': { template: '<textarea />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.applyPreset('low')

    expect(ciImpactApi.evaluateRisk).toHaveBeenCalledWith(expect.objectContaining({
      weight_volume: 0.3,
      weight_complexity: 0.35,
      weight_criticality: 0.35,
    }))
  })
})
