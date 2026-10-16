import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import SmartLocatorHealingConsoleDrawer from './SmartLocatorHealingConsoleDrawer.vue'
import { smartLocatorHealingApi } from '@/api/testSelfHealing'

const mockHealedResult = {
  healing_id: 'heal_test_101',
  original_locator: "//button[@id='old-checkout-btn']",
  healed_locator: "//button[contains(normalize-space(), '立即提交订单')]",
  is_healed: true,
  confidence_score: 0.79,
  winning_strategy: 'TEXT_SEMANTIC',
  scores_breakdown: {
    text_semantic_score: 1.0,
    test_id_score: 0.5,
    tag_role_score: 1.0,
    attribute_score: 0.5,
    spatial_score: 0.95,
    composite_confidence: 0.79,
  },
  remediation_patch_code: '# 自愈补丁建议:\npage.locator("//button[contains(normalize-space(), \'立即提交订单\')]")',
  retry_executed: true,
  retry_success: true,
  healed_at: '2026-10-16T12:00:00Z',
}

const mockUnmatchedResult = {
  healing_id: 'heal_test_102',
  original_locator: "//input[@name='user_password']",
  healed_locator: "//input[@name='user_password']",
  is_healed: false,
  confidence_score: 0.10,
  winning_strategy: 'NONE',
  scores_breakdown: {
    text_semantic_score: 0.0,
    test_id_score: 0.0,
    tag_role_score: 0.2,
    attribute_score: 0.0,
    spatial_score: 0.5,
    composite_confidence: 0.10,
  },
  remediation_patch_code: '',
  retry_executed: true,
  retry_success: false,
  healed_at: '2026-10-16T12:05:00Z',
}

const mockStats = {
  total_healing_attempts: 10,
  successful_healings_count: 10,
  healing_success_rate_pct: 100.0,
  strategy_distribution: { TEXT_SEMANTIC: 8, TEST_ID: 2 },
}

vi.mock('@/api/testSelfHealing', () => ({
  smartLocatorHealingApi: {
    heal: vi.fn(),
    getHistory: vi.fn(),
    clearHistory: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}))

vi.mock('@ant-design/icons-vue', () => ({
  ToolOutlined: { template: '<span>Tool</span>' },
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
  CopyOutlined: { template: '<span>Copy</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
}))

describe('SmartLocatorHealingConsoleDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(smartLocatorHealingApi.heal).mockResolvedValue({
      message: '自愈计算完成',
      result: mockHealedResult as any,
    })
    vi.mocked(smartLocatorHealingApi.getHistory).mockResolvedValue({
      statistics: mockStats as any,
      history: [mockHealedResult as any],
    })
  })

  it('renders header, 5 strategy cards, verdict banner, and progress scores', async () => {
    const wrapper = mount(SmartLocatorHealingConsoleDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-progress': { template: '<div class="progress" />' },
        },
      },
    })

    await flushPromises()

    // 检查调用与标题
    expect(smartLocatorHealingApi.heal).toHaveBeenCalled()
    expect(smartLocatorHealingApi.getHistory).toHaveBeenCalled()
    expect(wrapper.text()).toContain('UI 元素选择器漂移动态自愈与五维加权降级重试')

    // 检查五维策略卡片
    expect(wrapper.text()).toContain('文本语义 (30%)')
    expect(wrapper.text()).toContain('TestID 标识 (25%)')
    expect(wrapper.text()).toContain('空间邻域 (15%)')

    // 检查裁决横幅
    expect(wrapper.text()).toContain('自愈成功 (HEALED)')
    expect(wrapper.text()).toContain('79%')
    expect(wrapper.text()).toContain('//button[@id=\'old-checkout-btn\']')
    expect(wrapper.text()).toContain('//button[contains(normalize-space(), \'立即提交订单\')]')

    // 检查统计指标
    expect(wrapper.text()).toContain('100%')
  })

  it('switches preset to unmatch and verifies failed healing state', async () => {
    vi.mocked(smartLocatorHealingApi.heal).mockResolvedValueOnce({
      message: '自愈计算完成',
      result: mockHealedResult as any,
    }).mockResolvedValueOnce({
      message: '自愈计算完成',
      result: mockUnmatchedResult as any,
    })

    const wrapper = mount(SmartLocatorHealingConsoleDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-progress': { template: '<div class="progress" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.applyPreset('unmatch')
    await flushPromises()

    expect(smartLocatorHealingApi.heal).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('置信度不足 (UNRESOLVED)')
  })
})
