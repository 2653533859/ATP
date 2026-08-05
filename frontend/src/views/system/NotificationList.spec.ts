import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import NotificationList from './NotificationList.vue'

const {
  projectList,
  notificationList,
  notificationCreate,
  notificationUpdate,
  notificationTest,
  notificationDelete,
  suiteList,
  planList,
  messageError,
  messageSuccess,
  messageWarning,
} = vi.hoisted(() => ({
  projectList: vi.fn(),
  notificationList: vi.fn(),
  notificationCreate: vi.fn(),
  notificationUpdate: vi.fn(),
  notificationTest: vi.fn(),
  notificationDelete: vi.fn(),
  suiteList: vi.fn(),
  planList: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  messageWarning: vi.fn(),
}))

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('ant-design-vue', () => ({
  message: { error: messageError, success: messageSuccess, warning: messageWarning },
}))
vi.mock('@/api', () => ({
  projectApi: { list: projectList },
  notificationApi: {
    list: notificationList,
    create: notificationCreate,
    update: notificationUpdate,
    test: notificationTest,
    delete: notificationDelete,
  },
  suiteApi: { list: suiteList },
  planApi: { list: planList },
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

const buttonStub = defineComponent({
  name: 'AButton',
  props: { disabled: Boolean },
  emits: ['click'],
  setup: (props, { slots, emit }) => () => h('button', { disabled: props.disabled, onClick: () => emit('click') }, slots.default?.()),
})

const popconfirmStub = defineComponent({
  name: 'APopconfirm',
  emits: ['confirm'],
  setup: (_props, { slots, emit }) => () => h('span', { 'data-test': 'confirm', onClick: () => emit('confirm') }, slots.default?.()),
})

function mountPage() {
  return mount(NotificationList, {
    global: {
      stubs: {
        AButton: buttonStub,
        ACard: passthrough('ACard'),
        ACheckboxGroup: passthrough('ACheckboxGroup'),
        ADivider: passthrough('ADivider'),
        AForm: passthrough('AForm'),
        AFormItem: passthrough('AFormItem'),
        AInput: passthrough('AInput'),
        AInputPassword: passthrough('AInputPassword'),
        AModal: passthrough('AModal'),
        APopconfirm: popconfirmStub,
        ASelect: passthrough('ASelect'),
        ASelectOption: passthrough('ASelectOption'),
        ASpace: passthrough('ASpace'),
        ASwitch: passthrough('ASwitch'),
        ATable: passthrough('ATable'),
        ATag: passthrough('ATag'),
        ATextarea: passthrough('ATextarea'),
        PlusOutlined: true,
      },
    },
  })
}

const PROJECTS = [{ id: 10, name: 'Core' }]
const NOTIFICATION = {
  id: 5,
  name: 'Failure email',
  channel: 'email',
  is_enabled: true,
  config: {
    recipients: ['qa@example.com'],
    subject_prefix: '[ATP]',
    language: 'en-US',
    scope: 'suites',
    suite_ids: [2],
    plan_ids: [],
    status_filters: ['failed'],
  },
}

beforeEach(() => {
  vi.clearAllMocks()
  projectList.mockResolvedValue(PROJECTS)
  notificationList.mockResolvedValue([NOTIFICATION])
  notificationCreate.mockResolvedValue({ id: 6 })
  notificationUpdate.mockResolvedValue({})
  notificationTest.mockResolvedValue({})
  notificationDelete.mockResolvedValue({})
  suiteList.mockResolvedValue([{ id: 2, name: 'Smoke' }])
  planList.mockResolvedValue([{ id: 3, name: 'Nightly' }])
})

describe('NotificationList mount', () => {
  it('loads projects, notifications, and target options after project selection', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.projectId = 10
    await vm.handleProjectChange()

    expect(projectList).toHaveBeenCalledOnce()
    expect(notificationList).toHaveBeenCalledWith({ project_id: 10 })
    expect(suiteList).toHaveBeenCalledWith({ project_id: 10 })
    expect(planList).toHaveBeenCalledWith({ project_id: 10 })
    expect(vm.suiteOptions).toEqual([{ label: 'Smoke (#2)', value: 2 }])
  })

  it('validates email settings and builds a scoped create payload', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.projectId = 10
    await wrapper.vm.$nextTick()
    await wrapper.findAll('button').find((button) => button.text().includes('system_pages.notification.add'))!.trigger('click')
    await vm.handleSave()
    expect(messageWarning).toHaveBeenCalledWith('system_pages.notification.msg.name_required')

    vm.form.name = 'Failure email'
    vm.emailRecipients = 'qa@example.com\n ops@example.com '
    vm.notificationScope = 'suites'
    vm.selectedSuiteIds = [2]
    vm.statusFilters = ['failed', 'error']
    await vm.handleSave()

    expect(notificationCreate).toHaveBeenCalledWith({
      name: 'Failure email',
      channel: 'email',
      is_enabled: true,
      project_id: 10,
      config: {
        recipients: ['qa@example.com', 'ops@example.com'],
        subject_prefix: '[ATP]',
        language: 'zh-CN',
        scope: 'suites',
        suite_ids: [2],
        plan_ids: [],
        status_filters: ['failed', 'error'],
      },
    })
  })

  it('covers channel-specific validation and edit config reconstruction', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.projectId = 10
    vm.openCreate()
    vm.form.name = 'WeChat'
    vm.form.channel = 'wechat'
    await vm.handleSave()
    expect(messageWarning).toHaveBeenCalledWith('system_pages.notification.msg.wechat_url_required')

    vm.wechatUrl = 'https://wechat.example/hook'
    await vm.handleSave()
    expect(notificationCreate).toHaveBeenCalledWith(expect.objectContaining({
      channel: 'wechat',
      config: expect.objectContaining({ webhook_url: 'https://wechat.example/hook' }),
    }))

    vm.openEdit(NOTIFICATION)
    expect(vm.emailRecipients).toBe('qa@example.com')
    expect(vm.notificationLanguage).toBe('en-US')
    expect(vm.notificationScope).toBe('suites')
    expect(vm.selectedSuiteIds).toEqual([2])
    await vm.handleSave()
    expect(notificationUpdate).toHaveBeenCalledWith(5, expect.objectContaining({ name: 'Failure email' }))
  })

  it('tests and deletes a notification, including failure feedback', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.handleTest(NOTIFICATION)
    expect(notificationTest).toHaveBeenCalledWith(5)
    expect(messageSuccess).toHaveBeenCalledWith('system_pages.notification.msg.test_success')

    await vm.handleDelete(5)
    expect(notificationDelete).toHaveBeenCalledWith(5)
    expect(messageSuccess).toHaveBeenCalledWith('system_pages.notification.msg.delete_success')

    notificationTest.mockRejectedValueOnce(new Error('webhook failed'))
    await vm.handleTest(NOTIFICATION)
    expect(messageError).toHaveBeenCalledWith('system_pages.notification.msg.test_failed')
  })
})
