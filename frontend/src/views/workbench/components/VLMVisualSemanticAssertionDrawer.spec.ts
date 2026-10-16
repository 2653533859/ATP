import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import VLMVisualSemanticAssertionDrawer from './VLMVisualSemanticAssertionDrawer.vue'
import * as visualApi from '@/api/visualRegressionA11y'

describe('VLMVisualSemanticAssertionDrawer.vue (UI2.1)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(visualApi, 'listVlmAssertionReports').mockResolvedValue({
      total: 1,
      reports: [
        {
          report_id: 'vlm_rpt_001',
          page_route_or_name: '/views/checkout',
          total_assertions_count: 5,
          passed_count: 5,
          failed_count: 0,
          semantic_score_pct: 100.0,
          is_page_integrity_pass: true,
          assertions: [
            {
              rule_type: 'ASSERT_NO_WHITE_SCREEN',
              description: '无白屏崩溃',
              is_passed: true,
              confidence_score: 0.99,
              failure_reason: null,
            },
            {
              rule_type: 'ASSERT_NO_BROKEN_IMAGES',
              description: '无裂图断图',
              is_passed: true,
              confidence_score: 0.96,
              failure_reason: null,
            },
          ],
          created_at: new Date().toISOString(),
        },
      ],
    })
    vi.spyOn(visualApi, 'evaluateVlmSemanticAssertions').mockResolvedValue({
      message: '推导成功',
      report: {
        report_id: 'vlm_rpt_002',
        page_route_or_name: '/views/checkout',
        total_assertions_count: 5,
        passed_count: 5,
        failed_count: 0,
        semantic_score_pct: 100.0,
        is_page_integrity_pass: true,
        assertions: [
          {
            rule_type: 'ASSERT_NO_WHITE_SCREEN',
            description: '无白屏崩溃',
            is_passed: true,
            confidence_score: 0.99,
            failure_reason: null,
          },
        ],
        created_at: new Date().toISOString(),
      },
    })
  })

  it('正确渲染标题 Banner、4 项核心语义 KPI 卡片与规则编排卡片', async () => {
    const wrapper = mount(VLMVisualSemanticAssertionDrawer, {
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
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-checkbox': { template: '<input type="checkbox" />' },
          'a-table': { template: '<div class="ant-table"><slot /></div>' },
          'a-progress': { template: '<div class="ant-progress" />' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('基于视觉大模型 (VLM) 的多模态 UI 页面完整性语义推理引擎')
    expect(wrapper.text()).toContain('语义完整性判定')
    expect(wrapper.text()).toContain('视觉语义健康得分')
    expect(wrapper.text()).toContain('断言通过率')
    expect(wrapper.text()).toContain('大模型平均置信度')
    expect(wrapper.text()).toContain('INTEGRITY_PASS')
  })

  it('点击执行推导按钮能正确调用 API 并更新断言结论', async () => {
    const wrapper = mount(VLMVisualSemanticAssertionDrawer, {
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
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-checkbox': { template: '<input type="checkbox" />' },
          'a-table': { template: '<div class="ant-table"><slot /></div>' },
          'a-progress': { template: '<div class="ant-progress" />' },
        },
      },
    })

    await flushPromises()

    const evalBtn = wrapper.findAll('button').find(b => b.text().includes('执行 VLM 视觉语义推导'))
    expect(evalBtn).toBeDefined()
    await evalBtn?.trigger('click')
    await flushPromises()

    expect(visualApi.evaluateVlmSemanticAssertions).toHaveBeenCalledTimes(1)
  })
})
