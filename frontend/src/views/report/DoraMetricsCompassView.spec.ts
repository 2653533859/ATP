import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import DoraMetricsCompassView from './DoraMetricsCompassView.vue'
import { doraMetricsApi } from '@/api/doraMetrics'

const mockDoraReport = {
  report_id: 'dora_rep_123456',
  project_id: 1,
  evaluation_period_days: 30,
  overall_maturity_level: 'elite',
  dimensions: {
    deployment_frequency: {
      dimension_name: '部署频率',
      value: 2.0,
      unit: '次/天',
      level: 'elite',
      description: '每天多次或日均 ≥ 1 次按需部署',
      benchmark_guideline: '日均部署 ≥ 1.0 次 (持续集成卓越标准)',
    },
    lead_time_for_changes: {
      dimension_name: '变更前置时间',
      value: 0.8,
      unit: '小时',
      level: 'elite',
      description: '变更前置耗时 ≤ 1 小时 (极速交付)',
      benchmark_guideline: '代码 Commit 到测试验收通过 ≤ 1.0 小时',
    },
    change_failure_rate: {
      dimension_name: '变更失败率',
      value: 4.2,
      unit: '%',
      level: 'elite',
      description: '变更失败率 ≤ 5% (高可靠发布)',
      benchmark_guideline: '变更缺陷与回滚率 ≤ 5.0%',
    },
    time_to_restore_service: {
      dimension_name: '服务恢复时限',
      value: 35.0,
      unit: '分钟',
      level: 'elite',
      description: '平均故障恢复时长 ≤ 1 小时 (瞬时熔断自愈)',
      benchmark_guideline: '线上或回归阻断平均修复时长 MTTR ≤ 60 分钟',
    },
  },
  test_on_time_completion_rate_pct: 95.0,
  bottlenecks_identified: [],
  engineering_efficiency_recommendations: [
    '保持高频日构建与提交前准入校验，进一步缩短 PR Code Review 等待周期',
    '将回归自动化用例前置至流水线 PR Trigger，维持零逃逸率',
  ],
  evaluated_at: '2026-10-16T10:00:00Z',
}

vi.mock('@/api/doraMetrics', () => ({
  doraMetricsApi: {
    listReports: vi.fn(),
    getReport: vi.fn(),
    evaluate: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('@ant-design/icons-vue', () => ({
  CompassOutlined: { template: '<span>Compass</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  SlidersOutlined: { template: '<span>Sliders</span>' },
  AlertFilled: { template: '<span>Alert</span>' },
  CheckCircleFilled: { template: '<span>Check</span>' },
}))

vi.mock('@/utils/chartTheme', () => ({
  useChartTheme: () => ({ chartTheme: 'atp-light' }),
}))

vi.mock('vue-echarts', () => ({
  default: {
    name: 'VChart',
    props: ['option'],
    template: '<div class="v-chart-dora-radar-stub" />',
  },
}))

describe('DoraMetricsCompassView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(doraMetricsApi.listReports).mockResolvedValue({
      total: 1,
      reports: [mockDoraReport as any],
    })
    vi.mocked(doraMetricsApi.evaluate).mockResolvedValue({
      message: 'DORA 效能评估计算完成',
      report: mockDoraReport as any,
    })
  })

  it('renders overall maturity banner, four DORA metrics, and recommendations', async () => {
    const wrapper = mount(DoraMetricsCompassView, {
      global: {
        stubs: {
          'a-spin': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
        },
      },
    })

    await flushPromises()

    // 验证页面标题与成熟度 Banner
    expect(wrapper.text()).toContain('团队研发效能 DORA 罗盘看板与成熟度评估')
    expect(wrapper.text()).toContain('ELITE')
    expect(wrapper.text()).toContain('95%')
    expect(wrapper.text()).toContain('测试执行准时交付率')

    // 验证四维指标
    expect(wrapper.text()).toContain('部署频率')
    expect(wrapper.text()).toContain('2')
    expect(wrapper.text()).toContain('变更前置时间')
    expect(wrapper.text()).toContain('0.8')
    expect(wrapper.text()).toContain('变更失败率')
    expect(wrapper.text()).toContain('4.2')
    expect(wrapper.text()).toContain('服务恢复时限')
    expect(wrapper.text()).toContain('35')

    // 验证效能建议
    expect(wrapper.text()).toContain('保持高频日构建与提交前准入校验')

    expect(doraMetricsApi.listReports).toHaveBeenCalled()
  })

  it('triggers simulation evaluate and updates DORA report', async () => {
    const wrapper = mount(DoraMetricsCompassView, {
      global: {
        stubs: {
          'a-spin': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.handleRunEvaluate()

    expect(doraMetricsApi.evaluate).toHaveBeenCalledWith(expect.objectContaining({
      evaluation_period_days: 30,
      total_deployments_count: expect.any(Number),
    }))
  })
})
