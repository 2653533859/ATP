import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import SelfHealingDiffInspectionDrawer from './SelfHealingDiffInspectionDrawer.vue'
import { selfHealingCoreApi } from '@/api/testSelfHealing'

vi.mock('@/api/testSelfHealing', () => ({
  selfHealingCoreApi: {
    commitPatch: vi.fn().mockResolvedValue({ message: 'ok', patch: { status: 'COMMITTED_PERMANENT' } }),
    rejectPatch: vi.fn().mockResolvedValue({ message: 'rejected', patch: { status: 'REJECTED' } }),
  },
}))

const stubs = {
  'a-drawer': { template: '<div class="ant-drawer-stub"><slot /></div>' },
  'a-button': { template: '<button><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-space': { template: '<div class="ant-space-stub"><slot /></div>' },
  'a-table': { template: '<div class="ant-table-stub"><slot /></div>' },
}

describe('SelfHealingDiffInspectionDrawer.vue', () => {
  const samplePatch = {
    patch_id: 'patch_test_123',
    case_id: 'case_ecommerce_01',
    step_id: 'step_click_cart',
    status: 'APPLIED_IN_FLIGHT',
    confidence: 0.965,
    strategy_tier: 'TIER_1_ID_VARIATION',
    broken_context: {
      step_id: 'step_click_cart',
      failed_locator_type: 'css',
      failed_locator_value: '#btn_legacy_cart',
      element_text_hint: '立即加购',
      element_role_hint: 'button',
      screen_nodes: [
        {
          node_id: 'btn_new_cart',
          tag_name: 'button',
          text: '立即加购',
          attributes: { 'data-action': 'checkout_cart', class: 'btn-buy' },
        },
      ],
    },
    best_candidate: {
      matched_node_id: 'btn_new_cart',
      matched_node_tag: 'button',
      recommended_locator_type: 'css',
      recommended_locator_value: "button[data-action='checkout_cart']",
      confidence: 0.965,
      strategy_tier: 'TIER_1_ID_VARIATION',
      explanation: '基于属性特征匹配',
    },
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders diff comparison correctly when open', async () => {
    const wrapper = mount(SelfHealingDiffInspectionDrawer, {
      props: {
        open: true,
        patchData: samplePatch,
      },
      global: { stubs },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('#btn_legacy_cart')
    expect(wrapper.text()).toContain("button[data-action='checkout_cart']")
    expect(wrapper.text()).toContain('96.5%')
    expect(wrapper.text()).toContain('TIER_1_ID_VARIATION')
  })

  it('handles commit patch click', async () => {
    const wrapper = mount(SelfHealingDiffInspectionDrawer, {
      props: {
        open: true,
        patchData: samplePatch,
      },
      global: { stubs },
    })
    await flushPromises()

    const commitBtn = wrapper.findAll('button').find((b) => b.text().includes('一键采纳'))
    expect(commitBtn).toBeDefined()
    await commitBtn!.trigger('click')
    await flushPromises()

    expect(selfHealingCoreApi.commitPatch).toHaveBeenCalledWith('patch_test_123')
    expect(wrapper.emitted('committed')).toBeTruthy()
  })

  it('handles reject patch click', async () => {
    const wrapper = mount(SelfHealingDiffInspectionDrawer, {
      props: {
        open: true,
        patchData: samplePatch,
      },
      global: { stubs },
    })
    await flushPromises()

    const rejectBtn = wrapper.findAll('button').find((b) => b.text().includes('否决回滚'))
    expect(rejectBtn).toBeDefined()
    await rejectBtn!.trigger('click')
    await flushPromises()

    expect(selfHealingCoreApi.rejectPatch).toHaveBeenCalledWith('patch_test_123')
    expect(wrapper.emitted('rejected')).toBeTruthy()
  })
})
