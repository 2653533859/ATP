import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import VisualGoldenBaselineEvolutionPanel from './VisualGoldenBaselineEvolutionPanel.vue'
import * as visualApi from '@/api/visualRegressionA11y'

describe('VisualGoldenBaselineEvolutionPanel.vue (UI1.2)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(visualApi, 'listBaselineSnapshots').mockResolvedValue({
      total: 2,
      baselines: [
        {
          baseline_id: 'base_001',
          page_route: '/views/checkout',
          branch_name: 'main',
          version_tag: 'v1.2.0-gold',
          viewport_snapshots: { DESKTOP: 'sha1', TABLET: 'sha2', MOBILE: 'sha3' },
          approved_by: 'lead_architect',
          is_active_golden: true,
          changelog: '初始生产黄金基线',
          created_at: new Date().toISOString(),
        },
        {
          baseline_id: 'base_002',
          page_route: '/views/checkout',
          branch_name: 'feat/v4.5-ui',
          version_tag: 'v1.3.0-rc',
          viewport_snapshots: { DESKTOP: 'sha4' },
          approved_by: 'qa_engineer',
          is_active_golden: false,
          changelog: '改版抽屉样式',
          created_at: new Date().toISOString(),
        },
      ],
    })
    vi.spyOn(visualApi, 'compareBranchBaselines').mockResolvedValue({
      page_route: '/views/checkout',
      base_branch: 'main',
      target_branch: 'feat/v4.5-ui',
      evolution_type: 'INTENTIONAL_REDESIGN',
      has_regression: false,
      audit_summary: '目标分支视觉变迁属于有意图的 UI 改版，无非预期样式破坏。',
    })
    vi.spyOn(visualApi, 'promoteGoldenBaseline').mockResolvedValue({
      message: '晋升成功',
      baseline: {
        baseline_id: 'base_002',
        page_route: '/views/checkout',
        branch_name: 'feat/v4.5-ui',
        version_tag: 'v1.3.0-rc',
        viewport_snapshots: { DESKTOP: 'sha4' },
        approved_by: 'qa_engineer',
        is_active_golden: true,
        changelog: '改版抽屉样式',
        created_at: new Date().toISOString(),
      },
    })
  })

  it('正确渲染标题 Banner、活跃黄金基线 KPI 指标卡片及基线列表', async () => {
    const wrapper = mount(VisualGoldenBaselineEvolutionPanel, {
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
          'a-space': { template: '<div><slot /></div>' },
          'a-table': { template: '<div class="ant-table"><slot /></div>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-textarea': { template: '<textarea />' },
          'a-checkbox': { template: '<input type="checkbox" />' },
          StarFilled: { template: '<span>★</span>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('视觉黄金基线版本演变与跨分支比对中心')
    expect(wrapper.text()).toContain('活跃黄金基线版本')
    expect(wrapper.text()).toContain('跨视口覆盖率')
    expect(wrapper.text()).toContain('分支演变审计结论')
    expect(wrapper.text()).toContain('v1.2.0-gold')
  })

  it('点击执行分支比对能正确调用 API 并展示比对总结', async () => {
    const wrapper = mount(VisualGoldenBaselineEvolutionPanel, {
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
          'a-space': { template: '<div><slot /></div>' },
          'a-table': { template: '<div class="ant-table"><slot /></div>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-textarea': { template: '<textarea />' },
          'a-checkbox': { template: '<input type="checkbox" />' },
          StarFilled: { template: '<span>★</span>' },
        },
      },
    })

    await flushPromises()

    const compareBtn = wrapper.findAll('button').find(b => b.text().includes('执行分支比对'))
    expect(compareBtn).toBeDefined()
    await compareBtn?.trigger('click')
    await flushPromises()

    expect(visualApi.compareBranchBaselines).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('目标分支视觉变迁属于有意图的 UI 改版')
  })
})
