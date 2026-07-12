import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import RunDetail from './RunDetail.vue'

const { createRunWebSocket, messageError, routerBack, runExportHtml, runGet, tracingGetConfig } = vi.hoisted(() => ({
  createRunWebSocket: vi.fn(),
  messageError: vi.fn(),
  routerBack: vi.fn(),
  runExportHtml: vi.fn(),
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
  runApi: { exportHtml: runExportHtml, exportPdf: vi.fn(), get: runGet },
  tracingApi: { getConfig: tracingGetConfig },
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_p, { slots }) => () => h('div', slots.default?.()) })

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
  createRunWebSocket.mockReturnValue({ close: vi.fn() })
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
})
