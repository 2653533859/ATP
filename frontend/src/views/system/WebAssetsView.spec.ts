import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import WebAssetsView from './WebAssetsView.vue'

const {
  listElements,
  listPageObjects,
  listBaselines,
  updateBaseline,
  projectList,
  authRole,
  projectUserRole,
} = vi.hoisted(() => ({
  listElements: vi.fn(),
  listPageObjects: vi.fn(),
  listBaselines: vi.fn(),
  updateBaseline: vi.fn(),
  projectList: vi.fn(),
  authRole: { value: 'tester' },
  projectUserRole: { value: 'editor' as 'owner' | 'editor' | 'viewer' },
}))

vi.mock('vue-router', () => ({ useRoute: () => ({ query: { project_id: '1' } }) }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('ant-design-vue', () => ({
  message: { error: vi.fn(), success: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: { role: authRole.value } }),
}))
vi.mock('@/api', () => ({
  projectApi: { list: projectList },
  webAssetsApi: {
    listElements,
    listPageObjects,
    createElement: vi.fn(),
    updateElement: vi.fn(),
    deleteElement: vi.fn(),
    previewElementRepair: vi.fn(),
    createPageObject: vi.fn(),
    updatePageObject: vi.fn(),
    deletePageObject: vi.fn(),
    listStorageStates: vi.fn().mockResolvedValue([]),
    deleteStorageState: vi.fn(),
  },
  webFilesApi: {
    list: vi.fn().mockResolvedValue([]),
    rename: vi.fn(),
    delete: vi.fn(),
  },
  webVisualApi: {
    listBaselines,
    uploadBaseline: vi.fn(),
    updateBaseline,
    deleteBaseline: vi.fn(),
  },
}))

const passthrough = (name: string) => defineComponent({
  name,
  props: ['disabled', 'source', 'open'],
  setup: (_props, { slots }) => () => h('div', slots.default?.()),
})

function mountView() {
  return mount(WebAssetsView, {
    global: {
      stubs: {
        AAlert: passthrough('AAlert'),
        AButton: defineComponent({
          name: 'AButton',
          props: ['disabled'],
          emits: ['click'],
          setup: (props, { slots, emit }) => () => h('button', { disabled: props.disabled, onClick: () => emit('click') }, slots.default?.()),
        }),
        AForm: passthrough('AForm'),
        AFormItem: passthrough('AFormItem'),
        AImage: passthrough('AImage'),
        AInput: passthrough('AInput'),
        AInputNumber: passthrough('AInputNumber'),
        AModal: passthrough('AModal'),
        APopconfirm: passthrough('APopconfirm'),
        ARadio: passthrough('ARadio'),
        ARadioGroup: passthrough('ARadioGroup'),
        ASelect: passthrough('ASelect'),
        ASpace: passthrough('ASpace'),
        ATabPane: passthrough('ATabPane'),
        ATable: passthrough('ATable'),
        ATabs: passthrough('ATabs'),
        ATag: passthrough('ATag'),
        ATextarea: passthrough('ATextarea'),
        AUpload: passthrough('AUpload'),
        WebRecorderModal: defineComponent({
          name: 'WebRecorderModal',
          props: ['open', 'projectId', 'showCapture', 'autoApply', 'source'],
          setup: (props) => () => h('div', { 'data-recorder-source': props.source }),
        }),
      },
    },
  })
}

describe('WebAssetsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    authRole.value = 'tester'
    projectUserRole.value = 'editor'
    projectList.mockImplementation(async () => [{ id: 1, name: 'Demo', current_user_role: projectUserRole.value }])
    listElements.mockResolvedValue([])
    listPageObjects.mockResolvedValue([])
    listBaselines.mockResolvedValue([
      {
        id: 12,
        project_id: 1,
        name: '首页截图',
        page_url: 'https://demo.test',
        object_name: 'visual-baselines/projects/1/home.png',
        content_type: 'image/png',
        width: 1280,
        height: 720,
        threshold: 0.01,
        pixel_threshold: 10,
        ignore_regions: [],
        version: 1,
        created_at: '',
        updated_at: '',
      },
    ])
    updateBaseline.mockResolvedValue({})
  })

  it('allows project editors, passes source="assets" to WebRecorderModal, and edits visual baseline settings', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.get('[data-recorder-source]').attributes('data-recorder-source')).toBe('assets')
    const vm = wrapper.vm as unknown as {
      canModify: boolean
      openVisualBaselineEdit: (item: Record<string, unknown>) => void
      visualBaselineForm: { threshold: number; pixel_threshold: number; ignoreText: string }
      saveVisualBaseline: () => Promise<void>
    }
    expect(vm.canModify).toBe(true)

    vm.openVisualBaselineEdit({
      id: 12,
      name: '首页截图',
      page_url: 'https://demo.test',
      threshold: 0.01,
      pixel_threshold: 10,
      ignore_regions: [],
    })
    vm.visualBaselineForm.threshold = 0.05
    await vm.saveVisualBaseline()
    expect(updateBaseline).toHaveBeenCalledWith(12, {
      threshold: 0.05,
      pixel_threshold: 10,
      ignore_regions: [],
    })
    wrapper.unmount()
  })

  it('disables mutations for viewer project members', async () => {
    projectUserRole.value = 'viewer'
    const wrapper = mountView()
    await flushPromises()

    const vm = wrapper.vm as unknown as { canModify: boolean }
    expect(vm.canModify).toBe(false)
    const buttons = wrapper.findAll('button')
    expect(buttons.some((b) => b.text() === 'web_assets.new_element' && b.attributes('disabled') !== undefined)).toBe(true)
    wrapper.unmount()
  })

  it('lists, renames, and deletes storage states and uploaded web files', async () => {
    const apiMod = await import('@/api')
    vi.mocked(apiMod.webAssetsApi.listStorageStates).mockResolvedValue([
      { name: 'auth-session', size: 256, updated_at: '2026-11-27T00:00:00Z', object_name: 'storage-states/projects/1/auth-session.json' },
    ])
    vi.mocked(apiMod.webFilesApi.list).mockResolvedValue([
      { object_name: 'web-files/projects/1/sample.png', filename: 'sample.png', size: 1024, last_modified: '2026-11-27T00:00:00Z' },
    ])
    vi.mocked(apiMod.webAssetsApi.deleteStorageState).mockResolvedValue(undefined)
    vi.mocked(apiMod.webFilesApi.rename).mockResolvedValue({ object_name: 'web-files/projects/1/next.png', old_object_name: 'web-files/projects/1/sample.png', filename: 'next.png', content_type: 'image/png', size: 1024 })
    vi.mocked(apiMod.webFilesApi.delete).mockResolvedValue(undefined)

    const wrapper = mountView()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.storageStates).toHaveLength(1)
    expect(vm.uploadedFiles).toHaveLength(1)

    await vm.deleteStorageState('auth-session')
    expect(apiMod.webAssetsApi.deleteStorageState).toHaveBeenCalledWith(1, 'auth-session')

    vm.openRenameFileModal({ object_name: 'web-files/projects/1/sample.png', filename: 'sample.png' })
    vm.renameFileForm.filename = 'next.png'
    await vm.handleRenameFile()
    expect(apiMod.webFilesApi.rename).toHaveBeenCalledWith(1, { object_name: 'web-files/projects/1/sample.png', filename: 'next.png' })

    await vm.deleteUploadedFile('web-files/projects/1/sample.png')
    expect(apiMod.webFilesApi.delete).toHaveBeenCalledWith(1, 'web-files/projects/1/sample.png')
    wrapper.unmount()
  })
})
