import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ApkList from './ApkList.vue'

const { apkList, apkUpload, apkUpdate, apkDelete, apkDownload, projectList, messageError, messageSuccess } =
  vi.hoisted(() => ({
    apkList: vi.fn(),
    apkUpload: vi.fn(),
    apkUpdate: vi.fn(),
    apkDelete: vi.fn(),
    apkDownload: vi.fn(),
    projectList: vi.fn(),
    messageError: vi.fn(),
    messageSuccess: vi.fn(),
  }))

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))

vi.mock('ant-design-vue', () => ({
  message: { error: messageError, success: messageSuccess },
}))

vi.mock('@/api', () => ({
  apkApi: {
    list: apkList,
    upload: apkUpload,
    update: apkUpdate,
    delete: apkDelete,
    download: apkDownload,
  },
  projectApi: { list: projectList },
}))

// a-table 用一个能对每行渲染 action slot 的极简替身，让按钮点击可驱动真实 handler
const TableStub = defineComponent({
  name: 'ATable',
  props: ['dataSource', 'columns'],
  setup(props, { slots }) {
    return () =>
      h(
        'div',
        { 'data-test': 'apk-table' },
        (props.dataSource || []).map((record: Record<string, unknown>) =>
          h('div', { class: 'apk-row', key: record.id as number }, [
            slots.bodyCell?.({ column: { key: 'action' }, record }),
          ]),
        ),
      )
  },
})

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_p, { slots }) => () => h('div', slots.default?.()) })

const inputModel = (name: string) =>
  defineComponent({
    name,
    props: ['value'],
    emits: ['update:value'],
    setup: (props, { emit }) =>
      () => h('input', { value: props.value, onInput: (e: Event) => emit('update:value', (e.target as HTMLInputElement).value) }),
  })

function mountApkList() {
  return mount(ApkList, {
    global: {
      stubs: {
        ATable: TableStub,
        AInputSearch: defineComponent({
          name: 'AInputSearch',
          props: ['value'],
          emits: ['update:value'],
          setup: (props, { emit }) => () => h('input', { 'data-test': 'search', value: props.value, onInput: (e: Event) => emit('update:value', (e.target as HTMLInputElement).value) }),
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
        // 其余容器/表单组件直接透传插槽内容
        ARow: passthrough('ARow'),
        ACol: passthrough('ACol'),
        ACard: passthrough('ACard'),
        ASelect: inputModel('ASelect'),
        AModal: passthrough('AModal'),
        AForm: passthrough('AForm'),
        AFormItem: passthrough('AFormItem'),
        AInput: inputModel('AInput'),
        AInputNumber: inputModel('AInputNumber'),
        ATextarea: inputModel('ATextarea'),
        AUpload: passthrough('AUpload'),
        APopconfirm: defineComponent({
          name: 'APopconfirm',
          emits: ['confirm'],
          setup: (_p, { slots, emit }) => () => h('div', { 'data-test': 'delete-confirm', onClick: () => emit('confirm') }, slots.default?.()),
        }),
        ASpace: passthrough('ASpace'),
        UploadOutlined: true,
      },
    },
  })
}

const APKS = [
  { id: 1, filename: 'app-release.apk', package_name: 'com.acme.app', version_name: '1.2.0', version_code: 120, project_id: 5, file_size: 2 * 1024 * 1024, created_at: '2026-07-10T09:00:00Z' },
  { id: 2, filename: 'beta.apk', package_name: 'com.acme.beta', version_name: '0.9.0', version_code: 90, project_id: 6, file_size: 512, created_at: '2026-07-09T08:00:00Z' },
]
const PROJECTS = [{ id: 5, name: 'Acme' }, { id: 6, name: 'Beta' }]

beforeEach(() => {
  vi.clearAllMocks()
  apkList.mockResolvedValue(APKS)
  projectList.mockResolvedValue(PROJECTS)
  apkUpload.mockResolvedValue({})
  apkUpdate.mockResolvedValue({})
  apkDelete.mockResolvedValue({})
  apkDownload.mockResolvedValue({ url: 'https://minio/apk-1' })
})

describe('ApkList mount', () => {
  it('loads projects and apks on mount and renders summary stats', async () => {
    const wrapper = mountApkList()
    await flushPromises()

    expect(projectList).toHaveBeenCalledOnce()
    expect(apkList).toHaveBeenCalledWith(undefined)
    const stats = wrapper.findAll('[data-test="stat"]').map((s) => s.text())
    expect(stats).toContain('2') // total apks 数
    expect(stats).toContain('2.0 MB') // 大小汇总 2MB + 512B
  })

  it('filters apks by keyword across filename/package/version/project', async () => {
    const wrapper = mountApkList()
    await flushPromises()

    await wrapper.find('[data-test="search"]').setValue('beta')
    await flushPromises()
    expect(wrapper.findAll('.apk-row')).toHaveLength(1)

    // 项目名 'Beta' 唯一命中 apk 2（project_id=6）；验证按项目名过滤
    await wrapper.find('[data-test="search"]').setValue('Beta')
    await flushPromises()
    expect(wrapper.findAll('.apk-row')).toHaveLength(1)

    await wrapper.find('[data-test="search"]').setValue('')
    await flushPromises()
    expect(wrapper.findAll('.apk-row')).toHaveLength(2)
  })

  it('surfaces a message when apk load fails', async () => {
    apkList.mockRejectedValueOnce(new Error('boom'))
    mountApkList()
    await flushPromises()
    expect(messageError).toHaveBeenCalled()
  })

  it('deletes an apk via the row action and reloads', async () => {
    const wrapper = mountApkList()
    await flushPromises()
    apkList.mockClear()

    // action slot 里的 popconfirm confirm → handleDelete(record.id)
    await wrapper.find('[data-test="delete-confirm"]').trigger('click')
    await flushPromises()

    expect(apkDelete).toHaveBeenCalledWith(1)
    expect(messageSuccess).toHaveBeenCalled()
    expect(apkList).toHaveBeenCalled() // reload
  })
})
