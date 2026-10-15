import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import TrafficRecordingDrawer from './TrafficRecordingDrawer.vue'

const mockSession = {
  session_id: 'rec_sess_test_1001',
  project_id: 1,
  target_base_url: 'http://127.0.0.1:8000',
  filter_noise: true,
  is_recording: true,
  created_at: '2026-10-16T10:00:00Z',
  total_captured: 1,
  noise_filtered_ratio_pct: 25.0,
  recorded_entries: [
    {
      method: 'POST',
      path: '/api/v1/orders/checkout',
      status_code: 201,
      duration_ms: 45,
      captured_at: '2026-10-16T10:01:00Z',
      is_noise_filtered: false,
      headers: {
        Authorization: 'Bearer ***REDACTED***',
        'Content-Type': 'application/json',
      },
      request_body: { item_id: 'prod_9872', quantity: 2 },
      response_body: { order_id: 'ord_20261016_01', status: 'created' },
    },
  ],
}

const mockStart = vi.fn().mockResolvedValue(mockSession)
const mockStop = vi.fn().mockResolvedValue({
  ...mockSession,
  is_recording: false,
})
const mockGet = vi.fn().mockResolvedValue(mockSession)
const mockIngest = vi.fn().mockResolvedValue({ status: 'ok', total_captured: 2 })

vi.mock('@/api/trafficRecording', () => ({
  trafficRecordingApi: {
    startSession: (data: unknown) => mockStart(data),
    stopSession: (id: string) => mockStop(id),
    getSession: (id: string) => mockGet(id),
    ingestEntry: (id: string, data: unknown) => mockIngest(id, data),
  },
}))

const globalStubs = {
  'a-drawer': { template: '<div class="ant-drawer"><slot name="title" /><slot /></div>' },
  'a-card': { template: '<div class="ant-card"><slot /><slot name="extra" /></div>' },
  'a-button': { template: '<button class="ant-btn"><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
  'a-badge': { template: '<span class="ant-badge"><slot /></span>' },
  'a-form': { template: '<form><slot /></form>' },
  'a-form-item': { template: '<div class="form-item"><slot /></div>' },
  'a-input': { template: '<input />' },
  'a-switch': true,
  'a-space': { template: '<div><slot /></div>' },
  'a-table': {
    props: ['dataSource'],
    template: `
      <div class="ant-table">
        <slot />
        <div v-for="item in dataSource" :key="item.captured_at" class="table-row">
          <span class="row-method">{{ item.method }}</span>
          <span class="row-path">{{ item.path }}</span>
        </div>
      </div>
    `,
  },
  'a-descriptions': { template: '<div><slot /></div>' },
  'a-descriptions-item': { template: '<div><slot /></div>' },
}

describe('TrafficRecordingDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders drawer header, control inputs, and initial state', () => {
    const wrapper = mount(TrafficRecordingDrawer, {
      props: {
        open: true,
        projectId: 1,
      },
      global: {
        stubs: globalStubs,
      },
    })

    expect(wrapper.text()).toContain('微服务反向代理流量录制与抓包工作台')
    expect(wrapper.text()).toContain('开始流量录制')
    expect(wrapper.text()).toContain('空闲待命中')
  })

  it('starts traffic recording session upon clicking start button', async () => {
    const wrapper = mount(TrafficRecordingDrawer, {
      props: {
        open: true,
        projectId: 1,
      },
      global: {
        stubs: globalStubs,
      },
    })

    const startBtn = wrapper.findAll('button').find((b) => b.text().includes('开始流量录制'))
    expect(startBtn).toBeDefined()
    await startBtn!.trigger('click')
    await flushPromises()

    expect(mockStart).toHaveBeenCalledWith({
      project_id: 1,
      target_base_url: 'http://127.0.0.1:8000',
      filter_noise: true,
    })

    expect(wrapper.text()).toContain('正在实时录制')
    expect(wrapper.text()).toContain('停止录制')
    expect(wrapper.text()).toContain('模拟抓包流入')
    expect(wrapper.text()).toContain('/api/v1/orders/checkout')
  })

  it('stops recording session upon clicking stop button', async () => {
    const wrapper = mount(TrafficRecordingDrawer, {
      props: {
        open: true,
        projectId: 1,
      },
      global: {
        stubs: globalStubs,
      },
    })

    // Start first
    const startBtn = wrapper.findAll('button').find((b) => b.text().includes('开始流量录制'))
    await startBtn!.trigger('click')
    await flushPromises()

    // Stop
    const stopBtn = wrapper.findAll('button').find((b) => b.text().includes('停止录制'))
    expect(stopBtn).toBeDefined()
    await stopBtn!.trigger('click')
    await flushPromises()

    expect(mockStop).toHaveBeenCalledWith('rec_sess_test_1001')
    expect(wrapper.text()).toContain('空闲待命中')
  })
})
