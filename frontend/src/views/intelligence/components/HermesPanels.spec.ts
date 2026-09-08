import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import dayjs from 'dayjs'

import HermesConversationContextPanel from './HermesConversationContextPanel.vue'
import HermesGovernancePanel from './HermesGovernancePanel.vue'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => `${key}${params ? `:${JSON.stringify(params)}` : ''}`,
  }),
}))

vi.mock('@ant-design/icons-vue', () => ({
  PlusOutlined: { setup: () => () => null },
}))

const selectStub = defineComponent({
  name: 'ASelect',
  props: ['value'],
  emits: ['update:value'],
  setup: () => () => h('div'),
})

const rangePickerStub = defineComponent({
  name: 'ARangePicker',
  props: ['value'],
  emits: ['update:value'],
  setup: () => () => h('div'),
})

const buttonStub = defineComponent({
  name: 'AButton',
  emits: ['click'],
  setup: (_props, { emit, slots }) => () => h('button', { onClick: () => emit('click') }, slots.default?.()),
})

describe('Hermes extracted panels', () => {
  it('renders governance rates and unavailable cost state', () => {
    const wrapper = mount(HermesGovernancePanel, {
      props: {
        summary: {
          prompt_version: 'hermes-v2',
          prompt_versions: ['hermes-v2'],
          evaluation_set: { id: 'core', version: '2026-09-01', size: 5 },
          sessions: 2,
          assistant_messages: 3,
          citation_coverage: 0.8,
          refusal_rate: 0.2,
          no_result_rate: 0.1,
          helpful_count: 0,
          not_helpful_count: 0,
          feedback_total: 0,
          helpful_rate: null,
          average_latency_ms: 120,
          p95_latency_ms: 220,
          cost_tracking: { available: false, reason: 'not configured' },
        },
      },
    })

    expect(wrapper.text()).toContain('80%')
    expect(wrapper.text()).toContain('20%')
    expect(wrapper.text()).toContain('—')
    expect(wrapper.find('.governance-cost-note').exists()).toBe(true)
  })

  it('forwards conversation filters and emits the new conversation action', async () => {
    const wrapper = mount(HermesConversationContextPanel, {
      props: {
        shortConversationId: 'session1',
        sourceTypes: [],
        dateRange: undefined,
        contextBudget: 6_000,
        sourceTypeOptions: [{ label: 'Knowledge', value: 'knowledge' }],
        contextBudgetOptions: [{ label: '6000', value: 6_000 }],
        historyUsed: 2,
        historyOmitted: 1,
        contextChars: 320,
      },
      global: {
        stubs: {
          AButton: buttonStub,
          ASelect: selectStub,
          ARangePicker: rangePickerStub,
        },
      },
    })

    const selects = wrapper.findAllComponents(selectStub)
    const range = [dayjs('2026-09-01'), dayjs('2026-09-08')] as const
    selects[0].vm.$emit('update:value', ['knowledge'])
    selects[1].vm.$emit('update:value', 8_000)
    wrapper.findComponent(rangePickerStub).vm.$emit('update:value', range)
    await wrapper.find('button').trigger('click')

    expect(wrapper.emitted('update:sourceTypes')?.[0]).toEqual([['knowledge']])
    expect(wrapper.emitted('update:contextBudget')?.[0]).toEqual([8_000])
    expect(wrapper.emitted('update:dateRange')?.[0]).toEqual([range])
    expect(wrapper.emitted('new-conversation')).toHaveLength(1)
  })
})
