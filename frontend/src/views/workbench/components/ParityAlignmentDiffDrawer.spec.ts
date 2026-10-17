import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ParityAlignmentDiffDrawer from './ParityAlignmentDiffDrawer.vue'
import { crossPlatformMigrationApi } from '@/api/crossPlatformMigration'

const mockReport = {
  report_id: 'parrep_test_001',
  screen_name: '收银台结算中心',
  source_platform: 'ios',
  target_platform: 'android',
  composite_score: 82.5,
  grade: 'GRADE_B' as const,
  verdict: 'WARN' as const,
  scores: {
    control_alignment_score: 75.0,
    core_business_score: 85.0,
    text_consistency_score: 90.0,
    interaction_compatibility_score: 100.0,
    weighted_composite_score: 82.5,
  },
  matrix_summary: {
    total_source_nodes: 4,
    total_target_nodes: 4,
    aligned_pairs_count: 3,
    alignment_rate: 0.75,
  },
  discrepancy_summary: {
    total_gaps_count: 2,
    critical_count: 0,
    high_count: 1,
    medium_count: 1,
    low_count: 0,
  },
  gaps: [
    {
      gap_id: 'gap_1',
      gap_type: 'MISSING_CORE_CONTROL' as const,
      severity: 'HIGH' as const,
      title: '目标端 Android 缺失 Apple Pay 快捷付款入口',
      description: '源端 iOS 包含 Apple Pay 支付选项，目标端未找到对应聚合快捷入口。',
      suggested_fix: '在 Android 端适配接入对应的快捷闪付或微信/支付宝免密入口。',
      detected_at: '2026-10-17 12:00:00',
    },
    {
      gap_id: 'gap_2',
      gap_type: 'SEMANTIC_TEXT_DRIFT' as const,
      severity: 'MEDIUM' as const,
      title: '双端优惠券满减文案存在漂移',
      description: 'iOS 显示满100减20，Android 显示满200减10，优惠规则配置不同步。',
      suggested_fix: '核对营销中心配置，保持双端优惠券门槛与文案对称。',
      detected_at: '2026-10-17 12:00:00',
    },
  ],
  executive_summary:
    '【带险放行】双端一致性综合评分为 82.5 分 (评级: GRADE_B)。存在 1 项高危差异（支付方式缺失），建议完成对应端适配后上线。',
  generated_at: '2026-10-17 12:00:00',
}

const stubs = {
  'a-drawer': { template: '<div class="ant-drawer-stub"><slot /></div>' },
  'a-button': { template: '<button><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-space': { template: '<div class="ant-space-stub"><slot /></div>' },
  'a-tabs': { template: '<div class="ant-tabs-stub"><slot /></div>' },
  'a-tab-pane': { template: '<div class="ant-tab-pane-stub"><slot /></div>' },
  'a-empty': { template: '<div class="ant-empty-stub" />' },
}

describe('ParityAlignmentDiffDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(crossPlatformMigrationApi, 'getParityReport').mockResolvedValue({
      report: mockReport,
    })
    vi.spyOn(crossPlatformMigrationApi, 'analyzeParity').mockResolvedValue({
      message: '分析成功',
      report: mockReport,
    })
  })

  it('renders drawer header, composite score, grade, and verdict when open', async () => {
    const wrapper = mount(ParityAlignmentDiffDrawer, {
      props: {
        open: true,
        reportId: 'parrep_test_001',
      },
      global: { stubs },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('收银台结算中心')
    expect(wrapper.text()).toContain('82.5')
    expect(wrapper.text()).toContain('GRADE_B')
    expect(wrapper.text()).toContain('门禁: WARN')
  })

  it('renders side-by-side tree diff items in tree tab', async () => {
    const wrapper = mount(ParityAlignmentDiffDrawer, {
      props: {
        open: true,
        reportId: 'parrep_test_001',
      },
      global: { stubs },
    })
    await flushPromises()

    // 查验源端与目标端控件
    expect(wrapper.text()).toContain('立即支付')
    expect(wrapper.text()).toContain('Apple Pay 快捷付款')
    expect(wrapper.text()).toContain('目标端缺失')
    expect(wrapper.text()).toContain('确认付款 (微信/支付宝)')
    expect(wrapper.text()).toContain('源端未覆盖')
  })

  it('renders discrepancy gap cards in gaps tab', async () => {
    const wrapper = mount(ParityAlignmentDiffDrawer, {
      props: {
        open: true,
        reportId: 'parrep_test_001',
      },
      global: { stubs },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('目标端 Android 缺失 Apple Pay 快捷付款入口')
    expect(wrapper.text()).toContain('MISSING_CORE_CONTROL')
    expect(wrapper.text()).toContain('双端优惠券满减文案存在漂移')
    expect(wrapper.text()).toContain('SEMANTIC_TEXT_DRIFT')
  })

  it('renders 4 score breakdown cards and executive summary in scores tab', async () => {
    const wrapper = mount(ParityAlignmentDiffDrawer, {
      props: {
        open: true,
        reportId: 'parrep_test_001',
      },
      global: { stubs },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('控件对齐率得分')
    expect(wrapper.text()).toContain('75.0 分')
    expect(wrapper.text()).toContain('核心业务覆盖得分')
    expect(wrapper.text()).toContain('85.0 分')
    expect(wrapper.text()).toContain('高管决策层准入建议综述')
    expect(wrapper.text()).toContain('【带险放行】双端一致性综合评分为 82.5 分')
  })
})
