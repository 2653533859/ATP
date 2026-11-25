import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import SpecialTaskListView from './SpecialTaskListView.vue'

const {
  projectList,
  deviceList,
  apkList,
  listTasks,
  createTask,
  updateTask,
  deleteTask,
  triggerTask,
  routerPush,
  routeQuery,
  authState,
} = vi.hoisted(() => ({
  projectList: vi.fn(),
  deviceList: vi.fn(),
  apkList: vi.fn(),
  listTasks: vi.fn(),
  createTask: vi.fn(),
  updateTask: vi.fn(),
  deleteTask: vi.fn(),
  triggerTask: vi.fn(),
  routerPush: vi.fn(),
  routeQuery: {} as Record<string, string>,
  authState: { user: { role: 'admin' } },
}))

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (k: string) => k }) }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: routeQuery }),
  useRouter: () => ({ push: routerPush }),
}))
vi.mock('ant-design-vue', () => ({
  message: { error: vi.fn(), success: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => authState }))
vi.mock('@/runtimeMode', () => ({ getRuntimeMode: () => ({ mode: 'server' }) }))
vi.mock('@/utils/devicePackages', () => ({
  loadDevicePackagesAsync: vi.fn().mockResolvedValue({ packages: [], current_package: null }),
}))
vi.mock('@/api', () => ({
  projectApi: { list: projectList },
  deviceApi: { list: deviceList },
  apkApi: { list: apkList },
  mobileSpecialApi: {
    listTasks,
    createTask,
    updateTask,
    deleteTask,
    triggerTask,
  },
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_p, { slots }) => () => h('div', slots.default?.()) })

const buttonStub = defineComponent({
  name: 'AButton',
  props: { disabled: Boolean },
  emits: ['click'],
  setup: (props, { slots, emit }) => () =>
    h('button', { disabled: props.disabled, onClick: () => emit('click') }, slots.default?.()),
})

const tableStub = defineComponent({
  name: 'ATable',
  props: ['dataSource'],
  setup: (props, { slots }) => () =>
    h(
      'div',
      (props.dataSource || []).map((record: Record<string, unknown>) =>
        h('div', { class: 'task-row', key: String(record.id) }, [
          slots.bodyCell?.({ column: { key: 'action' }, record }),
        ]),
      ),
    ),
})

function mountView() {
  return mount(SpecialTaskListView, {
    global: {
      stubs: {
        AButton: buttonStub,
        ACheckbox: passthrough('ACheckbox'),
        ADivider: passthrough('ADivider'),
        ADrawer: passthrough('ADrawer'),
        AForm: passthrough('AForm'),
        AFormItem: passthrough('AFormItem'),
        AInput: passthrough('AInput'),
        AInputNumber: passthrough('AInputNumber'),
        APopconfirm: passthrough('APopconfirm'),
        ASelect: passthrough('ASelect'),
        ASpin: passthrough('ASpin'),
        ASwitch: passthrough('ASwitch'),
        ATable: tableStub,
        ATag: passthrough('ATag'),
        ATextarea: passthrough('ATextarea'),
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  authState.user = { role: 'admin' }
  delete routeQuery.project_id
  projectList.mockResolvedValue([{ id: 3, name: 'Mobile', current_user_role: 'owner' }])
  deviceList.mockResolvedValue([{ id: 10, serial: 'emu-1', status: 'online' }])
  apkList.mockResolvedValue([])
  listTasks.mockResolvedValue([
    {
      id: 1,
      project_id: 3,
      name: 'Monkey Smoke',
      task_type: 'stability',
      source_type: 'apk_only',
      device_scope_type: 'single_device',
      schedule_enabled: false,
      created_at: '',
      updated_at: '',
    },
  ])
})

describe('SpecialTaskListView regressions', () => {
  it('hides unimplemented source/scope options and clears state on project reset', async () => {
    const wrapper = mountView()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      sourceTypeOptions: Array<{ value: string }>
      deviceScopeOptions: Array<{ value: string }>
      selectedProjectId: number | null
      tasks: unknown[]
      onProjectChange: () => void
    }

    expect(vm.sourceTypeOptions.map((o) => o.value)).toEqual(['apk_only', 'monkey'])
    expect(vm.deviceScopeOptions.map((o) => o.value)).toEqual(['single_device'])
    expect(vm.tasks).toHaveLength(1)

    vm.selectedProjectId = null
    vm.onProjectChange()
    expect(vm.tasks).toEqual([])
    wrapper.unmount()
  })

  it('disables write buttons when user only holds project viewer role', async () => {
    authState.user = { role: 'tester' }
    projectList.mockResolvedValueOnce([{ id: 3, name: 'Mobile', current_user_role: 'viewer' }])
    const wrapper = mountView()
    await flushPromises()

    const vm = wrapper.vm as unknown as { canModify: boolean }
    expect(vm.canModify).toBe(false)

    const createBtn = wrapper.findAll('button').find((b) => b.text().includes('mobile_special.new_task'))!
    const execBtn = wrapper.findAll('button').find((b) => b.text() === 'mobile_special.execute')!
    const editBtn = wrapper.findAll('button').find((b) => b.text() === 'common.edit')!
    const delBtn = wrapper.findAll('button').find((b) => b.text() === 'common.delete')!
    expect(createBtn.attributes('disabled')).toBeDefined()
    expect(execBtn.attributes('disabled')).toBeDefined()
    expect(editBtn.attributes('disabled')).toBeDefined()
    expect(delBtn.attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })
})
