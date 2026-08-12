import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import DeviceList from './DeviceList.vue'

const { deviceList, deviceWorkers, deviceScan, deviceScanStatus, deviceUpdate, deviceDelete, messageError, messageInfo, messageSuccess } = vi.hoisted(() => ({
  deviceList: vi.fn(),
  deviceWorkers: vi.fn(),
  deviceScan: vi.fn(),
  deviceScanStatus: vi.fn(),
  deviceUpdate: vi.fn(),
  deviceDelete: vi.fn(),
  messageError: vi.fn(),
  messageInfo: vi.fn(),
  messageSuccess: vi.fn(),
}))

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('ant-design-vue', () => ({ message: { error: messageError, info: messageInfo, success: messageSuccess } }))
vi.mock('@/api', () => ({
    deviceApi: {
      list: deviceList,
      workers: deviceWorkers,
      scan: deviceScan,
      scanStatus: deviceScanStatus,
      update: deviceUpdate,
    delete: deviceDelete,
    screenshot: vi.fn(),
  },
}))

const TableStub = defineComponent({
  name: 'ATable',
  props: ['dataSource'],
  setup(props, { slots }) {
    return () =>
      h(
        'div',
        (props.dataSource || []).map((record: Record<string, unknown>) =>
          h('div', { class: 'device-row' }, [
            slots.bodyCell?.({ column: { key: 'action' }, record }),
            slots.bodyCell?.({ column: { key: 'status' }, record }),
          ]),
        ),
      )
  },
})

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_p, { slots }) => () => h('div', slots.default?.()) })

function mountDeviceList() {
  return mount(DeviceList, {
    global: {
      stubs: {
        ATable: TableStub,
        AInputSearch: defineComponent({
          name: 'AInputSearch',
          props: ['value'],
          emits: ['update:value'],
          setup: (p, { emit }) => () => h('input', { 'data-test': 'search', value: p.value, onInput: (e: Event) => emit('update:value', (e.target as HTMLInputElement).value) }),
        }),
        AButton: defineComponent({
          name: 'AButton',
          emits: ['click'],
          setup: (_p, { slots, emit }) => () => h('button', { onClick: () => emit('click') }, slots.default?.()),
        }),
        AStatistic: defineComponent({
          name: 'AStatistic',
          props: ['value', 'title'],
          setup: (props) => () => h('span', { 'data-test': 'stat', 'data-title': props.title }, String(props.value)),
        }),
        ABadge: defineComponent({
          name: 'ABadge',
          props: ['status', 'text'],
          setup: (props) => () => h('span', { 'data-test': 'badge', 'data-status': props.status }, String(props.text)),
        }),
        APopconfirm: defineComponent({
          name: 'APopconfirm',
          emits: ['confirm'],
          setup: (_p, { slots, emit }) => () => h('div', { 'data-test': 'delete-confirm', onClick: () => emit('confirm') }, slots.default?.()),
        }),
        ARow: passthrough('ARow'),
        ACol: passthrough('ACol'),
        ACard: passthrough('ACard'),
        ASelect: passthrough('ASelect'),
        AModal: passthrough('AModal'),
        AForm: passthrough('AForm'),
        AFormItem: passthrough('AFormItem'),
        AInput: passthrough('AInput'),
        ATextarea: passthrough('ATextarea'),
        ASpace: passthrough('ASpace'),
        ReloadOutlined: true,
        EyeOutlined: true,
      },
    },
  })
}

const DEVICES = [
  { id: 1, name: 'Pixel-7', brand: 'Google', model: 'Pixel 7', serial: 'PX7ABC', os_version: 'Android 14', resolution: '1080x2400', status: 'online', last_seen: '2026-07-10T09:00:00Z' },
  { id: 2, name: 'Galaxy-S23', brand: 'Samsung', model: 'S23', serial: 'SGS23X', os_version: 'Android 13', resolution: '1080x2340', status: 'offline', last_seen: '2026-07-09T08:00:00Z' },
  { id: 3, name: 'Mi-13', brand: 'Xiaomi', model: 'Mi13', serial: 'MI13YZ', os_version: 'Android 13', resolution: '1440x3200', status: 'busy', last_seen: '2026-07-08T07:00:00Z' },
]

beforeEach(() => {
  vi.clearAllMocks()
  deviceList.mockResolvedValue(DEVICES)
  deviceWorkers.mockResolvedValue([])
  deviceScan.mockResolvedValue({ status: 'completed', scan_id: null, devices: DEVICES })
  deviceScanStatus.mockResolvedValue({ status: 'completed', scan_id: 'scan-id', devices: DEVICES })
  deviceUpdate.mockResolvedValue({})
  deviceDelete.mockResolvedValue({})
})

describe('DeviceList mount', () => {
  it('loads devices on mount and renders status stats and badges', async () => {
    const wrapper = mountDeviceList()
    await flushPromises()

    expect(deviceList).toHaveBeenCalledWith(undefined)
    const stats = wrapper.findAll('[data-test="stat"]').map((s) => s.text())
    expect(stats).toContain('1') // online / busy / offline 各 1
    const badges = wrapper.findAll('[data-test="badge"]').map((b) => b.attributes('data-status'))
    expect(badges).toEqual(expect.arrayContaining(['success', 'default', 'processing']))
  })

  it('filters devices by keyword across name/brand/model/serial', async () => {
    const wrapper = mountDeviceList()
    await flushPromises()

    await wrapper.find('[data-test="search"]').setValue('samsung')
    await flushPromises()
    expect(wrapper.findAll('.device-row')).toHaveLength(1)

    await wrapper.find('[data-test="search"]').setValue('MI13YZ') // 按序列号
    await flushPromises()
    expect(wrapper.findAll('.device-row')).toHaveLength(1)

    await wrapper.find('[data-test="search"]').setValue('')
    await flushPromises()
    expect(wrapper.findAll('.device-row')).toHaveLength(3)
  })

  it('scans for devices and surfaces the result count', async () => {
    const wrapper = mountDeviceList()
    await flushPromises()

    // header 的第一个按钮是 scan
    await wrapper.findAll('button')[0].trigger('click')
    await flushPromises()

    expect(deviceScan).toHaveBeenCalledOnce()
    expect(messageSuccess).toHaveBeenCalled()
  })

  it('polls a queued Android Worker scan before reporting completion', async () => {
    vi.useFakeTimers()
    try {
      deviceScan.mockResolvedValue({ status: 'queued', scan_id: '550e8400-e29b-41d4-a716-446655440000', devices: [] })
      deviceScanStatus
        .mockResolvedValueOnce({ status: 'running', scan_id: 'scan-id', devices: [] })
        .mockResolvedValueOnce({ status: 'completed', scan_id: 'scan-id', devices: DEVICES })

      const wrapper = mountDeviceList()
      await flushPromises()
      const clickPromise = wrapper.findAll('button')[0].trigger('click')
      await flushPromises()
      expect(messageInfo).toHaveBeenCalled()

      await vi.advanceTimersByTimeAsync(500)
      await flushPromises()
      await vi.advanceTimersByTimeAsync(500)
      await clickPromise

      expect(deviceScanStatus).toHaveBeenCalledWith('550e8400-e29b-41d4-a716-446655440000')
      expect(messageSuccess).toHaveBeenCalled()
    } finally {
      vi.useRealTimers()
    }
  })

  it('deletes a device via the row action and reloads', async () => {
    const wrapper = mountDeviceList()
    await flushPromises()
    deviceList.mockClear()

    await wrapper.find('[data-test="delete-confirm"]').trigger('click')
    await flushPromises()

    expect(deviceDelete).toHaveBeenCalledWith(1)
    expect(messageSuccess).toHaveBeenCalled()
    expect(deviceList).toHaveBeenCalled()
  })

  it('surfaces a message when device load fails', async () => {
    deviceList.mockRejectedValueOnce(new Error('adb down'))
    mountDeviceList()
    await flushPromises()
    expect(messageError).toHaveBeenCalled()
  })
})
