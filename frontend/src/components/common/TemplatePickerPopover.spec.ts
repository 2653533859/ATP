import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import TemplatePickerPopover, { type TemplatePickerItem } from './TemplatePickerPopover.vue'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

const popoverStub = defineComponent({
  name: 'APopover',
  props: ['open'],
  setup: (_props, { slots }) => () => h('div', [slots.default?.(), h('div', { class: 'popover-content' }, slots.content?.())]),
})

const SAMPLE_ITEMS: TemplatePickerItem[] = [
  { id: 't1', label: '标准 REST GET', preview: 'GET /items', badge: 'GET', badgeTone: 'primary', group: '内置' },
  { id: 't2', label: '创建订单 POST', preview: '{"order_no": "123"}', badge: 'POST', badgeTone: 'success', group: '自定义', deletable: true },
  { id: 't3', label: 'Webhook 回调', preview: '{"event_id": "{{$uuid}}"}', badge: 'POST', badgeTone: 'success', group: '内置' },
]

function mountPicker(props: Record<string, unknown> = {}) {
  return mount(TemplatePickerPopover, {
    props: {
      items: SAMPLE_ITEMS,
      searchable: true,
      footerActionLabel: '+ Save Template',
      ...props,
    },
    slots: {
      default: '<button type="button" class="trigger-btn">Templates</button>',
    },
    global: {
      stubs: {
        APopover: popoverStub,
      },
    },
  })
}

describe('TemplatePickerPopover', () => {
  it('filters items by search keyword and group tabs', async () => {
    const wrapper = mountPicker()
    expect(wrapper.findAll('.tpl-picker-row')).toHaveLength(3)

    const tabs = wrapper.findAll('.tpl-picker-tab')
    expect(tabs.map((tab) => tab.text())).toEqual(['smart_json.picker_all_groups', '内置', '自定义'])

    await tabs[2].trigger('click')
    expect(wrapper.findAll('.tpl-picker-row')).toHaveLength(1)
    expect(wrapper.find('.tpl-picker-title').text()).toBe('创建订单 POST')

    await tabs[0].trigger('click')
    await wrapper.find('.tpl-picker-search').setValue('$uuid')
    expect(wrapper.findAll('.tpl-picker-row')).toHaveLength(1)
    expect(wrapper.find('.tpl-picker-title').text()).toBe('Webhook 回调')
  })

  it('emits select, delete (without selecting row), and footer-action cleanly', async () => {
    const wrapper = mountPicker()
    const rows = wrapper.findAll('.tpl-picker-row')

    await rows[1].find('.tpl-picker-del').trigger('click')
    expect(wrapper.emitted('delete')).toEqual([['t2']])
    expect(wrapper.emitted('select')).toBeUndefined()

    await rows[0].trigger('click')
    expect(wrapper.emitted('select')?.[0]?.[0]).toMatchObject({ id: 't1' })

    await wrapper.find('.tpl-picker-footer-btn').trigger('click')
    expect(wrapper.emitted('footer-action')).toHaveLength(1)
  })

  it('resets active group filter to all when the active group becomes empty', async () => {
    const wrapper = mountPicker()
    const tabs = wrapper.findAll('.tpl-picker-tab')
    await tabs[2].trigger('click')
    expect(wrapper.findAll('.tpl-picker-row')).toHaveLength(1)

    await wrapper.setProps({
      items: SAMPLE_ITEMS.filter((item) => item.group !== '自定义'),
    })
    expect(wrapper.findAll('.tpl-picker-row')).toHaveLength(2)
  })
})
