import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import LlmRedTeamConfigModal from './LlmRedTeamConfigModal.vue'

const stubs = {
  'a-modal': {
    template: `
      <div class="ant-modal-stub">
        <slot />
        <div class="ant-modal-footer-stub"><slot name="footer" /></div>
      </div>
    `,
    props: ['open', 'title'],
  },
  'a-button': { template: '<button class="ant-btn-stub" @click="$emit(\'click\')"><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-space': { template: '<div class="ant-space-stub"><slot /></div>' },
  'a-tabs': { template: '<div class="ant-tabs-stub"><slot /></div>' },
  'a-tab-pane': { template: '<div class="ant-tab-pane-stub"><slot /></div>' },
  'a-checkbox': {
    template: '<input type="checkbox" :checked="checked" @change="$emit(\'change\', $event)" />',
    props: ['checked'],
  },
  'a-divider': { template: '<hr />' },
  'a-row': { template: '<div class="ant-row-stub"><slot /></div>' },
  'a-col': { template: '<div class="ant-col-stub"><slot /></div>' },
  'a-form': { template: '<form class="ant-form-stub"><slot /></form>' },
  'a-form-item': { template: '<div class="ant-form-item-stub"><slot /></div>' },
  'a-input-number': { template: '<input type="number" :value="value" @input="$emit(\'update:value\', $event.target.value)" />', props: ['value'] },
  'a-select': { template: '<select :value="value"><slot /></select>', props: ['value'] },
  'a-select-option': { template: '<option :value="value"><slot /></option>', props: ['value'] },
  'a-radio-group': { template: '<div class="ant-radio-group-stub"><slot /></div>', props: ['value'] },
  'a-radio-button': { template: '<button class="ant-radio-button-stub"><slot /></button>', props: ['value'] },
  'a-switch': { template: '<input type="checkbox" :checked="checked" />', props: ['checked'] },
  'a-textarea': { template: '<textarea :value="value" />', props: ['value'] },
  'a-slider': { template: '<input type="range" :value="value" />', props: ['value'] },
}

describe('LlmRedTeamConfigModal.vue', () => {
  it('renders top summary banner with target model, operator count, and strictness', () => {
    const wrapper = mount(LlmRedTeamConfigModal, {
      props: {
        open: true,
        initialConfig: {
          target_model: 'deepseek-v3',
          enabled_operators: ['JAILBREAK_DAN', 'INSTRUCTION_OVERRIDE'],
          guardrail_strictness: 'STRICT',
          attack_rounds: 5,
        },
      },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('deepseek-v3')
    expect(wrapper.text()).toContain('2 / 6 种')
    expect(wrapper.text()).toContain('严苛模式 (阻断全部 PII)')
    expect(wrapper.text()).toContain('5 轮 / 算子')
  })

  it('renders 6 attack operator cards in the operators catalog', () => {
    const wrapper = mount(LlmRedTeamConfigModal, {
      props: { open: true },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('DAN 11.0 道德解锁')
    expect(wrapper.text()).toContain('内核特权指令覆盖')
    expect(wrapper.text()).toContain('底座提示词窃取探测')
    expect(wrapper.text()).toContain('Base64/ROT13 密文混淆')
    expect(wrapper.text()).toContain('剧本角色扮演催眠')
    expect(wrapper.text()).toContain('响应前缀强迫诱导')
  })

  it('toggles operator selection correctly on card click', async () => {
    const wrapper = mount(LlmRedTeamConfigModal, {
      props: {
        open: true,
        initialConfig: {
          enabled_operators: ['JAILBREAK_DAN'],
        },
      },
      global: { stubs },
    })

    const cards = wrapper.findAll('.operator-card')
    // Click second card to add INSTRUCTION_OVERRIDE
    await cards[1].trigger('click')

    const vm = wrapper.vm as unknown as { formState: { enabled_operators: string[] } }
    expect(vm.formState.enabled_operators).toContain('INSTRUCTION_OVERRIDE')
  })

  it('handles reset button and restores enterprise defaults', async () => {
    const wrapper = mount(LlmRedTeamConfigModal, {
      props: {
        open: true,
        initialConfig: {
          target_model: 'custom-model',
          attack_rounds: 10,
        },
      },
      global: { stubs },
    })

    const resetBtn = wrapper.findAll('.ant-btn-stub').find((b) => b.text().includes('恢复企业默认策略'))
    expect(resetBtn).toBeDefined()
    await resetBtn?.trigger('click')

    expect(wrapper.emitted('reset')).toBeTruthy()
    const vm = wrapper.vm as unknown as { formState: { target_model: string; attack_rounds: number } }
    expect(vm.formState.target_model).toBe('qwen-2.5-72b')
    expect(vm.formState.attack_rounds).toBe(3)
  })

  it('handles confirm and emits config object', async () => {
    const wrapper = mount(LlmRedTeamConfigModal, {
      props: {
        open: true,
        initialConfig: {
          target_model: 'deepseek-r1',
          attack_rounds: 4,
        },
      },
      global: { stubs },
    })

    const confirmBtn = wrapper.findAll('.ant-btn-stub').find((b) => b.text().includes('保存并触发红蓝对抗评测'))
    expect(confirmBtn).toBeDefined()
    await confirmBtn?.trigger('click')

    expect(wrapper.emitted('confirm')).toBeTruthy()
    const emittedConfig = wrapper.emitted('confirm')?.[0]?.[0] as { target_model: string; attack_rounds: number }
    expect(emittedConfig.target_model).toBe('deepseek-r1')
    expect(emittedConfig.attack_rounds).toBe(4)
  })
})
