import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ExplorationTraceSynthesizer from './ExplorationTraceSynthesizer.vue'

const mockSynthesize = vi.fn().mockResolvedValue({
  name: '自动探索冒烟用例 - 商品结算流',
  module_id: 1,
  case_type: 'android',
  description: '由 ATP AI 智能探索引擎自动去噪提炼合成',
  steps: [
    {
      name: '点击 加入购物车',
      action: 'click',
      params: { resource_id: 'btn_cart', text: '加入购物车' },
      is_key_step: true,
    },
    {
      name: '输入 user888',
      action: 'input',
      params: { resource_id: 'txt_coupon', text: 'user888' },
      is_key_step: true,
    },
    {
      name: '点击 提交订单',
      action: 'click',
      params: { resource_id: 'btn_submit' },
      is_key_step: true,
    },
    {
      name: '终态文本断言',
      action: 'assert_text',
      params: { expected_text: '支付成功，等待商家发货' },
      is_key_step: true,
    },
  ],
})

vi.mock('@/api/exploration', () => ({
  explorationApi: {
    synthesizeCase: (payload: unknown) => mockSynthesize(payload),
    step: vi.fn(),
    getSession: vi.fn(),
    evaluateCircuitBreaker: vi.fn(),
  },
}))

describe('ExplorationTraceSynthesizer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders initial sample events and calculates compression rate', async () => {
    const wrapper = mount(ExplorationTraceSynthesizer, {
      global: {
        stubs: {
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': true,
          'a-input-number': true,
          'a-select': true,
          'a-select-option': true,
          'a-switch': true,
          'a-button': { template: '<button><slot /></button>' },
          'a-tag': { template: '<span><slot /></span>' },
          'a-divider': true,
          'a-empty': { template: '<div class="empty-stub"><slot /></div>' },
        },
      },
    })

    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('探索事件流实时轨迹与自动化用例合成')
    expect(wrapper.text()).toContain('10 条') // 10 sample raw events

    const vm = wrapper.vm as unknown as {
      rawEvents: Array<Record<string, unknown>>
      runSynthesis: () => Promise<void>
      synthesizedResult: { steps?: unknown[] } | null
    }

    expect(vm.rawEvents.length).toBe(10)

    // Run synthesis
    await vm.runSynthesis()
    expect(mockSynthesize).toHaveBeenCalledWith(
      expect.objectContaining({
        name: '自动探索冒烟用例 - 商品结算流',
        module_id: 1,
      }),
    )

    expect(vm.synthesizedResult?.steps?.length).toBe(4)
    expect(wrapper.text()).toContain('压缩率 60%')
  })

  it('handles case persistence mode', async () => {
    mockSynthesize.mockResolvedValueOnce({
      id: 888,
      name: '持久化用例',
      module_id: 1,
      case_type: 'android',
      steps: [{ name: 'Step 1', action: 'click', params: {} }],
    })

    const wrapper = mount(ExplorationTraceSynthesizer, {
      global: {
        stubs: {
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': true,
          'a-input-number': true,
          'a-select': true,
          'a-select-option': true,
          'a-switch': true,
          'a-button': { template: '<button><slot /></button>' },
          'a-tag': { template: '<span><slot /></span>' },
          'a-divider': true,
          'a-empty': true,
        },
      },
    })

    const vm = wrapper.vm as unknown as {
      caseForm: { persist: boolean }
      runSynthesis: () => Promise<void>
      synthesizedResult: { id?: number } | null
    }

    vm.caseForm.persist = true
    await vm.runSynthesis()

    expect(mockSynthesize).toHaveBeenCalledWith(
      expect.objectContaining({ persist: true }),
    )
    expect(vm.synthesizedResult?.id).toBe(888)
  })
})
