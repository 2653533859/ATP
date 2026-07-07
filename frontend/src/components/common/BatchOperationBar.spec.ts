import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import BatchOperationBar from './BatchOperationBar.vue'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, number>) => {
      if (key === 'common.selected_count') return `selected ${params?.count ?? 0}`
      if (key === 'common.cancel_selection') return 'cancel'
      return key
    },
  }),
}))

describe('BatchOperationBar', () => {
  it('stays hidden when nothing is selected', () => {
    const wrapper = mount(BatchOperationBar, {
      props: { selectedCount: 0 },
      global: {
        stubs: {
          ASpace: { template: '<div><slot /></div>' },
          AButton: { template: '<button><slot /></button>' },
        },
      },
    })

    expect(wrapper.find('.batch-bar').exists()).toBe(false)
  })

  it('renders selected count, slot actions, and emits cancel', async () => {
    const wrapper = mount(BatchOperationBar, {
      props: { selectedCount: 3 },
      slots: {
        default: '<button class="bulk-action">Delete</button>',
      },
      global: {
        stubs: {
          ASpace: { template: '<div class="space"><slot /></div>' },
          AButton: { template: '<button class="cancel"><slot /></button>' },
        },
      },
    })

    expect(wrapper.find('.batch-bar-count').text()).toBe('selected 3')
    expect(wrapper.find('.bulk-action').exists()).toBe(true)

    await wrapper.find('.cancel').trigger('click')

    expect(wrapper.emitted('cancel')).toHaveLength(1)
  })
})
