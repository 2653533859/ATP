import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import TaskCenterView from './TaskCenterView.vue'
import WorkbenchTodosView from './WorkbenchTodosView.vue'

const {
  overview,
  tasks,
  projectList,
  routerReplace,
  routerPush,
  retry,
  stop,
  batchAction,
  modalConfirm,
} = vi.hoisted(() => ({
  overview: vi.fn(),
  tasks: vi.fn(),
  projectList: vi.fn(),
  routerReplace: vi.fn(),
  routerPush: vi.fn(),
  retry: vi.fn(),
  stop: vi.fn(),
  batchAction: vi.fn(),
  modalConfirm: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ replace: routerReplace, push: routerPush }),
}))
vi.mock('vue-i18n', () => ({
  useI18n: () => ({ locale: ref('zh-CN'), t: (key: string) => key }),
}))
vi.mock('ant-design-vue', () => ({
  message: { error: vi.fn(), success: vi.fn(), warning: vi.fn() },
  Modal: { confirm: modalConfirm },
}))
vi.mock('@ant-design/icons-vue', () => ({ ReloadOutlined: true }))
vi.mock('@/api', () => ({
  projectApi: { list: projectList },
  workbenchApi: {
    overview,
    tasks,
    retry,
    stop,
    batchAction,
  },
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

const buttonStub = defineComponent({
  name: 'AButton',
  props: { disabled: Boolean },
  emits: ['click'],
  setup(props, { slots, emit }) {
    return () => h('button', { disabled: props.disabled, onClick: () => emit('click') }, slots.default?.())
  },
})

const tableStub = defineComponent({
  name: 'ATable',
  props: {
    columns: { type: Array, default: () => [] },
    dataSource: { type: Array, default: () => [] },
  },
  setup(props, { slots }) {
    return () => h(
      'div',
      (props.dataSource as Array<Record<string, unknown>>).flatMap((record) =>
        (props.columns as Array<Record<string, unknown>>).map((column) =>
          slots.bodyCell?.({ column, record }),
        ),
      ),
    )
  },
})

const globalStubs = {
  AAlert: passthrough('AAlert'),
  AButton: buttonStub,
  ACard: passthrough('ACard'),
  ASelect: passthrough('ASelect'),
  ASelectOption: passthrough('ASelectOption'),
  AStatistic: passthrough('AStatistic'),
  ASpace: passthrough('ASpace'),
  ATable: tableStub,
  ATag: passthrough('ATag'),
  APagination: passthrough('APagination'),
  ReloadOutlined: true,
}

beforeEach(() => {
  vi.clearAllMocks()
  projectList.mockResolvedValue([{ id: 1, name: '核心项目' }])
  overview.mockResolvedValue({
    generated_at: '2026-08-24T10:00:00Z',
    project_id: null,
    counts: { pending_reviews: 1, failed_runs: 2, overdue_plans: 0, device_anomalies: 0, total_todos: 3 },
    todos: [],
    tasks: [],
    has_more_todos: false,
    has_more_tasks: false,
  })
  tasks.mockResolvedValue({
    generated_at: '2026-08-24T10:00:00Z',
    project_id: null,
    items: [],
    total: 0,
    has_more: false,
  })
  stop.mockResolvedValue({ message: 'stopped' })
  routerReplace.mockResolvedValue(undefined)
})

describe('WorkbenchTodosView', () => {
  it('loads projects and aggregated todos on mount', async () => {
    const wrapper = mount(WorkbenchTodosView, { global: { stubs: globalStubs } })
    await flushPromises()

    expect(projectList).toHaveBeenCalledOnce()
    expect(overview).toHaveBeenCalledWith({
      project_id: undefined,
      todo_limit: 50,
      todo_offset: 0,
      task_limit: 100,
    })
    expect(wrapper.text()).toContain('workbench.todos_title')

    wrapper.unmount()
  })
})

describe('TaskCenterView', () => {
  it('loads the unified task list and clears its refresh timer on unmount', async () => {
    const wrapper = mount(TaskCenterView, { global: { stubs: globalStubs } })
    await flushPromises()

    expect(projectList).toHaveBeenCalledOnce()
    expect(tasks).toHaveBeenCalledWith({
      project_id: undefined,
      status: undefined,
      task_type: undefined,
      limit: 50,
      offset: 0,
    })
    expect(wrapper.text()).toContain('task_center.title')

    wrapper.unmount()
  })

  it('confirms before stopping an individual task', async () => {
    tasks.mockResolvedValue({
      generated_at: '2026-08-24T10:00:00Z',
      project_id: null,
      items: [{
        id: 'android:8',
        task_type: 'android',
        run_id: 8,
        name: '设备任务',
        project_name: '核心项目',
        status: 'running',
        created_at: '2026-08-24T10:00:00Z',
        detail_path: '/mobile-special/reports/8',
        can_retry: false,
        can_stop: true,
      }],
      total: 1,
      has_more: false,
    })
    const wrapper = mount(TaskCenterView, { global: { stubs: globalStubs } })
    await flushPromises()

    const stopButton = wrapper.findAll('button').find((button) => button.text() === 'task_center.stop')
    expect(stopButton).toBeDefined()
    await stopButton!.trigger('click')

    expect(modalConfirm).toHaveBeenCalledOnce()
    const options = modalConfirm.mock.calls[0][0]
    expect(options.title).toBe('task_center.stop_confirm_title')
    expect(options.content).toBe('task_center.stop_confirm_content')
    expect(stop).not.toHaveBeenCalled()

    await options.onOk()
    expect(stop).toHaveBeenCalledWith('android', 8)
    wrapper.unmount()
  })
})
