import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import DefectListView from './DefectListView.vue'

const {
  authUser,
  routeQuery,
  modalConfirm,
  bugTrackerList,
  defectCreateExternal,
  defectPushExternal,
  defectLinkRun,
  defectUnlinkRun,
  projectList,
  memberList,
  defectList,
  defectUpdate,
  defectDelete,
  routerPush,
} = vi.hoisted(() => ({
  authUser: { role: 'engineer' as string },
  routeQuery: {} as Record<string, string>,
  modalConfirm: vi.fn(),
  bugTrackerList: vi.fn(),
  defectCreateExternal: vi.fn(),
  defectPushExternal: vi.fn(),
  defectLinkRun: vi.fn(),
  defectUnlinkRun: vi.fn(),
  projectList: vi.fn(),
  memberList: vi.fn(),
  defectList: vi.fn(),
  defectUpdate: vi.fn(),
  defectDelete: vi.fn(),
  routerPush: vi.fn(),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string, params?: Record<string, unknown>) => params ? `${key}:${JSON.stringify(params)}` : key }),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: routeQuery }),
  useRouter: () => ({ replace: vi.fn(), push: routerPush }),
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: authUser }) }))
vi.mock('ant-design-vue', () => ({
  message: { error: vi.fn(), success: vi.fn(), warning: vi.fn() },
  Modal: { confirm: modalConfirm },
}))
vi.mock('@/api', () => ({
  bugTrackerApi: { list: bugTrackerList },
  projectApi: { list: projectList },
  projectMemberApi: { list: memberList },
  defectApi: {
    list: defectList,
    update: defectUpdate,
    delete: defectDelete,
    linkRun: defectLinkRun,
    unlinkRun: defectUnlinkRun,
    createExternal: defectCreateExternal,
    pushExternal: defectPushExternal,
  },
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', [slots.default?.(), slots.footer?.()]) })

const tableStub = defineComponent({
  name: 'ATable',
  props: ['dataSource'],
  setup: (props, { slots }) => () => h(
    'div',
    (props.dataSource || []).map((record: Record<string, unknown>) => h(
      'div',
      { class: 'defect-row', key: String(record.id) },
      [
        slots.bodyCell?.({ column: { key: 'title' }, record }),
        slots.bodyCell?.({ column: { key: 'actions' }, record }),
      ],
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
  AInputNumber: passthrough('AInputNumber'),
  AInputSearch: passthrough('AInputSearch'),
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
  defectDelete.mockResolvedValue(undefined)
  defectLinkRun.mockResolvedValue(undefined)
  defectUnlinkRun.mockResolvedValue(undefined)
  bugTrackerList.mockResolvedValue([])
  defectCreateExternal.mockResolvedValue(undefined)
  defectPushExternal.mockResolvedValue({})
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

  it('routes every linked run type to its owning report surface', async () => {
    const wrapper = mount(DefectListView, { global: { stubs: globalStubs } })
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedDefect = { project_id: 1 }

    vm.openRun({ run_type: 'case', run_id: 11 })
    vm.openRun({ run_type: 'android', run_id: 12 })
    vm.openRun({ run_type: 'performance', run_id: 13 })
    vm.openRun({ run_type: 'suite', run_id: 14 })
    vm.openRun({ run_type: 'plan', run_id: 15 })

    expect(routerPush).toHaveBeenNthCalledWith(1, { name: 'run-detail', params: { runId: 11 } })
    expect(routerPush).toHaveBeenNthCalledWith(2, { name: 'mobile-special-report-detail', params: { runId: 12 } })
    expect(routerPush).toHaveBeenNthCalledWith(3, {
      name: 'performance-workbench',
      query: { project_id: '1', run_id: '13' },
    })
    expect(routerPush).toHaveBeenNthCalledWith(4, { path: '/suites', query: { project_id: '1', run_id: '14' } })
    expect(routerPush).toHaveBeenNthCalledWith(5, { path: '/plans', query: { project_id: '1', run_id: '15' } })
    wrapper.unmount()
  })

  it('supports keyword filter, quick transitions, full detail editing, run linking, external push, and deletion', async () => {
    const sampleDefect = {
      id: 10,
      project_id: 1,
      case_id: null,
      title: '登录失败',
      description: '旧描述',
      status: 'open' as const,
      priority: 'P2' as const,
      severity: 'major' as const,
      resolution: null,
      labels: ['auth'],
      occurrence_count: 1,
      creator_id: 7,
      assignee_id: null,
      created_at: '2026-11-26T00:00:00Z',
      updated_at: '2026-11-26T00:00:00Z',
      run_links: [],
      external_links: [{
        id: 21,
        defect_id: 10,
        tracker_id: 5,
        tracker_name: 'Jira',
        tracker_type: 'jira',
        external_key: 'ATP-10',
        external_url: 'https://jira.example/ATP-10',
        external_title: '登录失败',
        external_status: 'Open',
        sync_state: 'linked',
        last_synced_at: null,
        last_error: null,
        created_by: 7,
        created_at: '',
        updated_at: '',
      }],
    }
    defectList.mockResolvedValue({ items: [sampleDefect], total: 1, page: 1, page_size: 20 })
    defectUpdate.mockImplementation(async (_id, payload) => ({ ...sampleDefect, ...payload }))
    defectLinkRun.mockResolvedValue({ id: 31, run_type: 'case', run_id: 245, case_id: 109, evidence: {}, linked_by: 7, created_at: '' })

    const wrapper = mount(DefectListView, { global: { stubs: globalStubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('defect.total_count:{"count":1}')

    const vm = wrapper.vm as any
    vm.keywordFilter = '登录'
    vm.reloadFirstPage()
    await flushPromises()
    expect(defectList).toHaveBeenLastCalledWith(expect.objectContaining({ keyword: '登录', page: 1 }))

    // 快捷状态流转
    await vm.quickTransitionStatus(sampleDefect, 'in_progress')
    expect(defectUpdate).toHaveBeenCalledWith(10, { status: 'in_progress' })

    // 打开详情验证状态机约束与全字段编辑
    vm.openDetail(vm.defects[0])
    await flushPromises()
    expect(vm.detailStatusOptions.map((item: { value: string }) => item.value)).toEqual(['in_progress', 'open', 'resolved'])

    vm.editForm.title = '登录超时失败'
    vm.editForm.description = '补充复现步骤'
    vm.editForm.labels = 'auth, p1'
    vm.editForm.resolution = '增加重试'
    await vm.submitUpdate()
    expect(defectUpdate).toHaveBeenLastCalledWith(10, expect.objectContaining({
      title: '登录超时失败',
      description: '补充复现步骤',
      labels: ['auth', 'p1'],
      resolution: '增加重试',
    }))

    // 关联/解绑执行记录与推送外部状态
    vm.openLinkRunModal()
    vm.linkRunForm.run_type = 'case'
    vm.linkRunForm.run_id = 245
    await vm.submitLinkRun()
    expect(defectLinkRun).toHaveBeenCalledWith(10, { run_type: 'case', run_id: 245 })
    expect(vm.selectedDefect.run_links).toHaveLength(1)

    await vm.pushExternalLink(sampleDefect.external_links[0])
    expect(defectPushExternal).toHaveBeenCalledWith(10, 21)

    vm.confirmUnlinkRun(vm.selectedDefect.run_links[0])
    await modalConfirm.mock.calls[0][0].onOk()
    expect(defectUnlinkRun).toHaveBeenCalledWith(10, 31)
    expect(vm.selectedDefect.run_links).toHaveLength(0)

    // 删除缺陷
    vm.confirmDeleteDefect(vm.selectedDefect)
    await modalConfirm.mock.calls[1][0].onOk()
    expect(defectDelete).toHaveBeenCalledWith(10)
    expect(vm.detailOpen).toBe(false)
    wrapper.unmount()
  })
})
