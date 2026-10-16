import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import WcagA11yDeepScannerDrawer from './WcagA11yDeepScannerDrawer.vue'
import * as visualApi from '@/api/visualRegressionA11y'

describe('WcagA11yDeepScannerDrawer.vue (UI3.1)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(visualApi, 'listWcagReports').mockResolvedValue({
      total: 1,
      reports: [
        {
          report_id: 'wcag_rpt_001',
          page_url_or_name: 'https://atp.example.com/workbench',
          total_elements_scanned: 10,
          total_violations_count: 2,
          critical_count: 0,
          high_count: 1,
          medium_count: 1,
          low_count: 0,
          compliance_score_pct: 96.0,
          is_wcag_aa_compliant: true,
          violations: [
            {
              violation_id: 'v_1',
              rule_id: '1.1.1',
              rule_name: 'Non-text Content',
              severity: 'HIGH',
              element_id: 'avatar_img',
              tag_name: 'img',
              selector: 'img.avatar',
              issue_description: '缺少 alt',
              remediation_suggestion: '<img alt="avatar" />',
            },
          ],
          created_at: new Date().toISOString(),
        },
      ],
    })
    vi.spyOn(visualApi, 'scanDomAccessibility').mockResolvedValue({
      message: '扫描完成',
      report: {
        report_id: 'wcag_rpt_002',
        page_url_or_name: 'https://atp.example.com/workbench',
        total_elements_scanned: 5,
        total_violations_count: 0,
        critical_count: 0,
        high_count: 0,
        medium_count: 0,
        low_count: 0,
        compliance_score_pct: 100.0,
        is_wcag_aa_compliant: true,
        violations: [],
        created_at: new Date().toISOString(),
      },
    })
  })

  it('正确渲染标题 Banner、4 项核心 WCAG 2.2 KPI 卡片与违规列表', async () => {
    const wrapper = mount(WcagA11yDeepScannerDrawer, {
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

    expect(wrapper.text()).toContain('W3C WCAG 2.2 国际无障碍标准 DOM 深度合规审查中心')
    expect(wrapper.text()).toContain('WCAG 2.2 合规综合得分')
    expect(wrapper.text()).toContain('WCAG 2.2 AA 级准入')
    expect(wrapper.text()).toContain('致命阻断项 (Critical)')
    expect(wrapper.text()).toContain('违规缺陷总数')
    expect(wrapper.text()).toContain('96.0%')
  })

  it('点击启动扫描按钮能正确调用 API 并更新扫描结果', async () => {
    const wrapper = mount(WcagA11yDeepScannerDrawer, {
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

    const scanBtn = wrapper.findAll('button').find(b => b.text().includes('启动 WCAG 2.2 DOM 扫描'))
    expect(scanBtn).toBeDefined()
    await scanBtn?.trigger('click')
    await flushPromises()

    expect(visualApi.scanDomAccessibility).toHaveBeenCalledTimes(1)
  })
})
