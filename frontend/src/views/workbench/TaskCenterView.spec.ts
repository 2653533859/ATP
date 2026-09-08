import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import TaskCenterView from './TaskCenterView.vue'

const {
  projectList,
  taskList,
  retryTask,
  stopTask,
  batchAction,
  failureDiagnosis,
  caseDiagnosis,
  routerPush,
  routerReplace,
  confirm,
} = vi.hoisted(() => ({
  projectList: vi.fn(),
  taskList: vi.fn(),
  retryTask: vi.fn(),
  stopTask: vi.fn(),
  batchAction: vi.fn(),
  failureDiagnosis: vi.fn(),
  caseDiagnosis: vi.fn(),
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
  confirm: vi.fn(),
}))

const route = { query: {} as Record<string, string> }

vi.mock('vue-router', () => ({
  useRoute: () => route,
  useRouter: () => ({ push: routerPush, replace: routerReplace }),
}))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('ant-design-vue', () => ({
  message: { error: vi.fn(), success: vi.fn(), warning: vi.fn() },
  Modal: { confirm },
}))
vi.mock('@/api', () => ({
  projectApi: { list: projectList },
  runApi: { generateFailureDiagnosis: caseDiagnosis },
  workbenchApi: {
    tasks: taskList,
    retry: retryTask,
    stop: stopTask,
    batchAction,
    failureDiagnosis,
  },
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

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
      { 'data-test': 'task-table' },
      (props.dataSource || []).map((record: Record<string, unknown>) =>
        h('div', { class: 'task-row', key: String(record.id) }, [
          slots.bodyCell?.({ column: { key: 'action' }, record }),
        ]),
      ),
    ),
})

const mountedWrappers: Array<{ unmount: () => void }> = []

function mountPage() {
  const wrapper = mount(TaskCenterView, {
    global: {
      stubs: {
        AAlert: passthrough('AAlert'),
        AButton: buttonStub,
        AEmpty: passthrough('AEmpty'),
        AModal: passthrough('AModal'),
        APagination: passthrough('APagination'),
        ASelect: passthrough('ASelect'),
        ASelectOption: passthrough('ASelectOption'),
        ASpace: passthrough('ASpace'),
        ASpin: passthrough('ASpin'),
        ATable: tableStub,
        ATag: passthrough('ATag'),
        ReloadOutlined: true,
        ScheduleOutlined: true,
      },
    },
  })
  mountedWrappers.push(wrapper)
  return wrapper
}

function task(overrides: Record<string, unknown> = {}) {
  return {
    id: 'case:11',
    task_type: 'case',
    run_id: 11,
    project_id: 7,
    project_name: 'ATP',
    name: '登录回归',
    status: 'failed',
    created_at: '2026-09-09T01:00:00Z',
    detail_path: '/runs/11?project_id=7',
    can_retry: false,
    can_stop: false,
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  route.query = {}
  projectList.mockResolvedValue([{ id: 7, name: 'ATP' }])
  taskList.mockResolvedValue({ items: [], total: 0, generated_at: '2026-09-09T01:00:00Z', has_more: false })
  retryTask.mockResolvedValue({ message: 'ok' })
})

afterEach(() => {
  mountedWrappers.splice(0).forEach((wrapper) => wrapper.unmount())
})

describe('TaskCenterView role and deep-link contract', () => {
  it('restores project, filters, and bounded page offset from a deep link', async () => {
    route.query = { project_id: '7', status: 'failed', task_type: 'case', page: '2' }

    mountPage()
    await flushPromises()

    expect(taskList).toHaveBeenCalledWith({
      project_id: 7,
      status: 'failed',
      task_type: 'case',
      limit: 50,
      offset: 50,
    })
    expect(routerReplace).not.toHaveBeenCalled()
  })

  it('does not render retry or stop controls when the server disables viewer actions', async () => {
    taskList.mockResolvedValue({
      items: [task()],
      total: 1,
      generated_at: '2026-09-09T01:00:00Z',
      has_more: false,
    })

    const wrapper = mountPage()
    await flushPromises()

    const labels = wrapper.findAll('button').map((button) => button.text())
    expect(labels).toContain('task_center.diagnose')
    expect(labels).not.toContain('task_center.retry')
    expect(labels).not.toContain('task_center.stop')
    expect(retryTask).not.toHaveBeenCalled()
    expect(stopTask).not.toHaveBeenCalled()
  })

  it('renders and executes only an action explicitly enabled by the server', async () => {
    taskList.mockResolvedValue({
      items: [task({ can_retry: true })],
      total: 1,
      generated_at: '2026-09-09T01:00:00Z',
      has_more: false,
    })

    const wrapper = mountPage()
    await flushPromises()
    const retryButton = wrapper.findAll('button').find((button) => button.text() === 'task_center.retry')

    expect(retryButton).toBeDefined()
    await retryButton!.trigger('click')
    await flushPromises()

    expect(retryTask).toHaveBeenCalledWith('case', 11)
    expect(stopTask).not.toHaveBeenCalled()
  })
})
