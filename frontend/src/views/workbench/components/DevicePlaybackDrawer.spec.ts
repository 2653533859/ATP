import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DevicePlaybackDrawer from './DevicePlaybackDrawer.vue'

const mockInitResponse = {
  session_id: 'pb_sess_test_901',
  platform: 'android',
  device_id: 1,
  serial_or_udid: 'emulator-5554',
  target_app: 'com.example.app',
  status: 'running',
  created_at: '2026-10-16T10:00:00Z',
  total_steps: 0,
  passed_steps: 0,
  failed_steps: 0,
  healed_steps: 0,
  step_records: [],
}

const mockStepResponse = {
  step_no: 1,
  action: 'click',
  params: { resource_id: 'btn_search', text: '搜索' },
  status: 'passed',
  duration_ms: 120,
  healed: false,
}

const mockTeardownResponse = {
  ...mockInitResponse,
  status: 'teardown',
}

const mockInitSession = vi.fn().mockResolvedValue(mockInitResponse)
const mockExecuteStep = vi.fn().mockResolvedValue(mockStepResponse)
const mockTeardownSession = vi.fn().mockResolvedValue(mockTeardownResponse)
const mockGetSession = vi.fn().mockResolvedValue({
  ...mockInitResponse,
  total_steps: 1,
  passed_steps: 1,
  step_records: [mockStepResponse],
})

vi.mock('@/api/devicePlayback', () => ({
  devicePlaybackApi: {
    initSession: (data: unknown) => mockInitSession(data),
    executeStep: (id: string, data: unknown) => mockExecuteStep(id, data),
    teardownSession: (id: string) => mockTeardownSession(id),
    getSession: (id: string) => mockGetSession(id),
  },
}))

const globalStubs = {
  'a-drawer': { template: '<div class="ant-drawer"><slot name="title" /><slot /></div>' },
  'a-card': { template: '<div class="ant-card"><h4>{{ $attrs.title }}</h4><slot /><slot name="extra" /></div>' },
  'a-button': { template: '<button class="ant-btn"><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
  'a-form': { template: '<form><slot /></form>' },
  'a-form-item': { template: '<div class="form-item"><slot /></div>' },
  'a-input': { template: '<input />' },
  'a-textarea': { template: '<textarea />' },
  'a-select': { template: '<select><slot /></select>' },
  'a-select-option': { template: '<option><slot /></option>' },
  'a-space': { template: '<div><slot /></div>' },
  'a-row': { template: '<div class="ant-row"><slot /></div>' },
  'a-col': { template: '<div class="ant-col"><slot /></div>' },
  'a-table': {
    props: ['dataSource'],
    template: `
      <div class="ant-table">
        <div v-for="item in dataSource" :key="item.step_no" class="table-row">
          <span>步骤 #{{ item.step_no }}</span>
          <span>{{ item.action }}</span>
          <span>{{ item.status }}</span>
        </div>
      </div>
    `,
  },
}

describe('DevicePlaybackDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders drawer header, control inputs, and initial state', () => {
    const wrapper = mount(DevicePlaybackDrawer, {
      props: {
        open: true,
        deviceId: 1,
        serialOrUdid: 'emulator-5554',
        platform: 'android',
        targetApp: 'com.example.app',
      },
      global: {
        stubs: globalStubs,
      },
    })

    expect(wrapper.text()).toContain('移动端真机智能回放与动作执行调度器')
    expect(wrapper.text()).toContain('初始化真机连接')
    expect(wrapper.text()).toContain('空闲未连接')
  })

  it('initializes session and executes playback steps', async () => {
    const wrapper = mount(DevicePlaybackDrawer, {
      props: {
        open: true,
        deviceId: 1,
        serialOrUdid: 'emulator-5554',
        platform: 'android',
        targetApp: 'com.example.app',
      },
      global: {
        stubs: globalStubs,
      },
    })

    const initBtn = wrapper.findAll('button').find((b) => b.text().includes('初始化真机连接'))
    expect(initBtn).toBeDefined()
    await initBtn!.trigger('click')
    await flushPromises()

    expect(mockInitSession).toHaveBeenCalledWith({
      platform: 'android',
      device_id: 1,
      serial_or_udid: 'emulator-5554',
      target_app: 'com.example.app',
    })

    expect(wrapper.text()).toContain('真机已连接就绪')
    expect(wrapper.text()).toContain('安全回收会话')

    // Execute steps
    const execBtn = wrapper.findAll('button').find((b) => b.text().includes('顺序执行全部步骤'))
    expect(execBtn).toBeDefined()
    await execBtn!.trigger('click')
    await flushPromises()

    expect(mockExecuteStep).toHaveBeenCalled()
    expect(wrapper.text()).toContain('步骤 #1')
    expect(wrapper.text()).toContain('click')
  })

  it('teardowns session upon clicking teardown button', async () => {
    const wrapper = mount(DevicePlaybackDrawer, {
      props: {
        open: true,
        deviceId: 1,
        serialOrUdid: 'emulator-5554',
        platform: 'android',
        targetApp: 'com.example.app',
      },
      global: {
        stubs: globalStubs,
      },
    })

    // Init first
    const initBtn = wrapper.findAll('button').find((b) => b.text().includes('初始化真机连接'))
    await initBtn!.trigger('click')
    await flushPromises()

    // Teardown
    const teardownBtn = wrapper.findAll('button').find((b) => b.text().includes('安全回收会话'))
    expect(teardownBtn).toBeDefined()
    await teardownBtn!.trigger('click')
    await flushPromises()

    expect(mockTeardownSession).toHaveBeenCalledWith('pb_sess_test_901')
    expect(wrapper.text()).toContain('已安全回收')
  })
})
