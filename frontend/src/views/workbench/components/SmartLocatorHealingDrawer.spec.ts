import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import SmartLocatorHealingDrawer from './SmartLocatorHealingDrawer.vue'
import { aiHealingLocatorsApi } from '@/api/aiHealing'

const mockHealingSuccess = {
  audit_id: 'heal_audit_001',
  success: true,
  original_locator: "//button[@id='btn-old-submit']",
  best_proposal: {
    proposal_id: 'prop_001',
    healed_locator: "//*[@data-testid='submit-order-btn']",
    locator_type: 'test_id' as const,
    confidence_score: 0.92,
    match_strategy: '优先使用高保真 data-testid 稳定属性',
    matched_element: {
      tag_name: 'button',
      text_content: '确认支付并提交订单',
      element_id: 'btn-v2-dynamic-888',
      attributes: {
        'data-testid': 'submit-order-btn',
      },
    },
    reason: "data-testid='submit-order-btn' (35%)；文本完全匹配='确认支付并提交订单' (25%)",
  },
  all_proposals: [
    {
      proposal_id: 'prop_001',
      healed_locator: "//*[@data-testid='submit-order-btn']",
      locator_type: 'test_id' as const,
      confidence_score: 0.92,
      match_strategy: '优先使用高保真 data-testid 稳定属性',
      matched_element: {
        tag_name: 'button',
      },
      reason: '高置信度命中',
    },
    {
      proposal_id: 'prop_002',
      healed_locator: "//button[text()='确认支付并提交订单']",
      locator_type: 'xpath' as const,
      confidence_score: 0.65,
      match_strategy: '使用标签与文本内容唯一锚定',
      matched_element: {
        tag_name: 'button',
      },
      reason: '文本匹配',
    },
  ],
  elements_scanned_count: 5,
  healed_at: '2026-10-16T12:00:00Z',
}

const mockHealingFailure = {
  audit_id: 'heal_audit_002',
  success: false,
  original_locator: "//button[@id='btn-removed']",
  best_proposal: null,
  all_proposals: [],
  elements_scanned_count: 5,
  healed_at: '2026-10-16T12:00:00Z',
}

vi.mock('@/api/aiHealing', () => ({
  aiHealingLocatorsApi: {
    healLocator: vi.fn(),
    listHistory: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
    error: vi.fn(),
  },
}))

describe('SmartLocatorHealingDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders drawer header, original locator input, and JSON editors', async () => {
    const wrapper = mount(SmartLocatorHealingDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-input': { template: '<input />' },
          'a-textarea': { template: '<textarea />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-row': { template: '<div class="ant-row"><slot /></div>' },
          'a-col': { template: '<div class="ant-col"><slot /></div>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('AI 失效选择器 DOM/UI 树多模态自愈恢复')
    expect(wrapper.text()).toContain('失效元素选择器与多模态特征差分输入')
    expect(wrapper.text()).toContain('历史已知元素指纹 (Last Known Fingerprint)')
    expect(wrapper.text()).toContain('当前活动页面 DOM 快照列表 (Live DOM Snapshot)')
  })

  it('triggers locator healing and renders best proposal with confidence score', async () => {
    vi.mocked(aiHealingLocatorsApi.healLocator).mockResolvedValue(mockHealingSuccess)

    const wrapper = mount(SmartLocatorHealingDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-input': { template: '<input />' },
          'a-textarea': { template: '<textarea />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-alert': { template: '<div class="ant-alert">{{ message }} {{ description }}</div>', props: ['message', 'description'] },
          'a-progress': { template: '<div class="ant-progress" />' },
          'a-row': { template: '<div class="ant-row"><slot /></div>' },
          'a-col': { template: '<div class="ant-col"><slot /></div>' },
          'a-table': {
            template: `
              <div class="ant-table">
                <div v-for="item in dataSource" :key="item.proposal_id" class="row">
                  <slot name="bodyCell" :column="{ key: 'healed_locator' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'locator_type' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'confidence' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'actions' }" :record="item" />
                </div>
              </div>
            `,
            props: ['dataSource'],
          },
        },
      },
    })

    await flushPromises()

    const healBtn = wrapper.findAll('button').find((b) => b.text().includes('多模态智能自愈'))
    expect(healBtn).toBeDefined()
    await healBtn!.trigger('click')
    await flushPromises()

    expect(aiHealingLocatorsApi.healLocator).toHaveBeenCalledWith({
      original_locator: "//button[@id='btn-old-submit']",
      locator_type: 'xpath',
      last_known_fingerprint: expect.any(Object),
      live_dom_elements: expect.any(Array),
      min_confidence: 0.50,
    })

    // 验证自愈推荐结果渲染
    expect(wrapper.text()).toContain('⭐ AI 最优推荐自愈表达式')
    expect(wrapper.text()).toContain('92%')
    expect(wrapper.text()).toContain("//*[@data-testid='submit-order-btn']")
    expect(wrapper.text()).toContain("data-testid='submit-order-btn'")
    expect(wrapper.text()).toContain('自愈推导成功')
  })

  it('renders failure alert when healing does not meet confidence threshold', async () => {
    vi.mocked(aiHealingLocatorsApi.healLocator).mockResolvedValue(mockHealingFailure)

    const wrapper = mount(SmartLocatorHealingDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-input': { template: '<input />' },
          'a-textarea': { template: '<textarea />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-alert': { template: '<div class="ant-alert">{{ message }} {{ description }}</div>', props: ['message', 'description'] },
          'a-row': { template: '<div class="ant-row"><slot /></div>' },
          'a-col': { template: '<div class="ant-col"><slot /></div>' },
          'a-table': { template: '<div class="ant-table" />' },
        },
      },
    })

    await flushPromises()

    const healBtn = wrapper.findAll('button').find((b) => b.text().includes('多模态智能自愈'))
    await healBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('[自愈未达置信度]')
    expect(wrapper.text()).toContain('当前页面未发现与历史特征吻合度达到阈值的候选元素')
  })
})
