import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import DesignSystemTokenAuditDrawer from './DesignSystemTokenAuditDrawer.vue'
import * as visualApi from '@/api/visualRegressionA11y'

describe('DesignSystemTokenAuditDrawer.vue (UI2.3)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(visualApi, 'listDesignSystemReports').mockResolvedValue({
      total: 1,
      reports: [
        {
          report_id: 'token_rpt_001',
          target_name: '/views/checkout',
          total_elements_checked: 2,
          total_violations_count: 2,
          contrast_fails_count: 0,
          token_discrepancies_count: 2,
          compliance_score_pct: 95.0,
          is_wcag_aa_compliant: true,
          violations: [
            {
              violation_id: 'v_1',
              element_id: 'card_badge',
              violation_type: 'FONT_SIZE_OFF_GRID',
              severity: 'MEDIUM',
              current_value: '13.5px',
              recommended_token: '14px',
              explanation: '字号偏离标准字阶',
            },
          ],
          created_at: new Date().toISOString(),
        },
      ],
    })
    vi.spyOn(visualApi, 'computeContrastRatio').mockResolvedValue({
      foreground_hex: '#0F172A',
      background_hex: '#FFFFFF',
      contrast_ratio: 15.8,
      is_wcag_aa_pass: true,
      is_wcag_aaa_pass: true,
      rating: 'AAA',
    })
    vi.spyOn(visualApi, 'auditDesignTokens').mockResolvedValue({
      message: '审计完成',
      report: {
        report_id: 'token_rpt_002',
        target_name: '/views/checkout',
        total_elements_checked: 2,
        total_violations_count: 0,
        contrast_fails_count: 0,
        token_discrepancies_count: 0,
        compliance_score_pct: 100.0,
        is_wcag_aa_compliant: true,
        violations: [],
        created_at: new Date().toISOString(),
      },
    })
  })

  it('正确渲染标题 Banner、4 项核心 Token 规范 KPI 卡片及即时对比度计算器', async () => {
    const wrapper = mount(DesignSystemTokenAuditDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot /></div>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-input': { template: '<input />' },
          'a-table': { template: '<div class="ant-table"><slot /></div>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('企业级品牌设计系统 Token 合规与 WCAG 2.2 色彩对比度审查中心')
    expect(wrapper.text()).toContain('Token 规范符合度')
    expect(wrapper.text()).toContain('WCAG AA 对比度判定')
    expect(wrapper.text()).toContain('低对比度缺陷数')
    expect(wrapper.text()).toContain('Token 偏离网格数')
    expect(wrapper.text()).toContain('即时色彩对比度计算器')
  })

  it('点击计算对比度按钮能正确调用 API 并展示对比度比值', async () => {
    const wrapper = mount(DesignSystemTokenAuditDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot /></div>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-input': { template: '<input />' },
          'a-table': { template: '<div class="ant-table"><slot /></div>' },
        },
      },
    })

    await flushPromises()

    const calcBtn = wrapper.findAll('button').find(b => b.text().includes('计算 WCAG 对比度'))
    expect(calcBtn).toBeDefined()
    await calcBtn?.trigger('click')
    await flushPromises()

    expect(visualApi.computeContrastRatio).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('15.8:1')
  })
})
