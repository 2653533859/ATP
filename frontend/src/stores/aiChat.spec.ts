import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useAiChatStore } from './aiChat'

describe('useAiChatStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('initializes with a default session', () => {
    const store = useAiChatStore()
    store.loadFromStorage()

    expect(store.sessions.length).toBe(1)
    expect(store.currentSessionId).toBeTruthy()
    expect(store.currentMessages.length).toBe(0)
  })

  it('appends user and assistant messages, updating session title from first user prompt', () => {
    const store = useAiChatStore()
    store.loadFromStorage()

    store.appendMessage('user', '写一个接口测试用例')
    expect(store.currentMessages.length).toBe(1)
    expect(store.currentSession?.title).toBe('写一个接口测试用例')

    store.appendMessage('assistant', '这是测试用例内容')
    expect(store.currentMessages.length).toBe(2)
  })

  it('persists sessions to localStorage and restores on next load', () => {
    const store1 = useAiChatStore()
    store1.loadFromStorage()
    store1.appendMessage('user', '第一条会话')
    store1.appendMessage('assistant', '回复')

    // Create a new store instance with fresh pinia
    setActivePinia(createPinia())
    const store2 = useAiChatStore()
    store2.loadFromStorage()

    expect(store2.sessions.length).toBe(1)
    expect(store2.currentMessages.length).toBe(2)
    expect(store2.currentMessages[0].text).toBe('第一条会话')
  })

  it('supports creating, switching and deleting sessions', () => {
    const store = useAiChatStore()
    store.loadFromStorage()

    const session1 = store.currentSessionId
    const session2 = store.createSession('第二个会话')

    expect(store.sessions.length).toBe(2)
    expect(store.currentSessionId).toBe(session2.id)

    store.switchSession(session1)
    expect(store.currentSessionId).toBe(session1)

    store.deleteSession(session1)
    expect(store.sessions.length).toBe(1)
    expect(store.currentSessionId).toBe(session2.id)
  })
})
