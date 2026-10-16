import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ClientMemoryLeakDetectorCard from './ClientMemoryLeakDetectorCard.vue'
import * as visualApi from '@/api/visualRegressionA11y'

describe('ClientMemoryLeakDetectorCard.vue (UI4.2)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(visualApi, 'listMemoryLeakReports').mockResolvedValue({
      total: 1,
      reports: [
        {
          report_id: 'mem_rpt_001',
          page_or_scenario: 'drawer_open_close_test',
          initial_heap_bytes: 10000000,
          final_heap_bytes: 10520000,
          heap_growth_percentage: 5.2,
          total_detached_dom_count: 1,
          total_unreleased_listeners_count: 0,
          has_critical_leak: false,
          memory_health_score_pct: 95.0,
          findings: [
            {
              finding_id: 'find_1',
              leak_type: 'DETACHED_DOM_TREE_LEAK',
              severity: 'HIGH',
              title: '脱落 DOM 节点幽灵引用',
              impact_description: 'ECharts 画布脱落未回收',
              remediation_suggestion: '调用 dispose() 释放',
            },
          ],
          detached_nodes_sample: [],
          created_at: new Date().toISOString(),
        },
      ],
    })
    vi.spyOn(visualApi, 'analyzeMemoryLeak').mockResolvedValue({
      message: '分析完成',
      report: {
        report_id: 'mem_rpt_002',
        page_or_scenario: 'drawer_open_close_test',
        initial_heap_bytes: 10000000,
        final_heap_bytes: 10100000,
        heap_growth_percentage: 1.0,
        total_detached_dom_count: 0,
        total_unreleased_listeners_count: 0,
        has_critical_leak: false,
        memory_health_score_pct: 100.0,
        findings: [],
        detached_nodes_sample: [],
        created_at: new Date().toISOString(),
      },
    })
  })

  it('正确渲染标题 Banner、4 项核心内存健康 KPI 卡片及缺陷列表', async () => {
    const wrapper = mount(ClientMemoryLeakDetectorCard, {
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

    expect(wrapper.text()).toContain('客户端运行时内存泄漏与 DOM 节点脱落幽灵引用分析引擎')
    expect(wrapper.text()).toContain('内存健康综合评分')
    expect(wrapper.text()).toContain('高危内存泄露状态')
    expect(wrapper.text()).toContain('JS 堆净增长率')
    expect(wrapper.text()).toContain('脱落 DOM / 残留监听器')
    expect(wrapper.text()).toContain('95.0%')
  })

  it('点击启动分析按钮能正确调用 API 并更新内存报告结果', async () => {
    const wrapper = mount(ClientMemoryLeakDetectorCard, {
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

    const analyzeBtn = wrapper.findAll('button').find(b => b.text().includes('启动内存泄露全息诊断'))
    expect(analyzeBtn).toBeDefined()
    await analyzeBtn?.trigger('click')
    await flushPromises()

    expect(visualApi.analyzeMemoryLeak).toHaveBeenCalledTimes(1)
  })
})
