import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import RecordingHistoryDrawer from './RecordingHistoryDrawer.vue'

const { listMock, deleteMock, messageSuccess } = vi.hoisted(() => ({
  listMock: vi.fn(),
  deleteMock: vi.fn(),
  messageSuccess: vi.fn(),
}))

vi.mock('@/api', () => ({
  recordingRecordApi: {
    list: listMock,
    delete: deleteMock,
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      params ? `${key}:${JSON.stringify(params)}` : key,
  }),
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: messageSuccess,
    error: vi.fn(),
  },
}))

const passthrough = (name: string) =>
  defineComponent({
    name,
    setup: (_props, { slots }) => () => h('div', [slots.default?.(), slots.footer?.()]),
  })

const stubs = {
  ADrawer: passthrough('ADrawer'),
  ASpace: passthrough('ASpace'),
  ASpin: passthrough('ASpin'),
  AEmpty: passthrough('AEmpty'),
  AAlert: passthrough('AAlert'),
  ATag: passthrough('ATag'),
  ASegmented: defineComponent({
    name: 'ASegmented',
    props: ['value', 'options'],
    emits: ['update:value'],
    setup(_props) {
      return () => h('div')
    },
  }),
  AButton: defineComponent({
    name: 'AButton',
    props: ['disabled', 'loading'],
    emits: ['click'],
    setup(props, { slots, emit }) {
      return () =>
        h(
          'button',
          {
            disabled: props.disabled,
            onClick: () => emit('click'),
          },
          slots.default?.(),
        )
    },
  }),
  APopconfirm: defineComponent({
    name: 'APopconfirm',
    emits: ['confirm'],
    setup(_props, { slots, emit }) {
      return () =>
        h('div', [
          slots.default?.(),
          h('button', { 'data-test': 'confirm-delete', onClick: () => emit('confirm') }, 'confirm'),
        ])
    },
  }),
}

describe('RecordingHistoryDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listMock.mockResolvedValue([
      {
        id: 101,
        project_id: 7,
        kind: 'web',
        source: 'workbench',
        session_id: 'sess-101',
        title: 'Web 录制 · demo.local',
        target_url: 'https://demo.local/login',
        browser: 'chromium',
        status: 'draft',
        steps: [
          { action: 'goto', name: '打开登录页', params: { url: 'https://demo.local/login' } },
          { action: 'assert_visible', name: '断言可见 #submit', params: { selector: '#submit' } },
        ],
        steps_count: 2,
        assertion_count: 1,
        asset_ids: [11],
        artifacts: {
          trace: {
            kind: 'trace',
            filename: 'trace.zip',
            content_type: 'application/zip',
            size: 1024,
            url: 'https://minio.local/trace.zip?sig=fresh',
          },
          har: {
            kind: 'har',
            filename: 'network.har',
            content_type: 'application/json',
            size: 512,
            url: 'https://minio.local/network.har?sig=fresh',
          },
        },
        summary: {},
        created_at: '2026-11-13T07:00:00Z',
        updated_at: '2026-11-13T07:05:00Z',
      },
    ])
    deleteMock.mockResolvedValue({})
  })

  it('loads records on open, renders fresh trace/har links, emits restore and deletes record', async () => {
    const wrapper = mount(RecordingHistoryDrawer, {
      props: {
        open: true,
        projectId: 7,
        kind: 'web',
        mode: 'manage',
      },
      global: { stubs },
    })

    await flushPromises()
    expect(listMock).toHaveBeenCalledWith({ project_id: 7, kind: 'web', limit: 50 })
    expect(wrapper.text()).toContain('Web 录制 · demo.local')

    const links = wrapper.findAll('a.artifact-link')
    expect(links.map((a) => a.attributes('href'))).toEqual([
      'https://minio.local/trace.zip?sig=fresh',
      'https://minio.local/network.har?sig=fresh',
    ])

    const restoreBtn = wrapper.findAll('button').find((btn) => btn.text().includes('recording_history.restore_to_case'))
    await restoreBtn!.trigger('click')
    expect(wrapper.emitted('restore')?.[0]?.[0]).toMatchObject({ id: 101 })

    await wrapper.find('[data-test="confirm-delete"]').trigger('click')
    await flushPromises()
    expect(deleteMock).toHaveBeenCalledWith(101)
    expect(wrapper.emitted('deleted')?.[0]).toEqual([101])
    expect(messageSuccess).toHaveBeenCalledWith('recording_history.deleted')
    wrapper.unmount()
  })

  it('hides delete, disables restore when canModify=false, and drops unsafe artifact schemes', async () => {
    listMock.mockResolvedValueOnce([
      {
        id: 202,
        project_id: 7,
        kind: 'web',
        source: 'workbench',
        session_id: 's-202',
        title: '只读与异常链接记录',
        status: 'saved',
        case_id: 88,
        steps: [{ action: 'goto', name: '打开首页', params: { url: 'https://demo.local' } }],
        steps_count: 1,
        assertion_count: 0,
        asset_ids: [],
        artifacts: {
          trace: {
            kind: 'trace',
            filename: 'trace.zip',
            content_type: 'application/zip',
            size: 100,
            url: 'javascript:alert(1)',
          },
          har: {
            kind: 'har',
            filename: 'ok.har',
            content_type: 'application/json',
            size: 50,
            url: '/api/v1/files/ok.har',
          },
        },
        summary: {},
        created_at: '2026-11-13T07:00:00Z',
        updated_at: '2026-11-13T07:05:00Z',
      },
    ])

    const wrapper = mount(RecordingHistoryDrawer, {
      props: {
        open: true,
        projectId: 7,
        kind: 'web',
        mode: 'manage',
        canModify: false,
      },
      global: { stubs },
    })

    await flushPromises()
    const links = wrapper.findAll('a.artifact-link')
    expect(links.map((a) => a.attributes('href'))).toEqual(['/api/v1/files/ok.har'])

    const restoreBtn = wrapper.findAll('button').find((btn) => btn.text().includes('recording_history.restore_to_case'))
    expect(restoreBtn?.attributes('disabled')).toBeDefined()
    expect(wrapper.find('[data-test="confirm-delete"]').exists()).toBe(false)

    const openCaseBtn = wrapper.findAll('button').find((btn) => btn.text().includes('recording_history.linked_case'))
    await openCaseBtn?.trigger('click')
    expect(wrapper.emitted('open-case')?.[0]).toEqual([88])
    wrapper.unmount()
  })
})
