import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AndroidStepEditor from './AndroidStepEditor.vue'

const { packages, refreshPackages } = vi.hoisted(() => ({ packages: vi.fn(), refreshPackages: vi.fn() }))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))
vi.mock('ant-design-vue', () => ({
  message: { warning: vi.fn(), success: vi.fn(), error: vi.fn() },
}))
vi.mock('@/api', () => ({
  deviceApi: { packages, refreshPackages },
}))

const draggableStub = defineComponent({
  name: 'draggable',
  props: ['modelValue'],
  setup(props, { slots }) {
    return () =>
      h(
        'div',
        (props.modelValue as Array<Record<string, unknown>>).map((element, index) =>
          slots.item?.({ element, index }),
        ),
      )
  },
})

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

const globalStubs = {
  draggable: draggableStub,
  AAutoComplete: passthrough('AAutoComplete'),
  AAlert: passthrough('AAlert'),
  AButton: passthrough('AButton'),
  ACard: passthrough('ACard'),
  AEmpty: passthrough('AEmpty'),
  AFormItem: passthrough('AFormItem'),
  AInput: passthrough('AInput'),
  AInputNumber: passthrough('AInputNumber'),
  ARow: passthrough('ARow'),
  ACol: passthrough('ACol'),
  ASelect: passthrough('ASelect'),
  ASelectOption: passthrough('ASelectOption'),
  ASpin: passthrough('ASpin'),
}

function mountEditor(deviceId: number | null = 5) {
  return mount(AndroidStepEditor, {
    props: {
      modelValue: [{ action: 'start_app', name: '启动应用', params: { package: '' } }],
      deviceId,
    },
    global: { stubs: globalStubs },
  })
}

describe('AndroidStepEditor package suggestions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    packages.mockResolvedValue({
      device_id: 5,
      serial: '172.16.101.11:5555',
      current_package: 'com.hopesen.aiphytraining',
      current_activity: '.view.list.ExaminationListActivity',
      packages: ['com.hopesen.aiphytraining', 'com.mgtv.tv'],
      read_at: '2026-11-12T09:30:00Z',
      stale: false,
      source: 'refresh',
    })
  })

  it('合入当前选择设备的已安装包名，并标记前台应用', async () => {
    const wrapper = mountEditor(5)
    await flushPromises()

    expect(packages).toHaveBeenCalledWith(5)
    const options = wrapper.vm.packageOptions
    expect(options.map((option) => option.value)).toEqual(['com.hopesen.aiphytraining', 'com.mgtv.tv'])
    expect(options[0].label).toContain('case.android_editor.device_foreground_tag')
    wrapper.unmount()
  })

  it('未选择设备时不请求包名，读取失败时静默降级', async () => {
    const withoutDevice = mountEditor(null)
    await flushPromises()
    expect(packages).not.toHaveBeenCalled()
    withoutDevice.unmount()

    packages.mockRejectedValue(new Error('device offline'))
    const failed = mountEditor(5)
    await flushPromises()
    expect(failed.vm.devicePackages).toEqual([])
    expect(failed.find('.step-card').exists()).toBe(true)
    failed.unmount()
  })
})
