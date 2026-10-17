import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import TestSelfHealingWorkbenchView from './TestSelfHealingWorkbenchView.vue'
import { selfHealingCoreApi } from '@/api/testSelfHealing'

vi.mock('@/api/testSelfHealing', () => ({
  selfHealingCoreApi: {
    listPatches: vi.fn().mockResolvedValue({
      total: 2,
      patches: [
        {
          patch_id: 'patch_mock_1',
          case_id: 'case_cart_01',
          step_id: 'step_btn_cart',
          status: 'APPLIED_IN_FLIGHT',
          confidence: 0.965,
          strategy_tier: 'TIER_1_ID_VARIATION',
          broken_context: {
            failed_locator_value: '#btn_old_cart',
          },
          best_candidate: {
            recommended_locator_value: "button[data-action='cart']",
          },
        },
      ],
    }),
    commitPatch: vi.fn().mockResolvedValue({ message: 'ok', patch: {} }),
    rejectPatch: vi.fn().mockResolvedValue({ message: 'ok', patch: {} }),
  },
}))

const stubs = {
  'a-button': { template: '<button><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-space': { template: '<div class="ant-space-stub"><slot /></div>' },
  'a-tabs': { template: '<div class="ant-tabs-stub"><slot /></div>' },
  'a-tab-pane': { props: ['tab'], template: '<div class="ant-tab-pane-stub"><span>{{ tab }}</span><slot /></div>' },
  'a-radio-group': { template: '<div class="ant-radio-group-stub"><slot /></div>' },
  'a-radio-button': { template: '<button class="ant-radio-button-stub"><slot /></button>' },
  'a-input-search': { template: '<input class="ant-input-search-stub" />' },
  'a-drawer': { template: '<div class="ant-drawer-stub"><slot /></div>' },
  'a-modal': { template: '<div class="ant-modal-stub"><slot /><slot name="footer" /></div>' },
  'a-textarea': { template: '<textarea class="ant-textarea-stub" />' },
}

describe('TestSelfHealingWorkbenchView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders page header and 4 Bento KPI cards', async () => {
    const wrapper = mount(TestSelfHealingWorkbenchView, {
      global: { stubs },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('AI 用例自愈与断言演进工作台中枢')
    expect(wrapper.text()).toContain('92.4%')
    expect(wrapper.text()).toContain('多模态自愈综合成功率')
    expect(wrapper.text()).toContain('定位器自愈记录数')
    expect(wrapper.text()).toContain('断言漂移演进条数')
    expect(wrapper.text()).toContain('安全沙箱围栏拦截')
  })

  it('renders workbench tabs and table contents', async () => {
    const wrapper = mount(TestSelfHealingWorkbenchView, {
      global: { stubs },
    })
    await flushPromises()

    expect(selfHealingCoreApi.listPatches).toHaveBeenCalled()
    expect(wrapper.text()).toContain('UI 定位器动态自愈补丁大盘')
    expect(wrapper.text()).toContain('接口响应漂移与语义断言演进大盘')
  })

  it('opens diff inspection drawer when trigger diagnose is clicked', async () => {
    const wrapper = mount(TestSelfHealingWorkbenchView, {
      global: { stubs },
    })
    await flushPromises()

    const diagBtn = wrapper.findAll('button').find((b) => b.text().includes('实时定位自愈诊断'))
    expect(diagBtn).toBeDefined()
    await diagBtn!.trigger('click')
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.diffDrawerOpen).toBe(true)
    expect(vm.selectedPatch).toBeDefined()
  })
})
