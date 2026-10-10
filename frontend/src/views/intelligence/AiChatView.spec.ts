import { defineComponent, h } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import AiChatView from './AiChatView.vue'
import { useAiChatStore } from '@/stores/aiChat'

const { streamAiChatMock, projectList } = vi.hoisted(() => ({
  streamAiChatMock: vi.fn(
    async (
      _payload: { query: string },
      onToken: (token: string) => void
    ) => {
      onToken('这是大模型的自由回答内容。')
      return '这是大模型的自由回答内容。'
    }
  ),
  projectList: vi.fn(),
}))

vi.mock('@/api', () => ({
  streamAiChat: streamAiChatMock,
  projectApi: {
    list: projectList,
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}))

vi.mock('@ant-design/icons-vue', () => {
  const iconStub = { setup: () => () => null }
  return {
    ArrowRightOutlined: iconStub,
    DeleteOutlined: iconStub,
    HistoryOutlined: iconStub,
    MessageOutlined: iconStub,
    PlusOutlined: iconStub,
    ReloadOutlined: iconStub,
    RobotOutlined: iconStub,
    SendOutlined: iconStub,
    StopOutlined: iconStub,
  }
})

const passthrough = defineComponent({
  setup: (_props, { slots }) => () => h('div', slots.default?.()),
})

const globalStubs = {
  AButton: defineComponent({
    emits: ['click'],
    setup: (_props, { emit, slots }) => () => h('button', { onClick: () => emit('click') }, slots.default?.()),
  }),
  ASelect: passthrough,
  ATextarea: defineComponent({
    props: ['value'],
    emits: ['update:value'],
    setup: (props, { emit }) => () =>
      h('textarea', {
        value: props.value,
        onInput: (e: Event) => emit('update:value', (e.target as HTMLTextAreaElement).value),
      }),
  }),
}

describe('AiChatView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
    projectList.mockResolvedValue([
      { id: 1, name: '核心项目' },
      { id: 2, name: '二级项目' },
    ])
  })

  it('renders welcome state, loads projects, and streams chat messages', async () => {
    const wrapper = mount(AiChatView, {
      global: { stubs: globalStubs },
    })
    await flushPromises()

    expect(projectList).toHaveBeenCalled()
    expect(wrapper.text()).toContain('欢迎体验 ATP 自由 AI 助手')

    // Find and click a quick prompt
    const quickButtons = wrapper.findAll('.prompt-chip')
    expect(quickButtons.length).toBeGreaterThan(0)
    await quickButtons[0].trigger('click')
    await flushPromises()

    expect(streamAiChatMock).toHaveBeenCalledWith(
      expect.objectContaining({
        query: '帮我用 Python 写一个通用的接口测试签名算法',
        project_id: 1,
      }),
      expect.any(Function),
      expect.anything()
    )

    expect(wrapper.text()).toContain('这是大模型的自由回答内容。')
    wrapper.unmount()
  })

  it('persists messages in store and allows creating a new session', async () => {
    const wrapper = mount(AiChatView, {
      global: { stubs: globalStubs },
    })
    await flushPromises()

    const store = useAiChatStore()
    expect(store.sessions.length).toBe(1)

    const vm = wrapper.vm as unknown as {
      sendPrompt: (text: string) => void
      handleNewSession: () => void
      currentMessages: Array<{ text: string }>
    }

    vm.sendPrompt('你好，保存这条会话')
    await flushPromises()

    expect(store.currentMessages.length).toBe(2)
    expect(store.currentSession?.title).toBe('你好，保存这条会话')

    vm.handleNewSession()
    expect(store.sessions.length).toBe(2)
    expect(store.currentMessages.length).toBe(0)

    wrapper.unmount()
  })
})
