import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import BugTrackerList from './BugTrackerList.vue'

const {
  projectList,
  trackerList,
  trackerCreate,
  trackerUpdate,
  trackerDelete,
  trackerTest,
  messageError,
  messageSuccess,
  messageWarning,
} = vi.hoisted(() => ({
  projectList: vi.fn(),
  trackerList: vi.fn(),
  trackerCreate: vi.fn(),
  trackerUpdate: vi.fn(),
  trackerDelete: vi.fn(),
  trackerTest: vi.fn(),
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
  bugTrackerApi: {
    list: trackerList,
    create: trackerCreate,
    update: trackerUpdate,
    delete: trackerDelete,
    testConnection: trackerTest,
  },
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

const buttonStub = defineComponent({
  name: 'AButton',
  props: { disabled: Boolean },
  emits: ['click'],
  setup: (props, { slots, emit }) => () => h('button', { disabled: props.disabled, onClick: () => emit('click') }, slots.default?.()),
})

function mountPage() {
  return mount(BugTrackerList, {
    global: {
      stubs: {
        AButton: buttonStub,
        AForm: passthrough('AForm'),
        AFormItem: passthrough('AFormItem'),
        AInput: passthrough('AInput'),
        AInputNumber: passthrough('AInputNumber'),
        AInputPassword: passthrough('AInputPassword'),
        AModal: passthrough('AModal'),
        APopconfirm: passthrough('APopconfirm'),
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
const TRACKER = {
  id: 5,
  project_id: 10,
  name: 'Jira',
  tracker_type: 'jira',
  is_enabled: true,
  config: { base_url: 'https://jira.example', email: 'qa@example.com', project_key: 'ATP' },
  field_mapping: { priority: 'High' },
}

beforeEach(() => {
  vi.clearAllMocks()
  projectList.mockResolvedValue(PROJECTS)
  trackerList.mockResolvedValue([TRACKER])
  trackerCreate.mockResolvedValue({ id: 6 })
  trackerUpdate.mockResolvedValue({})
  trackerDelete.mockResolvedValue({})
  trackerTest.mockResolvedValue({ ok: true, message: 'connected' })
})

describe('BugTrackerList mount', () => {
  it('loads project options and trackers after project selection', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.projectId = 10
    await vm.loadTrackers()

    expect(projectList).toHaveBeenCalledOnce()
    expect(trackerList).toHaveBeenCalledWith({ project_id: 10 })
    expect(vm.trackers).toEqual([TRACKER])
  })

  it('validates and creates Jira, ZenTao, GitHub, and GitLab configurations', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.projectId = 10

    await wrapper.vm.$nextTick()
    await wrapper.findAll('button').find((button) => button.text().includes('system_pages.bug_tracker.add'))!.trigger('click')
    await vm.handleSave()
    expect(messageWarning).toHaveBeenCalledWith('system_pages.bug_tracker.msg.name_required')

    vm.form.name = 'Jira'
    vm.jiraBaseUrl = 'https://jira.example'
    vm.jiraEmail = 'qa@example.com'
    vm.jiraToken = 'token'
    vm.jiraProjectKey = 'ATP'
    await vm.handleSave()

    vm.openCreate()
    vm.form.name = 'ZenTao'
    vm.form.tracker_type = 'zentao'
    vm.zentaoBaseUrl = 'https://zentao.example'
    vm.zentaoAccount = 'qa'
    vm.zentaoPassword = 'password'
    vm.zentaoProductId = 9
    await vm.handleSave()

    vm.openCreate()
    vm.form.name = 'GitHub'
    vm.form.tracker_type = 'github'
    vm.githubOwner = 'acme'
    vm.githubRepo = 'atp'
    vm.githubToken = 'token'
    await vm.handleSave()

    vm.openCreate()
    vm.form.name = 'GitLab'
    vm.form.tracker_type = 'gitlab'
    vm.gitlabProjectId = 'acme/atp'
    vm.gitlabToken = 'token'
    await vm.handleSave()

    expect(trackerCreate).toHaveBeenCalledTimes(4)
    expect(trackerCreate.mock.calls.map((call) => call[0].tracker_type)).toEqual(['jira', 'zentao', 'github', 'gitlab'])
    expect(trackerCreate.mock.calls[0][0].config).toEqual(expect.objectContaining({ api_token: 'token', project_key: 'ATP' }))
  })

  it('rejects invalid field mapping and missing platform credentials', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.projectId = 10
    vm.openCreate()
    vm.form.name = 'Jira'
    vm.jiraBaseUrl = 'https://jira.example'
    vm.jiraEmail = 'qa@example.com'
    vm.jiraProjectKey = 'ATP'
    vm.jiraToken = 'token'
    vm.fieldMappingText = '{bad json'
    await vm.handleSave()
    expect(messageError).toHaveBeenCalledWith('system_pages.bug_tracker.msg.field_mapping_invalid')
    expect(trackerCreate).not.toHaveBeenCalled()

    vm.fieldMappingText = '{}'
    vm.jiraBaseUrl = ''
    vm.jiraEmail = ''
    vm.jiraProjectKey = ''
    vm.jiraToken = ''
    await vm.handleSave()
    expect(messageError).toHaveBeenCalledWith('system_pages.bug_tracker.msg.jira_required')
  })

  it('updates, tests, and deletes a tracker with success and failure feedback', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.openEdit(TRACKER)
    vm.form.name = 'Jira updated'
    vm.jiraToken = 'new-token'
    await vm.handleSave()
    expect(trackerUpdate).toHaveBeenCalledWith(5, expect.objectContaining({ name: 'Jira updated' }))

    await vm.handleTestConnection(TRACKER)
    expect(trackerTest).toHaveBeenCalledWith({ tracker_id: 5, tracker_type: 'jira', config: {} })
    expect(messageSuccess).toHaveBeenCalledWith('connected')

    trackerTest.mockResolvedValueOnce({ ok: false, message: 'bad credentials' })
    await vm.handleTestConnection(TRACKER)
    expect(messageError).toHaveBeenCalledWith('bad credentials')

    await vm.handleDelete(5)
    expect(trackerDelete).toHaveBeenCalledWith(5)
    expect(messageSuccess).toHaveBeenCalledWith('system_pages.bug_tracker.msg.delete_success')
  })
})
