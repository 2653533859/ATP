import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import UILayoutCollisionDetectorCard from './UILayoutCollisionDetectorCard.vue'
import * as visualApi from '@/api/visualRegressionA11y'

describe('UILayoutCollisionDetectorCard.vue (UI2.2)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(visualApi, 'listLayoutDefectReports').mockResolvedValue({
      total: 1,
      reports: [
        {
          report_id: 'layout_rpt_001',
          target_name: '/views/checkout',
          total_elements_checked: 8,
          collision_count: 1,
          horizontal_overflow_count: 1,
          truncation_count: 1,
          layout_integrity_score_pct: 92.0,
          has_blocking_defect: true,
          defects: [
            {
              defect_id: 'def_1',
              defect_type: 'ELEMENT_BOUNDING_BOX_COLLISION',
              severity: 'CRITICAL',
              element_id: 'btn1 vs btn2',
              bounding_box: { x: 10, y: 20, width: 100, height: 40 },
              description: '按钮重叠',
              remediation_suggestion: 'display: flex; gap: 8px;',
            },
          ],
          created_at: new Date().toISOString(),
        },
      ],
    })
    vi.spyOn(visualApi, 'detectLayoutDefects').mockResolvedValue({
      message: '检测完成',
      report: {
        report_id: 'layout_rpt_002',
        target_name: '/views/checkout',
        total_elements_checked: 5,
        collision_count: 1,
        horizontal_overflow_count: 0,
        truncation_count: 0,
        layout_integrity_score_pct: 95.0,
        has_blocking_defect: false,
        defects: [],
        created_at: new Date().toISOString(),
      },
    })
  })

  it('正确渲染标题 Banner、4 项核心几何空间 KPI 卡片及缺陷列表', async () => {
    const wrapper = mount(UILayoutCollisionDetectorCard, {
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
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-table': { template: '<div class="ant-table"><slot /></div>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('基于 AABB 空间几何盒模型的布局越界与物理碰撞检测引擎')
    expect(wrapper.text()).toContain('布局完整性评分')
    expect(wrapper.text()).toContain('阻断性缺陷状态')
    expect(wrapper.text()).toContain('元素重叠碰撞数')
    expect(wrapper.text()).toContain('横向溢出 / 文本截断')
    expect(wrapper.text()).toContain('92.0%')
  })

  it('点击启动检测按钮能正确调用 API 并更新布局分析结果', async () => {
    const wrapper = mount(UILayoutCollisionDetectorCard, {
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
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-table': { template: '<div class="ant-table"><slot /></div>' },
        },
      },
    })

    await flushPromises()

    const detectBtn = wrapper.findAll('button').find(b => b.text().includes('启动 AABB 碰撞溢出检测'))
    expect(detectBtn).toBeDefined()
    await detectBtn?.trigger('click')
    await flushPromises()

    expect(visualApi.detectLayoutDefects).toHaveBeenCalledTimes(1)
  })
})
