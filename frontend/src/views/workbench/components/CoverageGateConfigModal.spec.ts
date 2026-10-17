import { describe, it, expect } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import CoverageGateConfigModal from './CoverageGateConfigModal.vue'

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

describe('CoverageGateConfigModal.vue', () => {
  it('renders modal banner stats and default policy configuration', () => {
    const wrapper = mount(CoverageGateConfigModal, {
      props: {
        open: true,
      },
      global: { stubs },
    })

    expect(wrapper.find('.gate-metrics-banner').exists()).toBe(true)
    expect(wrapper.text()).toContain('增量行覆盖率门槛')
    expect(wrapper.text()).toContain('85%')
    expect(wrapper.text()).toContain('70%')
    expect(wrapper.text()).toContain('P0 零容忍强阻断')
  })

  it('renders initialPolicy when passed through props', () => {
    const wrapper = mount(CoverageGateConfigModal, {
      props: {
        open: true,
        initialPolicy: {
          min_diff_line_coverage_pct: 90.0,
          min_diff_branch_coverage_pct: 80.0,
          allow_p0_uncovered: true,
          max_allowed_uncovered_lines: 5,
        },
      },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('90%')
    expect(wrapper.text()).toContain('80%')
    expect(wrapper.text()).toContain('允许豁免放行')
    expect(wrapper.text()).toContain('≤ 5 行')
  })

  it('emits exportCases when clicking export cases button', async () => {
    const wrapper = mount(CoverageGateConfigModal, {
      props: {
        open: true,
      },
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const exportBtn = buttons.find(b => b.text().includes('导出补测脚本草稿'))
    expect(exportBtn).toBeDefined()
    await exportBtn!.trigger('click')

    expect(wrapper.emitted('exportCases')).toBeTruthy()
    const cases = wrapper.emitted('exportCases')![0][0] as any[]
    expect(cases.length).toBeGreaterThan(0)
  })

  it('emits save event with form state when save button is clicked', async () => {
    const wrapper = mount(CoverageGateConfigModal, {
      props: {
        open: true,
      },
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const saveBtn = buttons.find(b => b.text().includes('保存并生效门禁策略'))
    expect(saveBtn).toBeDefined()
    await saveBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.emitted('save')).toBeTruthy()
    const savedPolicy = wrapper.emitted('save')![0][0] as any
    expect(savedPolicy.min_diff_line_coverage_pct).toBe(85.0)
    expect(savedPolicy.allow_p0_uncovered).toBe(false)
  })

  it('resets form to defaults when reset button is clicked', async () => {
    const wrapper = mount(CoverageGateConfigModal, {
      props: {
        open: true,
        initialPolicy: {
          min_diff_line_coverage_pct: 65.0,
        },
      },
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const resetBtn = buttons.find(b => b.text().includes('恢复推荐门禁值'))
    expect(resetBtn).toBeDefined()
    await resetBtn!.trigger('click')

    expect(wrapper.text()).toContain('85%')
  })
})
