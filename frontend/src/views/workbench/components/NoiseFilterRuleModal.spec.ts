import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import NoiseFilterRuleModal from './NoiseFilterRuleModal.vue'
import { trafficReplayApi } from '@/api/trafficReplay'

vi.mock('@/api/trafficReplay', () => ({
  trafficReplayApi: {
    testNoiseRule: vi.fn().mockResolvedValue({
      matched: true,
      reason: '命中规则通配模式',
      rule_summary: {},
    }),
  },
}))

const stubs = {
  'a-modal': { props: ['title'], template: '<div class="ant-modal-stub"><h3>{{ title }}</h3><slot /><slot name="footer" /></div>' },
  'a-button': { template: '<button><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-space': { template: '<div class="ant-space-stub"><slot /></div>' },
  'a-form': { template: '<form><slot /></form>' },
  'a-form-item': { template: '<div class="ant-form-item-stub"><slot /></div>' },
  'a-select': { template: '<select><slot /></select>' },
  'a-select-option': { template: '<option><slot /></option>' },
  'a-switch': { template: '<input type="checkbox" class="ant-switch-stub" />' },
  'a-input': {
    props: ['value'],
    template: '<input :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
  },
}

describe('NoiseFilterRuleModal.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders modal with title and quick templates', async () => {
    const wrapper = mount(NoiseFilterRuleModal, {
      props: { open: true },
      global: { stubs },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('动态噪声过滤规则配置与仿真校验弹窗')
    expect(wrapper.text()).toContain('常用噪声模板')
    expect(wrapper.text()).toContain('任意时间戳')
    expect(wrapper.text()).toContain('32位 TraceID')
  })

  it('runs live simulation verification', async () => {
    const wrapper = mount(NoiseFilterRuleModal, {
      props: {
        open: true,
        initialRule: {
          name: '忽略 TraceID 噪声',
          path_pattern: '*.trace_id',
          noise_type: 'TRACE_ID',
        },
      },
      global: { stubs },
    })
    await flushPromises()

    const verifyBtn = wrapper.findAll('button').find((b) => b.text().includes('即时验证'))
    expect(verifyBtn).toBeDefined()
    await verifyBtn!.trigger('click')
    await flushPromises()

    expect(trafficReplayApi.testNoiseRule).toHaveBeenCalled()
    expect(wrapper.text()).toContain('命中降噪规则')
  })

  it('saves rule and emits saved event', async () => {
    const wrapper = mount(NoiseFilterRuleModal, {
      props: {
        open: true,
        initialRule: {
          name: '忽略时间戳',
          path_pattern: '*timestamp*',
          noise_type: 'TIMESTAMP',
        },
      },
      global: { stubs },
    })
    await flushPromises()

    const saveBtn = wrapper.findAll('button').find((b) => b.text().includes('保存规则'))
    expect(saveBtn).toBeDefined()
    await saveBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.emitted('saved')).toBeTruthy()
  })
})
