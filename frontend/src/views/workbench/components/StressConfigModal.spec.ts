import { describe, it, expect } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import StressConfigModal from './StressConfigModal.vue'

const stubs = {
  'a-modal': {
    template: '<div class="ant-modal-stub"><slot /><slot name="footer" /></div>',
  },
  'a-button': {
    template: '<button class="ant-btn-stub" @click="$emit(\'click\')"><slot /></button>',
  },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-space': { template: '<div class="ant-space-stub"><slot /></div>' },
  'a-row': { template: '<div class="ant-row-stub"><slot /></div>' },
  'a-col': { template: '<div class="ant-col-stub"><slot /></div>' },
  'a-tabs': {
    template: '<div class="ant-tabs-stub"><slot /></div>',
    props: ['activeKey'],
  },
  'a-tab-pane': {
    template: '<div class="ant-tab-pane-stub"><slot /></div>',
    props: ['tab', 'key'],
  },
  'a-form': { template: '<form class="ant-form-stub"><slot /></form>' },
  'a-form-item': { template: '<div class="ant-form-item-stub"><slot /></div>' },
  'a-input': {
    template: '<input class="ant-input-stub" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
    props: ['value'],
  },
  'a-input-number': {
    template: '<input type="number" class="ant-input-number-stub" :value="value" @input="$emit(\'update:value\', Number($event.target.value))" />',
    props: ['value'],
  },
  'a-switch': {
    template: '<button class="ant-switch-stub" @click="$emit(\'update:checked\', !checked)"><slot /></button>',
    props: ['checked'],
  },
  'a-select': {
    template: '<select class="ant-select-stub"><slot /></select>',
    props: ['value'],
  },
  'a-select-option': {
    template: '<option :value="value"><slot /></option>',
    props: ['value'],
  },
}

describe('StressConfigModal.vue', () => {
  it('renders modal banner stats with calculated peak VU and worker count', () => {
    const wrapper = mount(StressConfigModal, {
      props: {
        open: true,
        targetService: 'order-service',
      },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('order-service')
    // 默认 500 + (5 - 1) * 1000 = 4500 VU
    expect(wrapper.text()).toContain('4500 VU')
    // 4500 / 2000 = 3 节点
    expect(wrapper.text()).toContain('3 节点')
    expect(wrapper.text()).toContain('秒级断路已激活')
  })

  it('renders initialConfig when passed through props', () => {
    const customConfig = {
      initial_vu: 1000,
      step_vu: 2000,
      steps_count: 3,
      max_error_rate_pct: 0.5,
      auto_circuit_break_enabled: false,
    }

    const wrapper = mount(StressConfigModal, {
      props: {
        open: true,
        targetService: 'payment-service',
        initialConfig: customConfig,
      },
      global: { stubs },
    })

    // 1000 + (3 - 1) * 2000 = 5000 VU
    expect(wrapper.text()).toContain('5000 VU')
    expect(wrapper.text()).toContain('仅报警不断流')
  })

  it('emits save event with form state when save button is clicked', async () => {
    const wrapper = mount(StressConfigModal, {
      props: {
        open: true,
        targetService: 'payment-service',
      },
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const saveBtn = buttons.find((b) => b.text().includes('保存配置并生成发压作业'))
    expect(saveBtn).toBeDefined()
    await saveBtn!.trigger('click')

    expect(wrapper.emitted('save')).toBeTruthy()
    const emittedConfig = wrapper.emitted('save')![0][0] as any
    expect(emittedConfig.initial_vu).toBe(500)
    expect(emittedConfig.max_error_rate_pct).toBe(1.0)
    expect(emittedConfig.auto_circuit_break_enabled).toBe(true)
  })

  it('resets form to defaults when reset button is clicked', async () => {
    const wrapper = mount(StressConfigModal, {
      props: {
        open: true,
        targetService: 'payment-service',
        initialConfig: {
          initial_vu: 2000,
          steps_count: 6,
        },
      },
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const resetBtn = buttons.find((b) => b.text().includes('重置为推荐默认值'))
    expect(resetBtn).toBeDefined()
    await resetBtn!.trigger('click')

    await flushPromises()
    expect(wrapper.emitted('reset')).toBeTruthy()
    expect(wrapper.text()).toContain('4500 VU')
  })
})
