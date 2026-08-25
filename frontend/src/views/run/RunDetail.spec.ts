import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import RunDetail from './RunDetail.vue'

const { createRunWebSocket, messageError, routerBack, runExportHtml, runExportJunit, runGet, tracingGetConfig } = vi.hoisted(() => ({
  createRunWebSocket: vi.fn(),
  messageError: vi.fn(),
  routerBack: vi.fn(),
  runExportHtml: vi.fn(),
  runExportJunit: vi.fn(),
  runGet: vi.fn(),
  tracingGetConfig: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { runId: '42' } }),
  useRouter: () => ({ back: routerBack }),
}))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('ant-design-vue', () => ({ Empty: { PRESENTED_IMAGE_SIMPLE: 'empty' }, message: { error: messageError, success: vi.fn() } }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ token: 'token', user: { role: 'engineer' }, fetchMe: vi.fn() }) }))
vi.mock('@/utils/websocket', () => ({ createRunWebSocket }))
vi.mock('@/api', () => ({
  aiHealingPatchApi: { apply: vi.fn(), preview: vi.fn() },
  bugTrackerApi: { createBug: vi.fn(), list: vi.fn().mockResolvedValue([]), linkBug: vi.fn(), refreshStatus: vi.fn() },
  runApi: { exportHtml: runExportHtml, exportPdf: vi.fn(), exportJunit: runExportJunit, get: runGet },
  tracingApi: { getConfig: tracingGetConfig },
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_p, { slots }) => () => h('div', slots.default?.()) })

type TestWsMessage = { type: string; status?: string; duration_ms?: number }
let wsMessageHandler: ((message: TestWsMessage) => void) | null = null

function mountRunDetail() {
  return mount(RunDetail, {
    global: {
      stubs: {
        A: passthrough('A'),
        AButton: defineComponent({ name: 'AButton', emits: ['click'], setup: (_p, { slots, emit }) => () => h('button', { onClick: () => emit('click') }, slots.default?.()) }),
        ACard: passthrough('ACard'),
        ACol: passthrough('ACol'),
        ADescriptions: passthrough('ADescriptions'),
        ADescriptionsItem: passthrough('ADescriptionsItem'),
        AEmpty: passthrough('AEmpty'),
        AForm: passthrough('AForm'),
        AFormItem: passthrough('AFormItem'),
        AImage: passthrough('AImage'),
        AInput: passthrough('AInput'),
        AModal: passthrough('AModal'),
        APageHeader: defineComponent({ name: 'APageHeader', emits: ['back'], setup: (_p, { slots, emit }) => () => h('header', [h('button', { 'data-test': 'back', onClick: () => emit('back') }, 'back'), slots.extra?.(), slots.default?.()]) }),
        ARow: passthrough('ARow'),
        ASelect: passthrough('ASelect'),
        ASpace: passthrough('ASpace'),
        ASpin: passthrough('ASpin'),
        AStep: passthrough('AStep'),
        ASteps: passthrough('ASteps'),
        ATable: passthrough('ATable'),
        ATag: passthrough('ATag'),
        ATextarea: passthrough('ATextarea'),
        BugOutlined: true,
        BulbOutlined: true,
        CameraOutlined: true,
        FilePdfOutlined: true,
        FileTextOutlined: true,
        LinkOutlined: true,
        LoadingOutlined: true,
        VideoCameraOutlined: true,
        WarningOutlined: true,
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  wsMessageHandler = null
  tracingGetConfig.mockResolvedValue({ jaeger_ui_url: 'http://jaeger' })
  runGet.mockResolvedValue({
    id: 42,
    case_id: 100,
    status: 'failed',
    trace_id: 'trace-1',
    environment: 'staging',
    duration_ms: 123,
    created_at: '2026-07-11T01:00:00Z',
    error_message: 'assertion failed',
    result_summary: {},
    steps: [{ step_index: 0, name: 'assert text', status: 'failed', error_message: 'missing text', screenshot_url: 'https://minio/1.png' }],
  })
  runExportHtml.mockResolvedValue(new Blob(['html']))
  runExportJunit.mockResolvedValue(new Blob(['junit']))
  createRunWebSocket.mockImplementation((_runId: number, onMessage: (message: TestWsMessage) => void) => {
    wsMessageHandler = onMessage
    return { close: vi.fn() }
  })
})

describe('RunDetail mount', () => {
  it('loads tracing config and run detail on mount', async () => {
    const wrapper = mountRunDetail()
    await flushPromises()

    expect(tracingGetConfig).toHaveBeenCalledOnce()
    expect(runGet).toHaveBeenCalledWith(42)
    expect(wrapper.text()).toContain('42')
    expect(wrapper.text()).toContain('assertion failed')
  })

  it('uses router back from page header', async () => {
    const wrapper = mountRunDetail()
    await flushPromises()

    await wrapper.find('[data-test="back"]').trigger('click')

    expect(routerBack).toHaveBeenCalledOnce()
  })

  it('exposes JUnit XML export from the run detail', async () => {
    const wrapper = mountRunDetail()
    await flushPromises()

    const junitButton = wrapper.findAll('button').find((button) => button.text().includes('run.export_junit'))
    expect(junitButton).toBeDefined()
    await junitButton!.trigger('click')
    await flushPromises()

    expect(runExportJunit).toHaveBeenCalledWith(42)
  })

  it('renders Android device matrix child results', async () => {
    runGet.mockResolvedValueOnce({
      id: 42,
      case_id: 100,
      status: 'failed',
      trace_id: null,
      environment: 'staging',
      duration_ms: 321,
      created_at: '2026-07-11T01:00:00Z',
      error_message: 'one device failed',
      result_summary: {
        device_matrix_total: 2,
        device_matrix_passed: 1,
        device_matrix_failed: 1,
        device_matrix_error: 0,
        device_matrix_results: [
          { run_id: 43, index: 0, serial: 'emu-1', status: 'passed', duration_ms: 120, error: null },
          { run_id: 44, index: 1, serial: 'emu-2', status: 'failed', duration_ms: 200, error: 'assertion failed' },
        ],
      },
      steps: [],
    })

    const wrapper = mountRunDetail()
    await flushPromises()

    expect(wrapper.text()).toContain('emu-1')
    expect(wrapper.text()).toContain('emu-2')
    expect(wrapper.text()).toContain('assertion failed')
    expect(wrapper.text()).toContain('run.device_matrix.total')
  })

  it('renders an Android screen recording stored in android artifacts', async () => {
    runGet.mockResolvedValueOnce({
      id: 42,
      case_id: 100,
      status: 'passed',
      trace_id: null,
      environment: 'staging',
      duration_ms: 321,
      created_at: '2026-07-11T01:00:00Z',
      error_message: null,
      result_summary: {
        android_artifacts: {
          screen_recording: 'https://minio/android-artifacts/runs/42/screen-recording.mp4',
        },
      },
      steps: [],
    })

    const wrapper = mountRunDetail()
    await flushPromises()

    expect(wrapper.find('video').attributes('src')).toBe('https://minio/android-artifacts/runs/42/screen-recording.mp4')
  })

  it('shows an Android recording warning when the device cannot produce a video', async () => {
    runGet.mockResolvedValueOnce({
      id: 42,
      case_id: 100,
      status: 'passed',
      trace_id: null,
      environment: 'staging',
      duration_ms: 321,
      created_at: '2026-07-11T01:00:00Z',
      error_message: null,
      result_summary: {
        android_artifacts: { screen_recording_error: '设备未生成可上传的录屏文件' },
      },
      steps: [],
    })

    const wrapper = mountRunDetail()
    await flushPromises()

    expect(wrapper.find('[role="alert"]').text()).toContain('设备未生成可上传的录屏文件')
  })

  it('refreshes Android artifacts when a live run completes', async () => {
    runGet.mockResolvedValueOnce({
      id: 42,
      case_id: 100,
      status: 'running',
      trace_id: null,
      environment: 'staging',
      duration_ms: null,
      created_at: '2026-07-11T01:00:00Z',
      error_message: null,
      result_summary: {},
      steps: [],
    })
    runGet.mockResolvedValueOnce({
      id: 42,
      case_id: 100,
      status: 'passed',
      trace_id: null,
      environment: 'staging',
      duration_ms: 321,
      created_at: '2026-07-11T01:00:00Z',
      error_message: null,
      result_summary: {
        android_artifacts: {
          screen_recording: 'https://minio/android-artifacts/runs/42/screen-recording.mp4',
        },
      },
      steps: [],
    })

    const wrapper = mountRunDetail()
    await flushPromises()

    wsMessageHandler?.({ type: 'completed', status: 'passed', duration_ms: 321 })
    await flushPromises()

    expect(wrapper.find('video').attributes('src')).toBe('https://minio/android-artifacts/runs/42/screen-recording.mp4')
  })
})
