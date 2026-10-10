import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  time: string
}

export interface ChatSession {
  id: string
  title: string
  messages: ChatMessage[]
  projectId?: number
  updatedAt: string
}

const STORAGE_KEY = 'atp_ai_chat_sessions'
const ACTIVE_KEY = 'atp_ai_chat_active_id'

function nowTime(): string {
  const d = new Date()
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso)
    return `${d.getMonth() + 1}月${d.getDate()}日 ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
  } catch {
    return iso
  }
}

export const useAiChatStore = defineStore('aiChat', () => {
  const sessions = ref<ChatSession[]>([])
  const currentSessionId = ref<string>('')
  const initialized = ref(false)

  const currentSession = computed(() => {
    return sessions.value.find((s) => s.id === currentSessionId.value) || null
  })

  const currentMessages = computed(() => {
    return currentSession.value?.messages || []
  })

  function loadFromStorage() {
    if (initialized.value) return
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (raw) {
        const parsed = JSON.parse(raw) as unknown
        if (Array.isArray(parsed)) {
          sessions.value = parsed.filter(
            (item): item is ChatSession =>
              typeof item === 'object' &&
              item !== null &&
              typeof item.id === 'string' &&
              typeof item.title === 'string' &&
              Array.isArray(item.messages)
          )
        }
      }

      const activeId = localStorage.getItem(ACTIVE_KEY)
      if (activeId && sessions.value.some((s) => s.id === activeId)) {
        currentSessionId.value = activeId
      } else if (sessions.value.length > 0) {
        currentSessionId.value = sessions.value[0].id
      } else {
        createSession()
      }
    } catch {
      if (sessions.value.length === 0) {
        createSession()
      }
    } finally {
      initialized.value = true
    }
  }

  function saveToStorage() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions.value))
      localStorage.setItem(ACTIVE_KEY, currentSessionId.value)
    } catch {
      // 容错处理
    }
  }

  function createSession(title = '新对话', projectId?: number): ChatSession {
    const newSession: ChatSession = {
      id: `session-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      title,
      messages: [],
      projectId,
      updatedAt: new Date().toISOString(),
    }
    sessions.value.unshift(newSession)
    currentSessionId.value = newSession.id
    saveToStorage()
    return newSession
  }

  function switchSession(id: string) {
    if (sessions.value.some((s) => s.id === id)) {
      currentSessionId.value = id
      saveToStorage()
    }
  }

  function deleteSession(id: string) {
    const idx = sessions.value.findIndex((s) => s.id === id)
    if (idx !== -1) {
      sessions.value.splice(idx, 1)
      if (currentSessionId.value === id) {
        if (sessions.value.length > 0) {
          currentSessionId.value = sessions.value[0].id
        } else {
          createSession()
        }
      }
      saveToStorage()
    }
  }

  function appendMessage(role: 'user' | 'assistant', text: string) {
    let session = currentSession.value
    if (!session) {
      session = createSession()
    }

    const msg: ChatMessage = {
      id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      role,
      text,
      time: nowTime(),
    }

    session.messages.push(msg)
    session.updatedAt = new Date().toISOString()

    // 若是用户首次发言且为默认标题，根据问题提炼会话标题
    if (role === 'user' && (session.title === '新对话' || !session.title)) {
      session.title = text.slice(0, 24).trim() || '新对话'
    }

    saveToStorage()
    return session.messages[session.messages.length - 1]
  }

  function clearCurrentMessages() {
    const session = currentSession.value
    if (session) {
      session.messages = []
      session.title = '新对话'
      session.updatedAt = new Date().toISOString()
      saveToStorage()
    }
  }

  function setSessionProject(projectId?: number) {
    const session = currentSession.value
    if (session) {
      session.projectId = projectId
      saveToStorage()
    }
  }

  return {
    sessions,
    currentSessionId,
    currentSession,
    currentMessages,
    loadFromStorage,
    createSession,
    switchSession,
    deleteSession,
    appendMessage,
    clearCurrentMessages,
    setSessionProject,
    saveToStorage,
    formatDate,
  }
})
