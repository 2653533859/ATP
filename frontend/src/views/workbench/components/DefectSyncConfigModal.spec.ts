import { describe, it, expect } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import DefectSyncConfigModal from './DefectSyncConfigModal.vue'

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
  'a-input-password': {
    template: '<input type="password" class="ant-input-password-stub" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
    props: ['value'],
  },
  'a-input-number': {
    template: '<input type="number" class="ant-input-number-stub" :value="value" @input="$emit(\'update:value\', Number($event.target.value))" />',
    props: ['value'],
  },
  'a-switch': {
    template: '<input type="checkbox" class="ant-switch-stub" :checked="checked" @change="$emit(\'update:checked\', $event.target.checked)" />',
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
  'a-divider': { template: '<hr />' },
}

describe('DefectSyncConfigModal.vue', () => {
  it('renders modal banner stats and default sync configuration', () => {
    const wrapper = mount(DefectSyncConfigModal, {
      props: {
        open: true,
      },
      global: { stubs },
    })

    expect(wrapper.find('.sync-metrics-banner').exists()).toBe(true)
    expect(wrapper.text()).toContain('Jira 双向工单联动')
    expect(wrapper.text()).toContain('P0 故障解决 SLA')
    expect(wrapper.text()).toContain('24h')
    expect(wrapper.text()).toContain('48h')
    expect(wrapper.text()).toContain('智能 Reopen 激活')
  })

  it('renders initialConfig when passed through props', () => {
    const wrapper = mount(DefectSyncConfigModal, {
      props: {
        open: true,
        initialConfig: {
          primary_platform: 'GITHUB',
          project_key: 'MY_REPO',
          p0_resolution_hours: 12,
          auto_reopen_on_fail: false,
        },
      },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('12h')
    expect(wrapper.text()).toContain('仅手动管理')
  })

  it('emits testConnection when clicking test connection button', async () => {
    const wrapper = mount(DefectSyncConfigModal, {
      props: {
        open: true,
      },
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const testBtn = buttons.find(b => b.text().includes('测试外部平台连通性'))
    expect(testBtn).toBeDefined()
    await testBtn!.trigger('click')

    expect(wrapper.emitted('testConnection')).toBeTruthy()
    expect(wrapper.emitted('testConnection')![0]).toEqual(['JIRA'])
  })

  it('emits save event with form state when save button is clicked', async () => {
    const wrapper = mount(DefectSyncConfigModal, {
      props: {
        open: true,
      },
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const saveBtn = buttons.find(b => b.text().includes('保存并生效策略'))
    expect(saveBtn).toBeDefined()
    await saveBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.emitted('save')).toBeTruthy()
    const savedConfig = wrapper.emitted('save')![0][0] as any
    expect(savedConfig.p0_resolution_hours).toBe(24)
    expect(savedConfig.auto_reopen_on_fail).toBe(true)
  })

  it('resets form to defaults when reset button is clicked', async () => {
    const wrapper = mount(DefectSyncConfigModal, {
      props: {
        open: true,
        initialConfig: {
          p0_resolution_hours: 6,
        },
      },
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const resetBtn = buttons.find(b => b.text().includes('恢复标准推荐配置'))
    expect(resetBtn).toBeDefined()
    await resetBtn!.trigger('click')

    expect(wrapper.text()).toContain('24h')
  })
})
