import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import VisualRegressionAuditDashboardView from './VisualRegressionAuditDashboardView.vue'
import * as visualApi from '@/api/visualRegressionA11y'

describe('VisualRegressionAuditDashboardView.vue (UI1.3)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(visualApi, 'listVisualDiffReports').mockResolvedValue({
      total: 3,
      reports: [
        {
          report_id: 'rpt_1',
          page_name: '/views/checkout',
          overall_verdict: 'PERFECT_MATCH',
          average_ssim_score: 0.995,
          max_mismatch_ratio_pct: 0.05,
          total_diff_clusters_count: 0,
          viewports: [],
          created_at: new Date().toISOString(),
        },
        {
          report_id: 'rpt_2',
          page_name: '/views/workbench/api',
          overall_verdict: 'REGRESSION_BLOCKED',
          average_ssim_score: 0.912,
          max_mismatch_ratio_pct: 3.2,
          total_diff_clusters_count: 5,
          viewports: [],
          created_at: new Date().toISOString(),
        },
      ],
    })
  })

  it('正确渲染全景大盘 Banner、四大 KPI 统计卡片与报告列表', async () => {
    const wrapper = mount(VisualRegressionAuditDashboardView, {
      global: {
        stubs: {
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot /></div>' },
          'a-table': { template: '<div class="ant-table"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-badge': { template: '<span><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input-search': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          VisualPixelDiffInspectorDrawer: { template: '<div class="diff-inspector-drawer-stub" />' },
          VisualGoldenBaselineEvolutionPanel: { template: '<div class="baseline-panel-stub" />' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('多模态视觉回归与黄金基线管理全景大盘')
    expect(wrapper.text()).toContain('视觉回归综合达标率')
    expect(wrapper.text()).toContain('活跃黄金基线数')
    expect(wrapper.text()).toContain('待审视视觉差异')
    expect(wrapper.text()).toContain('全站平均 SSIM 相似度')
    expect(wrapper.text()).toContain('99.4%')
  })

  it('点击刷新大盘按钮能正确请求报告列表并更新展示', async () => {
    const wrapper = mount(VisualRegressionAuditDashboardView, {
      global: {
        stubs: {
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot /></div>' },
          'a-table': { template: '<div class="ant-table"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-badge': { template: '<span><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input-search': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          VisualPixelDiffInspectorDrawer: { template: '<div class="diff-inspector-drawer-stub" />' },
          VisualGoldenBaselineEvolutionPanel: { template: '<div class="baseline-panel-stub" />' },
        },
      },
    })

    await flushPromises()

    const reloadBtn = wrapper.findAll('button').find(b => b.text().includes('刷新大盘'))
    expect(reloadBtn).toBeDefined()
    await reloadBtn?.trigger('click')
    await flushPromises()

    expect(visualApi.listVisualDiffReports).toHaveBeenCalled()
  })
})
