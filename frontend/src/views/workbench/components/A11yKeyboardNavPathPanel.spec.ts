import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import A11yKeyboardNavPathPanel from './A11yKeyboardNavPathPanel.vue'
import * as visualApi from '@/api/visualRegressionA11y'

describe('A11yKeyboardNavPathPanel.vue (UI3.2)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(visualApi, 'listKeyboardNavReports').mockResolvedValue({
      total: 1,
      reports: [
        {
          report_id: 'kb_rpt_001',
          page_name: 'checkout_modal',
          total_focusable_elements: 4,
          total_defects_count: 1,
          has_focus_trap: false,
          keyboard_accessibility_score_pct: 92.0,
          is_fully_keyboard_accessible: false,
          traversal_path: [
            { step_order: 1, element_id: 'btn_1', tag_name: 'button', tabindex: 0, has_visible_focus: true, container_id: 'modal' },
            { step_order: 2, element_id: 'btn_2', tag_name: 'button', tabindex: 0, has_visible_focus: false, container_id: 'modal' },
          ],
          defects: [
            {
              defect_id: 'def_1',
              defect_type: 'FOCUS_RING_INVISIBLE',
              severity: 'HIGH',
              element_id: 'btn_2',
              description: '无可见聚焦环',
              remediation_suggestion: ':focus-visible { outline: 2px solid #1677ff; }',
            },
          ],
          created_at: new Date().toISOString(),
        },
      ],
    })
    vi.spyOn(visualApi, 'simulateKeyboardNav').mockResolvedValue({
      message: '仿真完成',
      report: {
        report_id: 'kb_rpt_002',
        page_name: 'checkout_modal',
        total_focusable_elements: 2,
        total_defects_count: 0,
        has_focus_trap: false,
        keyboard_accessibility_score_pct: 100.0,
        is_fully_keyboard_accessible: true,
        traversal_path: [],
        defects: [],
        created_at: new Date().toISOString(),
      },
    })
  })

  it('正确渲染标题 Banner、4 项核心全盲键盘可达性 KPI 卡片及步进轨迹流', async () => {
    const wrapper = mount(A11yKeyboardNavPathPanel, {
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

    expect(wrapper.text()).toContain('全盲读屏与无鼠标纯键盘导航路径可达性仿真中心')
    expect(wrapper.text()).toContain('键盘可访问性得分')
    expect(wrapper.text()).toContain('键盘死锁状态 (Trap)')
    expect(wrapper.text()).toContain('完全键盘可达性')
    expect(wrapper.text()).toContain('聚焦元素 / 缺陷数')
    expect(wrapper.text()).toContain('92.0%')
  })

  it('点击启动 Tab 仿真按钮能正确调用 API 并更新键盘分析结论', async () => {
    const wrapper = mount(A11yKeyboardNavPathPanel, {
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

    const simBtn = wrapper.findAll('button').find(b => b.text().includes('启动 Tab 键流转仿真'))
    expect(simBtn).toBeDefined()
    await simBtn?.trigger('click')
    await flushPromises()

    expect(visualApi.simulateKeyboardNav).toHaveBeenCalledTimes(1)
  })
})
