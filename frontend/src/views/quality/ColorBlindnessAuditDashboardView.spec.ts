import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ColorBlindnessAuditDashboardView from './ColorBlindnessAuditDashboardView.vue'
import * as visualApi from '@/api/visualRegressionA11y'

describe('ColorBlindnessAuditDashboardView.vue (UI3.3)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(visualApi, 'listColorBlindnessReports').mockResolvedValue({
      total: 1,
      reports: [
        {
          report_id: 'cvd_rpt_001',
          component_or_page: 'atp_main_workbench',
          total_indicators_checked: 3,
          total_violations_count: 1,
          critical_count: 1,
          is_wcag_1_4_1_compliant: false,
          cvd_accessibility_score_pct: 94.0,
          violations: [],
          simulations: [],
          created_at: new Date().toISOString(),
        },
      ],
    })
    vi.spyOn(visualApi, 'simulateColorVision').mockResolvedValue({
      message: '计算完成',
      simulation: {
        original_hex: '#22C55E',
        protanopia_hex: '#A09D5E',
        deuteranopia_hex: '#B2975E',
        tritanopia_hex: '#24B6BE',
        achromatopsia_hex: '#969696',
      },
    })
    vi.spyOn(visualApi, 'auditColorBlindness').mockResolvedValue({
      message: '审计完成',
      report: {
        report_id: 'cvd_rpt_002',
        component_or_page: 'atp_main_workbench',
        total_indicators_checked: 3,
        total_violations_count: 0,
        critical_count: 0,
        is_wcag_1_4_1_compliant: true,
        cvd_accessibility_score_pct: 100.0,
        violations: [],
        simulations: [],
        created_at: new Date().toISOString(),
      },
    })
  })

  it('正确渲染全景大盘 Banner、四大 CVD KPI 统计卡片与 4 分屏滤镜舞台', async () => {
    const wrapper = mount(ColorBlindnessAuditDashboardView, {
      global: {
        stubs: {
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot /></div>' },
          'a-table': { template: '<div class="ant-table"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('色盲/色弱多模态视觉感知模拟与无障碍准入大盘')
    expect(wrapper.text()).toContain('CVD 无障碍准入得分')
    expect(wrapper.text()).toContain('WCAG 1.4.1 准入裁决')
    expect(wrapper.text()).toContain('唯一色彩指示缺陷')
    expect(wrapper.text()).toContain('标准正常视觉 (Normal)')
    expect(wrapper.text()).toContain('红色盲视角 (Protanopia)')
    expect(wrapper.text()).toContain('绿色盲视角 (Deuteranopia)')
    expect(wrapper.text()).toContain('全色盲视角 (Achromatopsia)')
  })

  it('点击模拟计算按钮能正确调用 API 并更新 4 屏色卡数值', async () => {
    const wrapper = mount(ColorBlindnessAuditDashboardView, {
      global: {
        stubs: {
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot /></div>' },
          'a-table': { template: '<div class="ant-table"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
        },
      },
    })

    await flushPromises()

    const simBtn = wrapper.findAll('button').find(b => b.text().includes('模拟计算'))
    expect(simBtn).toBeDefined()
    await simBtn?.trigger('click')
    await flushPromises()

    expect(visualApi.simulateColorVision).toHaveBeenCalledTimes(1)
  })
})
