import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import WebRecorderModal from './WebRecorderModal.vue'

const { recordingStart, recordingStop, messageWarning } = vi.hoisted(() => ({
  recordingStart: vi.fn(),
  recordingStop: vi.fn(),
  messageWarning: vi.fn(),
}))

vi.mock('@/api', () => ({
  webRecordingApi: {
    start: recordingStart,
    get: vi.fn(),
    screenshot: vi.fn(),
    stop: recordingStop,
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

vi.mock('ant-design-vue', () => ({
  message: {
    warning: messageWarning,
  },
}))

const Passthrough = {
  template: '<div><slot /></div>',
}

function mountRecorder() {
  return mount(WebRecorderModal, {
    props: {
      open: true,
      projectId: 1,
      autoApply: true,
    },
    global: {
      stubs: Object.fromEntries([
        'AModal', 'AForm', 'AFormItem', 'AInput', 'ASelect', 'ASelectOption', 'AAlert', 'AEmpty', 'AList', 'AListItem', 'ATag', 'AButton',
      ].map((name) => [name, Passthrough])),
    },
  })
}

describe('WebRecorderModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not auto-apply steps when stopping the recording fails', async () => {
    recordingStop.mockRejectedValue(new Error('录制会话不存在'))
    const wrapper = mountRecorder()
    const vm = wrapper.vm as any
    vm.recordingId = 'recording-1'
    vm.status = 'recording'
    vm.steps = [{ action: 'click', name: 'Click submit', params: {} }]

    await vm.stopRecording()
    await flushPromises()

    expect(recordingStop).toHaveBeenCalledWith('recording-1')
    expect(vm.status).toBe('error')
    expect(vm.error).toBe('录制会话不存在')
    expect(wrapper.emitted('recorded')).toBeUndefined()
    expect(wrapper.emitted('close')).toBeUndefined()
    wrapper.unmount()
  })

  it('passes the selected Playwright browser to the recording API', async () => {
    recordingStart.mockResolvedValue({ id: 'recording-1', status: 'recording', steps: [] })
    const wrapper = mountRecorder()
    const vm = wrapper.vm as any
    vm.startUrl = 'https://example.com'
    vm.browser = 'firefox'

    await vm.startRecording()
    await flushPromises()

    expect(recordingStart).toHaveBeenCalledWith({
      start_url: 'https://example.com',
      project_id: 1,
      browser: 'firefox',
    })
    wrapper.unmount()
  })
})
