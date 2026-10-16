import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import SmartTestSelectionWorkbenchCard from './SmartTestSelectionWorkbenchCard.vue'
import { ciImpactApi } from '@/api/ciImpact'

const mockReport = {
  selection_id: 'sel_demo_123',
  diff_analysis_id: 'diff_123',
  strategy: 'balanced',
  total_repository_cases_count: 20,
  selected_cases_count: 2,
  pruned_cases_count: 18,
  pruning_ratio_pct: 90.0,
  estimated_execution_time_sec: 7.0,
  estimated_time_saved_sec: 63.0,
  selected_cases: [
    {
      case_id: 101,
      case_name: '订单折扣核算用例',
      priority: 'P0',
      selection_reason: '直接命中修改代码符号 (2 处); P0 级核心业务准入用例',
      confidence_score: 0.95,
      estimated_duration_sec: 3.5,
      matched_symbols: ['app/api/orders.py:calculate_discount'],
      matched_routes: ['POST /api/v1/orders/create'],
    },
    {
      case_id: 102,
      case_name: '结算收银台流程',
      priority: 'P1',
      selection_reason: '命中同一代码模块/文件上下文',
      confidence_score: 0.70,
      estimated_duration_sec: 3.5,
      matched_symbols: [],
      matched_routes: [],
    },
  ],
  created_at: '2026-10-16T10:00:00Z',
}

vi.mock('@/api/ciImpact', () => ({
  ciImpactApi: {
    selectTests: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('@ant-design/icons-vue', () => ({
  AimOutlined: { template: '<span>Aim</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  PlayCircleOutlined: { template: '<span>Play</span>' },
}))

describe('SmartTestSelectionWorkbenchCard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(ciImpactApi.selectTests).mockResolvedValue({
      message: '精准测试集推导完成',
      report: mockReport as any,
    })
  })

  it('renders card title, 90% pruning ratio metric, and recommended cases table', async () => {
    const wrapper = mount(SmartTestSelectionWorkbenchCard, {
      props: {
        projectId: 1,
      },
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-progress': { template: '<div class="ant-progress" />' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.case_id" class="row">
                  <span class="case-name-col">{{ item.case_name }}</span>
                  <span class="reason-col">{{ item.selection_reason }}</span>
                </div>
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()

    // 验证标题与裁剪率统计
    expect(wrapper.text()).toContain('精准测试用例推荐与冗余裁剪')
    expect(wrapper.text()).toContain('90%')
    expect(wrapper.text()).toContain('2')
    expect(wrapper.text()).toContain('20 全量')
    expect(wrapper.text()).toContain('63')

    // 验证表格内容
    expect(wrapper.text()).toContain('订单折扣核算用例')
    expect(wrapper.text()).toContain('直接命中修改代码符号')

    expect(ciImpactApi.selectTests).toHaveBeenCalled()
  })

  it('triggers execute selected and emits execute event', async () => {
    const wrapper = mount(SmartTestSelectionWorkbenchCard, {
      props: {
        projectId: 1,
      },
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-progress': { template: '<div class="ant-progress" />' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    vm.handleExecuteSelected()

    expect(wrapper.emitted('execute')).toBeTruthy()
    expect(wrapper.emitted('execute')![0]).toEqual([[101, 102]])
  })
})
