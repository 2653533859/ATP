import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import DefectListView from './DefectListView.vue'

const { authUser, routeQuery, bugTrackerList, defectCreateExternal, projectList, memberList, defectList, defectUpdate } = vi.hoisted(() => ({
  authUser: { role: 'engineer' as string },
  routeQuery: {} as Record<string, string>,
  bugTrackerList: vi.fn(),
  defectCreateExternal: vi.fn(),
  projectList: vi.fn(),
  memberList: vi.fn(),
  defectList: vi.fn(),
  defectUpdate: vi.fn(),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string, params?: Record<string, unknown>) => params ? `${key}:${JSON.stringify(params)}` : key }),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: routeQuery }),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: authUser }) }))
vi.mock('ant-design-vue', () => ({
  message: { error: vi.fn(), success: vi.fn(), warning: vi.fn() },
  Modal: { confirm: vi.fn() },
}))
vi.mock('@/api', () => ({
  bugTrackerApi: { list: bugTrackerList },
  projectApi: { list: projectList },
  projectMemberApi: { list: memberList },
  defectApi: { list: defectList, update: defectUpdate, createExternal: defectCreateExternal },
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

const tableStub = defineComponent({
  name: 'ATable',
  props: ['dataSource'],
  setup: (props, { slots }) => () => h(
    'div',
    (props.dataSource || []).map((record: Record<string, unknown>) => h(
      'div',
      { class: 'defect-row', key: String(record.id) },
      slots.bodyCell?.({ column: { key: 'title' }, record }),
    )),
  ),
})

const globalStubs = {
  AAlert: passthrough('AAlert'),
  AButton: passthrough('AButton'),
  ABadge: passthrough('ABadge'),
  ACard: passthrough('ACard'),
  ACol: passthrough('ACol'),
  ADescriptions: passthrough('ADescriptions'),
  ADescriptionsItem: passthrough('ADescriptionsItem'),
  ADrawer: passthrough('ADrawer'),
  AEmpty: passthrough('AEmpty'),
  AForm: passthrough('AForm'),
  AFormItem: passthrough('AFormItem'),
  AInput: passthrough('AInput'),
  AModal: passthrough('AModal'),
  APagination: passthrough('APagination'),
  ARow: passthrough('ARow'),
  ASelect: passthrough('ASelect'),
  ASpace: passthrough('ASpace'),
  ATable: tableStub,
  ATag: passthrough('ATag'),
  ATextarea: passthrough('ATextarea'),
}

beforeEach(() => {
  vi.clearAllMocks()
  Object.keys(routeQuery).forEach((key) => delete routeQuery[key])
  authUser.role = 'engineer'
  projectList.mockResolvedValue([{ id: 1, name: 'Core' }])
  memberList.mockResolvedValue([{ user_id: 8, username: 'qa', email: 'qa@example.com', role: 'editor', created_at: '2026-08-24T00:00:00Z' }])
  defectList.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  defectUpdate.mockResolvedValue(undefined)
  bugTrackerList.mockResolvedValue([])
  defectCreateExternal.mockResolvedValue(undefined)
})

describe('DefectListView', () => {
  it('loads project members and defects on mount', async () => {
    const wrapper = mount(DefectListView, { global: { stubs: globalStubs } })
    await flushPromises()

    expect(projectList).toHaveBeenCalledOnce()
    expect(defectList).toHaveBeenCalledWith({
      project_id: undefined,
      status: undefined,
      priority: undefined,
      severity: undefined,
      page: 1,
      page_size: 20,
    })
    expect(wrapper.text()).toContain('defect.title')
    wrapper.unmount()
  })

  it('filters the list for a linked run without opening the create form', async () => {
    routeQuery.run_type = 'performance'
    routeQuery.run_id = '10'
    routeQuery.view = 'linked'
    const wrapper = mount(DefectListView, { global: { stubs: globalStubs } })
    await flushPromises()

    expect(defectList).toHaveBeenCalledWith({
      project_id: undefined,
      run_type: 'performance',
      run_id: 10,
      status: undefined,
      priority: undefined,
      severity: undefined,
      page: 1,
      page_size: 20,
    })
    expect((wrapper.vm as any).createOpen).toBe(false)
    wrapper.unmount()
  })

  it('creates an external issue mapping from the defect detail', async () => {
    defectList.mockResolvedValue({
      items: [{
        id: 11,
        project_id: 1,
        case_id: null,
        title: 'Login failed',
        description: 'HTTP 500',
        status: 'open',
        priority: 'P2',
        severity: 'major',
        labels: [],
        occurrence_count: 1,
        creator_id: 7,
        assignee_id: null,
        created_at: '2026-08-24T00:00:00Z',
        updated_at: '2026-08-24T00:00:00Z',
        run_links: [],
        external_links: [],
      }],
      total: 1,
      page: 1,
      page_size: 20,
    })
    bugTrackerList.mockResolvedValue([{ id: 5, name: 'Jira', project_id: 1, tracker_type: 'jira', config: {}, field_mapping: {}, is_enabled: true, created_at: '', updated_at: '' }])
    const externalLink = { id: 21, defect_id: 11, tracker_id: 5, tracker_name: 'Jira', tracker_type: 'jira', external_key: 'ATP-21', external_url: 'https://jira.example/ATP-21', external_title: 'Login failed', external_status: null, sync_state: 'linked', last_synced_at: null, last_error: null, created_by: 7, created_at: '', updated_at: '' }
    defectCreateExternal.mockResolvedValue(externalLink)

    const wrapper = mount(DefectListView, { global: { stubs: globalStubs } })
    await flushPromises()
    await wrapper.find('.title-button').trigger('click')
    await flushPromises()
    const vm = wrapper.vm as any
    vm.openExternalModal('create')
    await vm.submitExternal()

    expect(defectCreateExternal).toHaveBeenCalledWith(11, { tracker_id: 5 })
    expect(vm.selectedDefect.external_links).toEqual([externalLink])
    wrapper.unmount()
  })

  it('hides external mutation actions for viewers', async () => {
    authUser.role = 'viewer'
    defectList.mockResolvedValue({
      items: [{
        id: 11,
        project_id: 1,
        case_id: null,
        title: 'Login failed',
        description: 'HTTP 500',
        status: 'open',
        priority: 'P2',
        severity: 'major',
        labels: [],
        occurrence_count: 1,
        creator_id: 7,
        assignee_id: null,
        created_at: '2026-08-24T00:00:00Z',
        updated_at: '2026-08-24T00:00:00Z',
        run_links: [],
        external_links: [{
          id: 21,
          defect_id: 11,
          tracker_id: 5,
          tracker_name: 'Jira',
          tracker_type: 'jira',
          external_key: 'ATP-21',
          external_url: 'https://jira.example/ATP-21',
          external_title: 'Login failed',
          external_status: 'Open',
          sync_state: 'linked',
          last_synced_at: null,
          last_error: null,
          created_by: 7,
          created_at: '',
          updated_at: '',
        }],
      }],
      total: 1,
      page: 1,
      page_size: 20,
    })

    const wrapper = mount(DefectListView, { global: { stubs: globalStubs } })
    await flushPromises()
    await wrapper.find('.title-button').trigger('click')
    await flushPromises()

    expect(wrapper.find('.external-card-actions').exists()).toBe(false)
    expect(bugTrackerList).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
