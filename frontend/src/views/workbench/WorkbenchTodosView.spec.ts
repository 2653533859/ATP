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
} = vi.hoisted(() => ({
  overview: vi.fn(),
  tasks: vi.fn(),
  projectList: vi.fn(),
  routerReplace: vi.fn(),
  routerPush: vi.fn(),
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
}))
vi.mock('@ant-design/icons-vue', () => ({ ReloadOutlined: true }))
vi.mock('@/api', () => ({
  projectApi: { list: projectList },
  workbenchApi: {
    overview,
    tasks,
    retry: vi.fn(),
    stop: vi.fn(),
    batchAction: vi.fn(),
  },
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

const globalStubs = {
  AAlert: passthrough('AAlert'),
  AButton: passthrough('AButton'),
  ACard: passthrough('ACard'),
  ASelect: passthrough('ASelect'),
  ASelectOption: passthrough('ASelectOption'),
  AStatistic: passthrough('AStatistic'),
  ASpace: passthrough('ASpace'),
  ATable: passthrough('ATable'),
  ATag: passthrough('ATag'),
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
  routerReplace.mockResolvedValue(undefined)
})

describe('WorkbenchTodosView', () => {
  it('loads projects and aggregated todos on mount', async () => {
    const wrapper = mount(WorkbenchTodosView, { global: { stubs: globalStubs } })
    await flushPromises()

    expect(projectList).toHaveBeenCalledOnce()
    expect(overview).toHaveBeenCalledWith({ project_id: undefined, todo_limit: 100, task_limit: 100 })
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
      limit: 200,
    })
    expect(wrapper.text()).toContain('task_center.title')

    wrapper.unmount()
  })
})
