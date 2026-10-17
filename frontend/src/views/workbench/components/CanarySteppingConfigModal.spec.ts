import { describe, it, expect } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import CanarySteppingConfigModal from './CanarySteppingConfigModal.vue'

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
}

describe('CanarySteppingConfigModal.vue', () => {
  it('renders modal banner stats and default stepping configuration', () => {
    const wrapper = mount(CanarySteppingConfigModal, {
      props: {
        open: true,
        targetService: 'order-service',
      },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('order-service')
    expect(wrapper.text()).toContain('5% 探针')
    expect(wrapper.text()).toContain('+2%')
    expect(wrapper.text()).toContain('秒级熔断已激活')
  })

  it('renders initialConfig when passed through props', () => {
    const customConfig = {
      initial_probe_weight_pct: 10.0,
      min_observation_requests: 1000,
      max_error_rate_diff_pct: 1.5,
      auto_rollback_enabled: false,
    }

    const wrapper = mount(CanarySteppingConfigModal, {
      props: {
        open: true,
        targetService: 'payment-service',
        initialConfig: customConfig,
      },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('10% 探针')
    expect(wrapper.text()).toContain('+1.5%')
    expect(wrapper.text()).toContain('仅告警不切流')
  })

  it('emits save event with form state when save button is clicked', async () => {
    const wrapper = mount(CanarySteppingConfigModal, {
      props: {
        open: true,
        targetService: 'payment-service',
      },
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const saveBtn = buttons.find((b) => b.text().includes('保存配置并立即下发生效'))
    expect(saveBtn).toBeDefined()
    await saveBtn!.trigger('click')

    expect(wrapper.emitted('save')).toBeTruthy()
    const emittedConfig = wrapper.emitted('save')![0][0] as any
    expect(emittedConfig.initial_probe_weight_pct).toBe(5.0)
    expect(emittedConfig.max_error_rate_diff_pct).toBe(2.0)
    expect(emittedConfig.auto_rollback_enabled).toBe(true)
  })

  it('resets form to defaults when reset button is clicked', async () => {
    const wrapper = mount(CanarySteppingConfigModal, {
      props: {
        open: true,
        targetService: 'payment-service',
        initialConfig: {
          initial_probe_weight_pct: 20.0,
        },
      },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('20% 探针')

    const buttons = wrapper.findAll('.ant-btn-stub')
    const resetBtn = buttons.find((b) => b.text().includes('重置为企业推荐默认值'))
    expect(resetBtn).toBeDefined()
    await resetBtn!.trigger('click')

    await flushPromises()
    expect(wrapper.emitted('reset')).toBeTruthy()
    expect(wrapper.text()).toContain('5% 探针')
  })
})
