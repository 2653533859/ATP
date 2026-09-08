import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import DeviceMatrixPanel from './DeviceMatrixPanel.vue'

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))

const buttonStub = defineComponent({
  emits: ['click'],
  setup: (_props, { emit, slots }) => () => h('button', { onClick: () => emit('click') }, slots.default?.()),
})

const popconfirmStub = defineComponent({
  emits: ['confirm'],
  setup: (_props, { emit, slots }) => () => h('div', {
    class: 'delete-confirm',
    onClick: () => emit('confirm'),
  }, slots.default?.()),
})

const passthrough = defineComponent({
  setup: (_props, { slots }) => () => h('div', slots.default?.()),
})

const emptyStub = defineComponent({
  props: ['description'],
  setup: (props) => () => h('div', String(props.description)),
})

const devices = [
  {
    id: 1,
    name: 'Pixel-7',
    brand: 'Google',
    model: 'Pixel 7',
    serial: 'PX7ABC',
    os_version: '14',
    resolution: '1080x2400',
    description: '实验室设备',
    status: 'online',
  },
  {
    id: 2,
    name: 'Busy device',
    brand: '',
    model: '',
    serial: 'BUSY-2',
    os_version: null,
    resolution: null,
    description: null,
    status: 'busy',
  },
  {
    id: 3,
    name: 'Offline device',
    brand: 'Samsung',
    model: 'S23',
    serial: 'OFF-3',
    os_version: '13',
    resolution: '1080x2340',
    description: null,
    status: 'offline',
  },
] as any[]

function mountPanel(items = devices) {
  return mount(DeviceMatrixPanel, {
    props: { devices: items },
    global: {
      stubs: {
        AButton: buttonStub,
        APopconfirm: popconfirmStub,
        ATooltip: passthrough,
        AEmpty: emptyStub,
        MobileOutlined: true,
      },
    },
  })
}

describe('DeviceMatrixPanel', () => {
  it('renders real device fields, status labels and unavailable-data placeholders', () => {
    const wrapper = mountPanel()

    expect(wrapper.findAll('.device-card-item')).toHaveLength(3)
    expect(wrapper.text()).toContain('Pixel 7')
    expect(wrapper.text()).toContain('空闲')
    expect(wrapper.text()).toContain('使用中')
    expect(wrapper.text()).toContain('离线')
    expect(wrapper.text()).toContain('品牌未上报')
    expect(wrapper.find('.user-val').text()).toBe('--')
    expect(wrapper.find('.agent-val').text()).toBe('--')
  })

  it('delegates edit, delete and online-use actions while blocking offline use', async () => {
    const wrapper = mountPanel()
    const cards = wrapper.findAll('.device-card-item')

    await cards[0].findAll('button')[0].trigger('click')
    await cards[0].find('.delete-confirm').trigger('click')
    await cards[0].find('.cta-use-btn').trigger('click')
    await cards[2].find('.cta-use-btn').trigger('click')

    expect(wrapper.emitted('edit')).toEqual([[devices[0]]])
    expect(wrapper.emitted('delete')).toEqual([[1]])
    expect(wrapper.emitted('use')).toEqual([[devices[0]]])
    expect(cards[2].find('.cta-use-btn').attributes('disabled')).toBeDefined()
  })

  it('renders the shared empty state when no devices match the filters', () => {
    const wrapper = mountPanel([])

    expect(wrapper.findAll('.device-card-item')).toHaveLength(0)
    expect(wrapper.find('.empty-matrix-card').exists()).toBe(true)
    expect(wrapper.text()).toContain('device.empty')
  })
})
