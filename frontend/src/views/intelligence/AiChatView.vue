<template>
  <div class="page-shell ai-chat-page">
    <header class="chat-toolbar">
      <div class="toolbar-left">
        <div class="toolbar-identity">
          <MessageOutlined class="toolbar-icon" />
          <span class="toolbar-name">AI 自由对话</span>
        </div>
        <div class="toolbar-sep">/</div>
        <div class="toolbar-project">
          <label for="chat-project" class="sr-only">项目上下文</label>
          <a-select
            id="chat-project"
            v-model:value="selectedProjectId"
            :options="projectOptions"
            allow-clear
            size="small"
            class="project-select-dropdown"
            placeholder="项目上下文（可选）"
            @change="handleProjectChange"
          />
        </div>
        <span class="status-badge">
          <span class="live-dot" />
          <span>自由对话模式（不设资产门禁 · 自动保存）</span>
        </span>
      </div>

      <div class="toolbar-right">
        <a-button
          size="small"
          class="toolbar-btn"
          :class="{ 'toolbar-btn-active': historyVisible }"
          @click="historyVisible = !historyVisible"
        >
          <HistoryOutlined /> 历史记录 ({{ chatStore.sessions.length }})
        </a-button>
        <a-button type="primary" size="small" class="toolbar-btn primary-btn" @click="handleNewSession">
          <PlusOutlined /> 新会话
        </a-button>
      </div>
    </header>

    <main class="chat-main" role="region" aria-label="AI 自由对话工作区">
      <!-- 历史会话侧边栏 -->
      <aside v-if="historyVisible" class="history-sidebar" aria-label="历史会话列表">
        <div class="history-sidebar-header">
          <span>历史会话 ({{ chatStore.sessions.length }})</span>
          <a-button type="text" size="small" @click="handleNewSession">
            <PlusOutlined /> 新建
          </a-button>
        </div>

        <div class="history-list">
          <div
            v-for="session in chatStore.sessions"
            :key="session.id"
            class="history-item"
            :class="{ active: session.id === chatStore.currentSessionId }"
            @click="chatStore.switchSession(session.id)"
          >
            <MessageOutlined class="history-item-icon" />
            <div class="history-item-body">
              <span class="history-item-title">{{ session.title }}</span>
              <small class="history-item-time">{{ formatSessionTime(session.updatedAt) }}</small>
            </div>
            <a-button
              type="text"
              size="small"
              class="history-item-del"
              title="删除此会话"
              @click.stop="chatStore.deleteSession(session.id)"
            >
              <DeleteOutlined />
            </a-button>
          </div>
        </div>
      </aside>

      <!-- 核心对话区 -->
      <section class="chat-workspace">
        <div class="messages-container" ref="messagesContainer">
          <!-- 欢迎看板与快捷提问 -->
          <div v-if="currentMessages.length === 0 && !isStreaming" class="welcome-box">
            <div class="welcome-avatar">
              <RobotOutlined />
            </div>
            <h2>欢迎体验 ATP 自由 AI 助手</h2>
            <p class="welcome-desc">
              当前处于自由闲聊模式：无需检索特定项目测试资产，不设严谨引用门禁。您可以咨询任何自动化测试框架设计、Python/TypeScript 编程、接口调试思路或进行日常轻松闲聊，对话记录将自动实时保存。
            </p>

            <div class="quick-prompts">
              <span class="prompts-title">您可以试试这样提问：</span>
              <div class="prompts-grid">
                <button
                  v-for="(prompt, idx) in quickPrompts"
                  :key="idx"
                  type="button"
                  class="prompt-chip"
                  :disabled="loading"
                  @click="sendPrompt(prompt.text)"
                >
                  <span class="prompt-chip-icon">{{ prompt.icon }}</span>
                  <span class="prompt-chip-content">
                    <strong>{{ prompt.title }}</strong>
                    <small>{{ prompt.text }}</small>
                  </span>
                  <ArrowRightOutlined class="prompt-chip-arrow" />
                </button>
              </div>
            </div>
          </div>

          <!-- 消息流 -->
          <div v-else class="message-stream">
            <article
              v-for="msg in currentMessages"
              :key="msg.id"
              class="message-row"
              :class="`message-${msg.role}`"
            >
              <div class="message-avatar" aria-hidden="true">
                <span v-if="msg.role === 'assistant'">AI</span>
                <span v-else>你</span>
              </div>
              <div class="message-bubble-wrapper">
                <div class="message-meta">
                  <strong>{{ msg.role === 'assistant' ? 'Hermes AI' : '你' }}</strong>
                  <span>{{ msg.time }}</span>
                </div>
                <div class="message-bubble">
                  <div
                    v-if="msg.role === 'assistant'"
                    class="markdown-body"
                    v-html="renderMarkdown(msg.text)"
                  />
                  <p v-else class="message-text">{{ msg.text }}</p>
                </div>
              </div>
            </article>

            <!-- 实时流式响应气泡 -->
            <article v-if="isStreaming" class="message-row message-assistant">
              <div class="message-avatar" aria-hidden="true">AI</div>
              <div class="message-bubble-wrapper">
                <div class="message-meta">
                  <strong>Hermes AI</strong>
                  <span>{{ streamingTime }}</span>
                </div>
                <div class="message-bubble">
                  <div
                    v-if="streamingText"
                    class="markdown-body"
                    v-html="renderMarkdown(streamingText)"
                  />
                  <div v-else class="thinking-indicator">
                    <span class="thinking-dot" />
                    <span>AI 正在思考并组织回答...</span>
                  </div>
                </div>
              </div>
            </article>
          </div>
        </div>

        <!-- 底部输入框 -->
        <footer class="composer-container">
          <form class="composer-form" @submit.prevent="submitMessage">
            <a-textarea
              v-model:value="inputText"
              :auto-size="{ minRows: 2, maxRows: 8 }"
              :disabled="loading"
              class="composer-textarea"
              placeholder="输入任意问题与 AI 自由交流，支持技术答疑、编程辅助或日常闲聊..."
              @keydown="handleKeydown"
            />
            <div class="composer-bottom-bar">
              <span class="shortcut-tip">Enter 换行 · Ctrl / ⌘ + Enter 快速发送</span>
            <div class="composer-buttons">
              <a-button
                v-if="loading"
                danger
                class="stop-btn"
                @click="stopGeneration"
              >
                停止生成 <StopOutlined />
              </a-button>
              <a-button
                v-else
                type="primary"
                html-type="submit"
                :disabled="!inputText.trim()"
                class="send-btn"
              >
                发送 <SendOutlined />
              </a-button>
            </div>
          </div>
        </form>
        </footer>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  ArrowRightOutlined,
  DeleteOutlined,
  HistoryOutlined,
  MessageOutlined,
  PlusOutlined,
  RobotOutlined,
  SendOutlined,
  StopOutlined,
} from '@ant-design/icons-vue'
import { projectApi, streamAiChat } from '@/api'
import { renderMarkdown } from '@/utils/markdown'
import type { ProjectItem } from '@/api'
import { useAiChatStore } from '@/stores/aiChat'

const chatStore = useAiChatStore()

const projects = ref<ProjectItem[]>([])
const projectOptions = ref<Array<{ label: string; value: number }>>([])
const selectedProjectId = ref<number | undefined>(undefined)
const inputText = ref('')
const loading = ref(false)
const historyVisible = ref(true)
const messagesContainer = ref<HTMLDivElement | null>(null)
const abortController = ref<AbortController | null>(null)
const streamingText = ref('')
const isStreaming = ref(false)
const streamingTime = ref('')
const currentMessages = computed(() => chatStore.currentMessages)

// 用户主动停止后，被中止的流式请求会以 AbortError 拒绝；
// 用显式标记区分“用户停止”与“真实网络错误”，避免误报发送失败。
let stoppedByUser = false

function formatSessionTime(iso: string): string {
  try {
    const d = new Date(iso)
    const now = new Date()
    const isToday = d.toDateString() === now.toDateString()
    const timeStr = `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
    if (isToday) return timeStr
    return `${d.getMonth() + 1}/${d.getDate()} ${timeStr}`
  } catch {
    return iso
  }
}

const quickPrompts = [
  {
    icon: '💡',
    title: '接口测试签名算法',
    text: '帮我用 Python 写一个通用的接口测试签名算法',
  },
  {
    icon: '🧪',
    title: '用例设计方法论',
    text: '如何设计高覆盖率、低维护成本的自动化测试用例？',
  },
  {
    icon: '🔍',
    title: '网络报错排障',
    text: '解释一下微服务中常见的 HTTP 502/504 错误与排查步骤',
  },
  {
    icon: '🚀',
    title: '测试框架横向对比',
    text: '对比一下 Pytest、Playwright 与 Cypress 的优劣势和适用场景',
  },
]

async function loadProjects() {
  try {
    const list = await projectApi.list()
    projects.value = list
    projectOptions.value = list.map((p) => ({ label: p.name, value: p.id }))
    if (!selectedProjectId.value && list.length > 0) {
      selectedProjectId.value = list[0].id
    }
  } catch {
    // 忽略项目获取异常
  }
}

function handleProjectChange(val: unknown) {
  selectedProjectId.value = typeof val === 'number' ? val : undefined
  chatStore.setSessionProject(selectedProjectId.value)
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

function handleNewSession() {
  chatStore.createSession('新对话', selectedProjectId.value)
  message.success('已开启新会话')
  scrollToBottom()
}

function sendPrompt(text: string) {
  inputText.value = text
  void submitMessage()
}

function stopGeneration() {
  if (abortController.value) {
    stoppedByUser = true
    abortController.value.abort()
    abortController.value = null
    loading.value = false
    if (streamingText.value) {
      chatStore.appendMessage('assistant', streamingText.value)
    }
    isStreaming.value = false
    streamingText.value = ''
    message.info('已停止生成')
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (e.isComposing) return
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault()
    void submitMessage()
  }
}

async function submitMessage() {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  inputText.value = ''
  chatStore.appendMessage('user', text)
  scrollToBottom()

  loading.value = true
  isStreaming.value = true
  streamingText.value = ''
  const d = new Date()
  streamingTime.value = `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
  abortController.value = new AbortController()

  try {
    const historyPayload = currentMessages.value.slice(-10).map((m) => ({
      role: m.role,
      content: m.text,
    }))

    await streamAiChat(
      {
        query: text,
        project_id: selectedProjectId.value,
        history: historyPayload,
      },
      (token: string) => {
        streamingText.value += token
        scrollToBottom()
      },
      abortController.value.signal
    )

    if (streamingText.value) {
      chatStore.appendMessage('assistant', streamingText.value)
    }
  } catch (err: unknown) {
    const abortedByUser =
      stoppedByUser ||
      abortController.value?.signal.aborted === true ||
      (err instanceof DOMException && err.name === 'AbortError')
    if (abortedByUser) {
      if (streamingText.value) {
        chatStore.appendMessage('assistant', streamingText.value)
      }
      return
    }
    const errMsg = err instanceof Error ? err.message : '与大模型通信异常，请重试'
    const fullErr = streamingText.value
      ? `${streamingText.value}\n\n[回答已中断：${errMsg}]`
      : `发送失败：${errMsg}`
    chatStore.appendMessage('assistant', fullErr)
  } finally {
    loading.value = false
    isStreaming.value = false
    streamingText.value = ''
    abortController.value = null
    stoppedByUser = false
    scrollToBottom()
  }
}

watch(
  () => chatStore.currentSessionId,
  () => {
    scrollToBottom()
  }
)

onMounted(() => {
  chatStore.loadFromStorage()
  void loadProjects()
  scrollToBottom()
})
</script>

<style scoped>
.ai-chat-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 100px);
  max-width: 1360px;
  margin: 0 auto;
  gap: 12px;
}

.chat-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 18px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  background: var(--c-bg-elevated);
  box-shadow: var(--shadow-sm);
  flex-shrink: 0;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.toolbar-identity {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  font-size: 15px;
  color: var(--c-text);
}

.toolbar-icon {
  font-size: 18px;
  color: var(--c-primary);
}

.toolbar-sep {
  color: var(--c-border-strong);
}

.project-select-dropdown {
  min-width: 160px;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  border-radius: var(--radius-full);
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-size: 11px;
  font-weight: 600;
}

.toolbar-btn-active {
  color: var(--c-primary);
  border-color: var(--c-primary);
  background: var(--c-primary-soft);
}

.chat-main {
  display: flex;
  flex: 1;
  min-height: 0;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-lg);
  background: var(--c-bg-elevated);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

/* 历史侧边栏 */
.history-sidebar {
  width: 260px;
  flex-shrink: 0;
  border-right: 1px solid var(--c-border);
  background: var(--c-bg-subtle);
  display: flex;
  flex-direction: column;
}

.history-sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  border-bottom: 1px solid var(--c-border);
  font-size: 12px;
  font-weight: 700;
  color: var(--c-text);
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: var(--radius-md);
  cursor: pointer;
  border: 1px solid transparent;
  color: var(--c-text);
  transition: all 0.15s ease;
}

.history-item:hover {
  background: var(--c-bg-elevated);
  border-color: var(--c-border);
}

.history-item.active {
  background: var(--c-primary-soft);
  border-color: var(--c-primary-glow);
  color: var(--c-primary);
}

.history-item-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.history-item-body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.history-item-title {
  font-size: 12px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-item-time {
  font-size: 10px;
  color: var(--c-text-tertiary);
}

.history-item-del {
  opacity: 0;
  padding: 2px 4px;
  font-size: 12px;
  color: var(--c-text-tertiary);
}

.history-item:hover .history-item-del {
  opacity: 1;
}

.history-item-del:hover {
  color: var(--c-error);
}

/* 核心对话工作区 */
.chat-workspace {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
  height: 100%;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
}

/* 欢迎页空态 */
.welcome-box {
  margin: auto;
  max-width: 680px;
  text-align: center;
  padding: 24px 16px;
}

.welcome-avatar {
  display: inline-grid;
  place-items: center;
  width: 50px;
  height: 50px;
  border-radius: 16px;
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-size: 24px;
  margin-bottom: 14px;
}

.welcome-box h2 {
  margin: 0 0 8px;
  font-size: 20px;
  font-weight: 700;
  color: var(--c-text);
}

.welcome-desc {
  margin: 0 0 24px;
  color: var(--c-text-secondary);
  font-size: 12px;
  line-height: 1.65;
}

.quick-prompts {
  text-align: left;
}

.prompts-title {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: var(--c-text-tertiary);
  margin-bottom: 10px;
}

.prompts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.prompt-chip {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  background: var(--c-bg-subtle);
  color: var(--c-text);
  text-align: left;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.prompt-chip:hover {
  border-color: var(--c-primary);
  background: var(--c-primary-soft);
  transform: translateY(-1px);
}

.prompt-chip-icon {
  font-size: 20px;
  flex-shrink: 0;
}

.prompt-chip-content {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
  gap: 2px;
}

.prompt-chip-content strong {
  font-size: 13px;
  color: var(--c-text);
}

.prompt-chip-content small {
  font-size: 11px;
  color: var(--c-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.prompt-chip-arrow {
  color: var(--c-text-tertiary);
  font-size: 12px;
  flex-shrink: 0;
}

/* 消息流 */
.message-stream {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.message-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.message-user {
  flex-direction: row-reverse;
}

.message-avatar {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
  background: var(--c-primary-soft);
  color: var(--c-primary);
}

.message-user .message-avatar {
  background: var(--c-primary);
  color: #fff;
}

.message-bubble-wrapper {
  max-width: 82%;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.message-user .message-bubble-wrapper {
  align-items: flex-end;
}

.message-meta {
  display: flex;
  gap: 8px;
  align-items: baseline;
  font-size: 11px;
  color: var(--c-text-tertiary);
}

.message-bubble {
  padding: 12px 16px;
  border-radius: var(--radius-lg);
  line-height: 1.65;
  font-size: 13px;
  word-break: break-word;
}

.message-assistant .message-bubble {
  background: var(--c-bg-subtle);
  border: 1px solid var(--c-border);
  color: var(--c-text);
  border-top-left-radius: 4px;
}

.message-user .message-bubble {
  background: var(--c-primary);
  color: #ffffff;
  border-top-right-radius: 4px;
}

.message-text {
  margin: 0;
  white-space: pre-wrap;
}

/* Markdown 富文本 */
.markdown-body {
  font-size: 13px;
  line-height: 1.7;
  color: var(--c-text);
  word-break: break-word;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  margin: 14px 0 8px;
  font-weight: 700;
  color: var(--c-text);
  line-height: 1.35;
}

.markdown-body :deep(h1) { font-size: 17px; }
.markdown-body :deep(h2) { font-size: 15px; border-bottom: 1px solid var(--c-border); padding-bottom: 4px; }
.markdown-body :deep(h3) { font-size: 14px; }
.markdown-body :deep(h4) { font-size: 13px; }

.markdown-body :deep(p) {
  margin: 0 0 10px;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0 0 10px;
  padding-left: 20px;
}

.markdown-body :deep(li) {
  margin-bottom: 4px;
}

.markdown-body :deep(blockquote) {
  margin: 8px 0;
  padding: 8px 14px;
  border-left: 3px solid var(--c-primary);
  background: var(--c-primary-soft);
  color: var(--c-text-secondary);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.markdown-body :deep(pre) {
  margin: 10px 0;
  padding: 12px 14px;
  overflow-x: auto;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  background: var(--c-bg-elevated);
  font-family: 'JetBrains Mono', Consolas, Monaco, monospace;
  font-size: 12px;
  line-height: 1.5;
}

.markdown-body :deep(code) {
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-family: 'JetBrains Mono', Consolas, Monaco, monospace;
  font-size: 12px;
}

.markdown-body :deep(pre code) {
  padding: 0;
  background: transparent;
  color: var(--c-text);
  font-size: 12px;
}

.markdown-body :deep(table) {
  width: 100%;
  margin: 10px 0;
  border-collapse: collapse;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: 6px 10px;
  border: 1px solid var(--c-border);
  font-size: 12px;
}

.markdown-body :deep(th) {
  background: var(--c-bg-subtle);
  font-weight: 600;
}

.markdown-body :deep(hr) {
  margin: 14px 0;
  border: 0;
  border-top: 1px solid var(--c-border);
}

.thinking-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  color: var(--c-text-secondary);
  font-size: 12px;
}

.thinking-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--c-primary);
  animation: pulse 1.2s infinite ease-in-out;
}

@keyframes pulse {
  0%, 100% { opacity: 0.2; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.2); }
}

/* 底部输入框 */
.composer-container {
  padding: 14px 20px;
  border-top: 1px solid var(--c-border);
  background: var(--c-bg-subtle);
  flex-shrink: 0;
}

.composer-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.composer-textarea {
  border-radius: var(--radius-md);
  font-size: 13px;
  line-height: 1.55;
  resize: none;
}

.composer-bottom-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.shortcut-tip {
  font-size: 11px;
  color: var(--c-text-tertiary);
}

.send-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: var(--radius-sm);
}

@media (max-width: 900px) {
  .history-sidebar {
    position: absolute;
    z-index: 10;
    height: 100%;
    box-shadow: var(--shadow-lg);
  }
}

@media (max-width: 768px) {
  .prompts-grid {
    grid-template-columns: 1fr;
  }
  .message-bubble-wrapper {
    max-width: 92%;
  }
}
</style>
