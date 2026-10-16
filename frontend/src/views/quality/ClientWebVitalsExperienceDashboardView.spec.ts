import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ClientWebVitalsExperienceDashboardView from './ClientWebVitalsExperienceDashboardView.vue'
import * as visualApi from '@/api/visualRegressionA11y'

describe('ClientWebVitalsExperienceDashboardView.vue (UI4.3)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(visualApi, 'listWebVitalsReports').mockResolvedValue({
      total: 1,
      reports: [
        {
          report_id: 'cwv_rpt_001',
          target_url_or_page: 'https://atp.example.com/workbench',
          overall_cwv_passed: true,
          performance_score_pct: 100.0,
          lcp: { name: 'LCP', value: 1850.0, unit: 'ms', rating: 'GOOD', good_threshold: 2500, poor_threshold: 4000 },
          inp: { name: 'INP', value: 110.0, unit: 'ms', rating: 'GOOD', good_threshold: 200, poor_threshold: 500 },
          cls: { name: 'CLS', value: 0.035, unit: 'score', rating: 'GOOD', good_threshold: 0.1, poor_threshold: 0.25 },
          auxiliary_metrics: [
            { name: 'FCP', value: 920.0, unit: 'ms', rating: 'GOOD', description: '首次内容渲染' },
          ],
          optimization_recommendations: ['各项核心指标全绿，表现卓越！'],
          created_at: new Date().toISOString(),
        },
      ],
    })
    vi.spyOn(visualApi, 'generateWebVitalsReport').mockResolvedValue({
      message: '生成成功',
      report: {
        report_id: 'cwv_rpt_002',
        target_url_or_page: 'https://atp.example.com/workbench',
        overall_cwv_passed: true,
        performance_score_pct: 100.0,
        lcp: { name: 'LCP', value: 1850.0, unit: 'ms', rating: 'GOOD', good_threshold: 2500, poor_threshold: 4000 },
        inp: { name: 'INP', value: 110.0, unit: 'ms', rating: 'GOOD', good_threshold: 200, poor_threshold: 500 },
        cls: { name: 'CLS', value: 0.035, unit: 'score', rating: 'GOOD', good_threshold: 0.1, poor_threshold: 0.25 },
        auxiliary_metrics: [],
        optimization_recommendations: ['全绿'],
        created_at: new Date().toISOString(),
      },
    })
    vi.spyOn(visualApi, 'getWebVitalsMarkdown').mockResolvedValue({
      report_id: 'cwv_rpt_001',
      markdown: '# Web Vitals 核心体验审计报告\n- LCP: 1850ms',
    })
  })

  it('正确渲染全景体验大盘 Banner、三大核心指标卡片看板与报告大表', async () => {
    const wrapper = mount(ClientWebVitalsExperienceDashboardView, {
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
          'a-input': { template: '<input />' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-textarea': { template: '<textarea />' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Google Core Web Vitals 全景核心体验审计大盘')
    expect(wrapper.text()).toContain('CWV 综合达标率')
    expect(wrapper.text()).toContain('加权体验得分')
    expect(wrapper.text()).toContain('LCP (最大内容渲染)')
    expect(wrapper.text()).toContain('INP (交互到下次绘制)')
    expect(wrapper.text()).toContain('CLS (累积布局偏移)')
    expect(wrapper.text()).toContain('1850.0ms')
    expect(wrapper.text()).toContain('110.0ms')
  })

  it('点击实时生成报告按钮能正确调用 API 并更新展示结果', async () => {
    const wrapper = mount(ClientWebVitalsExperienceDashboardView, {
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
          'a-input': { template: '<input />' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-textarea': { template: '<textarea />' },
        },
      },
    })

    await flushPromises()

    const genBtn = wrapper.findAll('button').find(b => b.text().includes('实时生成 Web Vitals 报告'))
    expect(genBtn).toBeDefined()
    await genBtn?.trigger('click')
    await flushPromises()

    expect(visualApi.generateWebVitalsReport).toHaveBeenCalledTimes(1)
  })
})
