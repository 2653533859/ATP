import { defineComponent, h, ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import HermesAssistantView from './HermesAssistantView.vue'

const {
  caseList,
  defectList,
  executeAiChatAction,
  projectList,
  reportOverview,
  routerPush,
  streamAiChat,
  taskList,
} = vi.hoisted(() => ({
  caseList: vi.fn(),
  defectList: vi.fn(),
  executeAiChatAction: vi.fn(),
  projectList: vi.fn(),
  reportOverview: vi.fn(),
  routerPush: vi.fn(),
  streamAiChat: vi.fn(),
  taskList: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: { project_id: '1' } }),
  useRouter: () => ({ push: routerPush }),
}))
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    locale: ref('zh-CN'),
    t: (key: string) => key,
  }),
}))
vi.mock('ant-design-vue', () => ({
  message: { error: vi.fn(), success: vi.fn(), warning: vi.fn() },
}))
vi.mock('@/api', () => ({
  projectApi: { list: projectList },
  caseApi: { list: caseList },
  reportApi: { overview: reportOverview },
  defectApi: { list: defectList },
  workbenchApi: { tasks: taskList },
}))
vi.mock('@/api/aiChat', () => ({
  streamAiChat,
  executeAiChatAction,
}))

const ButtonStub = defineComponent({
  name: 'AButton',
  props: { disabled: Boolean, loading: Boolean },
  emits: ['click'],
  setup(props, { slots, emit }) {
    return () =>
      h('button', { type: 'button', disabled: props.disabled, onClick: () => emit('click') }, slots.default?.())
  },
})

const SelectStub = defineComponent({
  name: 'ASelect',
  props: ['value', 'options'],
  emits: ['update:value', 'change'],
  setup(props, { emit }) {
    return () =>
      h(
        'select',
        {
          value: props.value ?? '',
          onChange: (e: Event) => {
            const raw = (e.target as HTMLSelectElement).value
            const next = raw ? Number(raw) : undefined
            emit('update:value', next)
            emit('change', next)
          },
        },
        (props.options || []).map((opt: { label: string; value: number }) =>
          h('option', { value: opt.value }, opt.label),
        ),
      )
  },
})

function mountView() {
  return mount(HermesAssistantView, {
    global: {
      stubs: {
        'a-button': ButtonStub,
        'a-select': SelectStub,
        'a-tag': { template: '<span><slot /></span>' },
        'a-empty': { props: ['description'], template: '<div>{{ description }}</div>' },
        RobotOutlined: true,
        HistoryOutlined: true,
        DashboardOutlined: true,
        PlusOutlined: true,
        MessageOutlined: true,
        DeleteOutlined: true,
        UserOutlined: true,
        SendOutlined: true,
        ReloadOutlined: true,
      },
    },
  })
}

describe('HermesAssistantView', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()

    projectList.mockResolvedValue([{ id: 1, name: '支付网关项目' }])
    caseList.mockResolvedValue([{ id: 10, name: '登录验证' }, { id: 11, name: '下单支付' }])
    reportOverview.mockResolvedValue({ total_runs: 20, pass_rate: 85.0 })
    defectList.mockResolvedValue({ total: 2, items: [] })
    taskList.mockResolvedValue({
      items: [{ task_type: 'case', run_id: 42, name: '下单支付超时', status: 'failed' }],
    })
  })

  it('loads project snapshot and renders failure tasks', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(projectList).toHaveBeenCalled()
    expect(caseList).toHaveBeenCalledWith({ project_id: 1 })
    expect(wrapper.text()).toContain('85.0%')
    expect(wrapper.text()).toContain('下单支付超时')
  })

  it('streams project-aware response with tool events and executes confirmed action', async () => {
    streamAiChat.mockImplementation(async (_payload, onToken, _signal, callbacks) => {
      callbacks?.onToolEvent?.({ tool: 'failed_tasks', label: '失败任务', summary: '1 条' })
      callbacks?.onActionProposal?.({
        action: 'run_case',
        title: '执行测试用例 #11',
        summary: '验证下单支付流程',
        params: { case_id: 11 },
      })
      onToken('已查询失败记录，建议重新执行用例 #11。')
      return '已查询失败记录，建议重新执行用例 #11。'
    })
    executeAiChatAction.mockResolvedValue({
      ok: true,
      action: 'run_case',
      message: '已触发执行用例 #11（运行 ID: #99）',
      resource_id: 99,
      route: '/runs/99',
    })

    const wrapper = mountView()
    await flushPromises()

    await wrapper.find('.failure-item').trigger('click')
    await flushPromises()

    expect(streamAiChat).toHaveBeenCalled()
    expect(wrapper.text()).toContain('失败任务 · 1 条')
    expect(wrapper.text()).toContain('执行测试用例 #11')

    const confirmBtn = wrapper.findAll('button').find((b) => b.text().includes('确认执行'))
    expect(confirmBtn).toBeTruthy()
    await confirmBtn!.trigger('click')
    await flushPromises()

    expect(executeAiChatAction).toHaveBeenCalledWith({
      project_id: 1,
      action: 'run_case',
      params: { case_id: 11 },
    })
    expect(wrapper.text()).toContain('已触发执行用例 #11')
  })
})
