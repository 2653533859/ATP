import { describe, it, expect } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import BlastRadiusConfigModal from './BlastRadiusConfigModal.vue'

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
  'a-slider': {
    template: '<input type="range" class="ant-slider-stub" :value="value" @input="$emit(\'update:value\', Number($event.target.value))" />',
    props: ['value'],
  },
  'a-switch': {
    template: '<input type="checkbox" class="ant-switch-stub" :checked="checked" @change="$emit(\'update:checked\', $event.target.checked)" />',
    props: ['checked'],
  },
  'a-select': {
    template: '<div class="ant-select-stub"><slot /></div>',
    props: ['value'],
  },
}

describe('BlastRadiusConfigModal.vue', () => {
  it('renders modal banner stats and initial policy form fields', () => {
    const wrapper = mount(BlastRadiusConfigModal, {
      props: {
        open: true,
        experimentId: 'exp_payment_circuit_breaker',
      },
      global: { stubs },
    })

    expect(wrapper.find('.guardrail-metrics-banner').exists()).toBe(true)
    expect(wrapper.text()).toContain('允许波及服务上限')
    expect(wrapper.text()).toContain('全局错误率熔断红线')
    expect(wrapper.text()).toContain('P99 延迟绝对天花板')
    expect(wrapper.text()).toContain('越界保护动作')
  })

  it('renders initialPolicy when passed through props', () => {
    const wrapper = mount(BlastRadiusConfigModal, {
      props: {
        open: true,
        initialPolicy: {
          policy_id: 'pol_custom_99',
          experiment_id: 'exp_order_test',
          max_impacted_services: 4,
          max_error_rate_pct: 8.0,
          latency_ceiling_ms: 2000,
          auto_abort_enabled: false,
          exempt_tenant_ids: ['tenant_custom'],
        },
      },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('4')
    expect(wrapper.text()).toContain('8%')
    expect(wrapper.text()).toContain('2000ms')
    expect(wrapper.text()).toContain('仅边界报警')
  })

  it('emits testTriggerAbort when test button is clicked', async () => {
    const wrapper = mount(BlastRadiusConfigModal, {
      props: {
        open: true,
        experimentId: 'exp_test_run',
      },
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const testBtn = buttons.find(b => b.text().includes('测试越界看门狗回滚'))
    expect(testBtn).toBeDefined()
    await testBtn!.trigger('click')

    expect(wrapper.emitted('testTriggerAbort')).toBeTruthy()
  })

  it('emits save event with form state when save button is clicked', async () => {
    const wrapper = mount(BlastRadiusConfigModal, {
      props: {
        open: true,
        experimentId: 'exp_payment_circuit_breaker',
      },
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const saveBtn = buttons.find(b => b.text().includes('保存并应用安全围栏'))
    expect(saveBtn).toBeDefined()
    await saveBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.emitted('save')).toBeTruthy()
    const savedPolicy = wrapper.emitted('save')![0][0] as any
    expect(savedPolicy.max_error_rate_pct).toBe(5.0)
    expect(savedPolicy.max_impacted_services).toBe(2)
  })

  it('resets form to defaults when reset button is clicked', async () => {
    const wrapper = mount(BlastRadiusConfigModal, {
      props: {
        open: true,
        initialPolicy: {
          max_impacted_services: 9,
          max_error_rate_pct: 18.0,
        },
      },
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const resetBtn = buttons.find(b => b.text().includes('恢复默认推荐值'))
    expect(resetBtn).toBeDefined()
    await resetBtn!.trigger('click')

    expect(wrapper.text()).toContain('2')
    expect(wrapper.text()).toContain('5%')
  })
})
