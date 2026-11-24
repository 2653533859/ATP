<template>
  <div class="hermes-shell">
    <!-- 顶部单行极简工具栏 -->
    <header class="hermes-topbar">
      <div class="topbar-left">
        <div class="brand-chip">
          <RobotOutlined class="brand-icon" />
          <span class="brand-title">{{ t('menu.intelligence.hermes') }}</span>
        </div>
        <a-select
          v-model:value="selectedProjectId"
          :options="projectOptions"
          allow-clear
          size="small"
          class="project-picker"
          :placeholder="t('hermes.project_placeholder')"
          @change="handleProjectChange"
        />
        <div v-if="selectedProjectId" class="metric-pills">
          <span class="metric-pill">用例 {{ casesCount }}</span>
          <span class="metric-pill" :class="{ warn: failedTasks.length > 0 }">失败 {{ failedTasks.length }}</span>
          <span class="metric-pill">通过率 {{ passRateText }}</span>
        </div>
      </div>

      <div class="topbar-right">
        <a-button
          size="small"
          :type="historyOpen ? 'primary' : 'default'"
          @click="historyOpen = !historyOpen"
        >
          <HistoryOutlined /> 会话 ({{ chatStore.sessions.length }})
        </a-button>
        <a-button
          v-if="selectedProjectId"
          size="small"
          :type="contextOpen ? 'primary' : 'default'"
          @click="contextOpen = !contextOpen"
        >
          <DashboardOutlined /> 项目面板
        </a-button>
        <a-button type="primary" size="small" @click="handleNewSession">
          <PlusOutlined /> 新对话
        </a-button>
      </div>
    </header>

    <div class="hermes-body">
      <!-- 左侧历史会话（可收起） -->
      <aside v-if="historyOpen" class="history-pane">
        <div class="pane-header">
          <span>历史会话</span>
          <a-button type="text" size="small" @click="handleNewSession"><PlusOutlined /></a-button>
        </div>
        <div class="history-scroll">
          <div
            v-for="session in chatStore.sessions"
            :key="session.id"
            class="history-item"
            :class="{ active: session.id === chatStore.currentSessionId }"
            @click="switchSession(session.id)"
          >
            <MessageOutlined class="history-icon" />
            <span class="history-title">{{ session.title }}</span>
            <DeleteOutlined class="history-del" @click.stop="chatStore.deleteSession(session.id)" />
          </div>
        </div>
      </aside>

      <!-- 中间核心对话区 -->
      <main class="chat-pane">
        <div ref="messagesRef" class="messages-scroll">
          <div v-if="!currentMessages.length && !isStreaming" class="empty-stage">
            <div class="empty-avatar"><RobotOutlined /></div>
            <h2>Hermes 智能助手</h2>
            <div class="quick-grid">
              <button
                v-for="(item, idx) in quickPrompts"
                :key="idx"
                type="button"
                class="quick-chip"
                @click="sendQuickPrompt(item)"
              >
                {{ item }}
              </button>
            </div>
          </div>

          <div v-else class="message-list">
            <div
              v-for="msg in currentMessages"
              :key="msg.id"
              class="msg-row"
              :class="msg.role"
            >
              <div class="msg-avatar">
                <UserOutlined v-if="msg.role === 'user'" />
                <RobotOutlined v-else />
              </div>
              <div class="msg-content">
                <!-- 工具调用胶囊 -->
                <div v-if="msg.toolEvents?.length" class="tool-chips">
                  <span v-for="(evt, i) in msg.toolEvents" :key="i" class="tool-chip">
                    ✓ {{ evt.label }} · {{ evt.summary }}
                  </span>
                </div>

                <!-- 气泡正文 -->
                <div class="msg-bubble">
                  <div v-if="msg.role === 'user'" class="user-text">{{ msg.text }}</div>
                  <div v-else class="markdown-body" v-html="renderMarkdown(msg.text)" />
                </div>

                <!-- 可控项目操作确认卡 -->
                <div v-if="msg.actionProposal" class="action-card">
                  <div class="action-card-head">
                    <a-tag color="blue">{{ actionTypeLabel(msg.actionProposal.action) }}</a-tag>
                    <strong>{{ msg.actionProposal.title }}</strong>
                  </div>
                  <div v-if="msg.actionProposal.summary" class="action-card-summary">
                    {{ msg.actionProposal.summary }}
                  </div>
                  <div class="action-card-footer">
                    <template
                      v-if="!msg.actionProposal.status || msg.actionProposal.status === 'pending' || msg.actionProposal.status === 'failed' || msg.actionProposal.status === 'executing'"
                    >
                      <a-button
                        type="primary"
                        size="small"
                        :loading="msg.actionProposal.status === 'executing'"
                        @click="confirmAction(msg)"
                      >
                        确认执行
                      </a-button>
                      <a-button size="small" :disabled="msg.actionProposal.status === 'executing'" @click="cancelAction(msg)">
                        取消
                      </a-button>
                    </template>
                    <span v-else-if="msg.actionProposal.status === 'cancelled'" class="action-status muted">已取消</span>
                    <div v-else-if="msg.actionProposal.status === 'executed'" class="action-done">
                      <span>✓ {{ msg.actionProposal.resultMessage }}</span>
                      <a-button
                        v-if="msg.actionProposal.resultRoute"
                        type="link"
                        size="small"
                        @click="router.push(msg.actionProposal.resultRoute!)"
                      >
                        查看
                      </a-button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 流式输出中的临时气泡 -->
            <div v-if="isStreaming" class="msg-row assistant">
              <div class="msg-avatar"><RobotOutlined /></div>
              <div class="msg-content">
                <div v-if="streamingToolEvents.length" class="tool-chips">
                  <span v-for="(evt, i) in streamingToolEvents" :key="i" class="tool-chip">
                    ✓ {{ evt.label }} · {{ evt.summary }}
                  </span>
                </div>
                <div class="msg-bubble">
                  <div v-if="streamingText" class="markdown-body" v-html="renderMarkdown(streamingText)" />
                  <span v-else class="typing-dots"><span /><span /><span /></span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 底部输入框 -->
        <div class="composer-wrap">
          <div class="composer-box">
            <textarea
              v-model="inputText"
              rows="2"
              class="composer-input"
              :placeholder="selectedProjectId ? '询问当前项目数据、排查失败或让 Hermes 执行操作... (Enter 发送)' : '输入任意测试或技术问题... (Enter 发送)'"
              @keydown.enter.exact.prevent="handleSend"
            />
            <div class="composer-actions">
              <a-button v-if="isStreaming" danger size="small" @click="stopStreaming">停止</a-button>
              <a-button
                v-else
                type="primary"
                size="small"
                :disabled="!inputText.trim()"
                @click="handleSend"
              >
                <SendOutlined /> 发送
              </a-button>
            </div>
          </div>
        </div>
      </main>

      <!-- 右侧精简项目面板（仅选中项目且展开时显示） -->
      <aside v-if="selectedProjectId && contextOpen" class="context-pane">
        <div class="pane-header">
          <span>项目快照</span>
          <a-button type="text" size="small" :loading="contextLoading" @click="loadProjectSnapshot">
            <ReloadOutlined />
          </a-button>
        </div>

        <div class="stat-grid">
          <div class="stat-cell">
            <span class="stat-label">通过率</span>
            <strong>{{ passRateText }}</strong>
          </div>
          <div class="stat-cell">
            <span class="stat-label">总运行</span>
            <strong>{{ totalRuns }}</strong>
          </div>
          <div class="stat-cell">
            <span class="stat-label">用例数</span>
            <strong>{{ casesCount }}</strong>
          </div>
          <div class="stat-cell">
            <span class="stat-label">待处理缺陷</span>
            <strong>{{ openDefectsCount }}</strong>
          </div>
        </div>

        <div class="failure-section">
          <div class="section-title">最近失败任务</div>
          <a-empty v-if="!failedTasks.length" description="暂无失败任务" :image="false" style="margin: 16px 0" />
          <div v-else class="failure-list">
            <button
              v-for="task in failedTasks"
              :key="`${task.task_type}-${task.run_id}`"
              type="button"
              class="failure-item"
              @click="analyzeFailureTask(task)"
            >
              <span class="failure-name">{{ task.name }}</span>
              <span class="failure-meta">#{{ task.run_id }} · {{ task.status }}</span>
            </button>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import {
  DashboardOutlined,
  DeleteOutlined,
  HistoryOutlined,
  MessageOutlined,
  PlusOutlined,
  ReloadOutlined,
  RobotOutlined,
  SendOutlined,
  UserOutlined,
} from '@ant-design/icons-vue'
import {
  caseApi,
  defectApi,
  projectApi,
  reportApi,
  workbenchApi,
  type ProjectItem,
  type WorkbenchTaskItem,
} from '@/api'
import {
  executeAiChatAction,
  streamAiChat,
  type AiChatActionProposal,
  type AiChatToolEvent,
  type ChatActionType,
} from '@/api/aiChat'
import { useAiChatStore, type ChatMessage } from '@/stores/aiChat'
import { projectIdFromQuery } from '@/utils/projectContext'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const chatStore = useAiChatStore()

const projects = ref<ProjectItem[]>([])
const selectedProjectId = ref<number | undefined>(projectIdFromQuery(route.query.project_id))
const historyOpen = ref(false)
const contextOpen = ref(true)
const inputText = ref('')
const isStreaming = ref(false)
const streamingText = ref('')
const streamingToolEvents = ref<AiChatToolEvent[]>([])
const messagesRef = ref<HTMLElement | null>(null)
let abortController: AbortController | null = null

const contextLoading = ref(false)
const casesCount = ref(0)
const totalRuns = ref(0)
const passRate = ref(0)
const openDefectsCount = ref(0)
const failedTasks = ref<WorkbenchTaskItem[]>([])

const currentMessages = computed(() => chatStore.currentMessages)
const projectOptions = computed(() => projects.value.map((p) => ({ label: p.name, value: p.id })))
const passRateText = computed(() => (totalRuns.value > 0 ? `${passRate.value.toFixed(1)}%` : '--'))

const quickPrompts = computed(() =>
  selectedProjectId.value
    ? [
        '查看当前项目概览和用例分布',
        '分析最近失败的测试任务及可能原因',
        '帮我创建一条 Web 登录测试用例',
        '针对当前项目给出测试质量改进建议',
      ]
    : [
        '如何设计稳定的 Web UI 自动化断言？',
        'Pytest 接口自动化如何管理动态 Token？',
        'Playwright 元素定位易失效怎么治理？',
        '帮我写一个幂等接口测试思路',
      ],
)

function renderMarkdown(text: string): string {
  const html = marked.parse(text || '', { async: false }) as string
  return DOMPurify.sanitize(html)
}

function actionTypeLabel(action: ChatActionType): string {
  const map: Record<ChatActionType, string> = {
    run_case: '执行用例',
    run_suite: '执行套件',
    create_case: '创建用例',
    update_case: '更新用例',
    create_defect: '提交缺陷',
    update_defect: '更新缺陷',
    create_knowledge: '沉淀知识',
  }
  return map[action] || action
}

function scrollToBottom() {
  void nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

async function loadProjects() {
  try {
    projects.value = await projectApi.list()
    if (!selectedProjectId.value && chatStore.currentSession?.projectId) {
      selectedProjectId.value = chatStore.currentSession.projectId
    } else if (!selectedProjectId.value && projects.value.length === 1) {
      selectedProjectId.value = projects.value[0].id
    }
  } catch {
    projects.value = []
  }
}

async function loadProjectSnapshot() {
  const pid = selectedProjectId.value
  if (!pid) return
  contextLoading.value = true
  try {
    const [caseList, overview, defects, tasks] = await Promise.all([
      caseApi.list({ project_id: pid }).catch(() => []),
      reportApi.overview({ project_id: pid, days: 30 }).catch(() => null),
      defectApi.list({ project_id: pid, status: 'open', page_size: 1 }).catch(() => null),
      workbenchApi.tasks({ project_id: pid, status: 'failed', limit: 6 }).catch(() => null),
    ])
    if (selectedProjectId.value !== pid) return
    casesCount.value = caseList.length
    totalRuns.value = overview?.total_runs ?? 0
    passRate.value = overview?.pass_rate ?? 0
    openDefectsCount.value = defects?.total ?? 0
    failedTasks.value = tasks?.items ?? []
  } finally {
    if (selectedProjectId.value === pid) {
      contextLoading.value = false
    }
  }
}

function handleProjectChange(val: unknown) {
  const nextId = typeof val === 'number' && Number.isFinite(val) ? val : undefined
  selectedProjectId.value = nextId
  chatStore.setSessionProject(nextId)
  if (nextId) {
    void loadProjectSnapshot()
  } else {
    casesCount.value = 0
    totalRuns.value = 0
    passRate.value = 0
    openDefectsCount.value = 0
    failedTasks.value = []
  }
}

function switchSession(id: string) {
  if (isStreaming.value) return
  chatStore.switchSession(id)
  const sessionProj = chatStore.currentSession?.projectId
  if (sessionProj && sessionProj !== selectedProjectId.value) {
    handleProjectChange(sessionProj)
  }
  scrollToBottom()
}

function handleNewSession() {
  if (isStreaming.value) stopStreaming()
  chatStore.createSession('新对话', selectedProjectId.value)
}

function sendQuickPrompt(prompt: string) {
  inputText.value = prompt
  void handleSend()
}

function analyzeFailureTask(task: WorkbenchTaskItem) {
  inputText.value = `请帮我分析运行 #${task.run_id}（${task.name}）的失败原因，并给出排查建议。`
  void handleSend()
}

function stopStreaming() {
  if (abortController) {
    abortController.abort()
    abortController = null
  }
}

async function handleSend() {
  const query = inputText.value.trim()
  if (!query || isStreaming.value) return

  const history = currentMessages.value.slice(-10).map((m) => ({
    role: m.role,
    content: m.text,
  }))
  chatStore.appendMessage('user', query)
  inputText.value = ''
  scrollToBottom()

  isStreaming.value = true
  streamingText.value = ''
  streamingToolEvents.value = []
  abortController = new AbortController()
  let pendingProposal: AiChatActionProposal | undefined

  try {
    const finalText = await streamAiChat(
      {
        query,
        project_id: selectedProjectId.value,
        history,
      },
      (token) => {
        streamingText.value += token
        scrollToBottom()
      },
      abortController.signal,
      {
        onToolEvent: (evt) => {
          streamingToolEvents.value.push(evt)
        },
        onActionProposal: (proposal) => {
          pendingProposal = { ...proposal, status: 'pending' }
        },
      },
    )

    const msg = chatStore.appendMessage('assistant', finalText || streamingText.value || '（无输出）')
    if (streamingToolEvents.value.length) {
      msg.toolEvents = [...streamingToolEvents.value]
    }
    if (pendingProposal) {
      msg.actionProposal = pendingProposal
    }
    chatStore.saveToStorage()
  } catch (err: unknown) {
    const isAbort = err instanceof Error && err.name === 'AbortError'
    if (isAbort && streamingText.value) {
      const msg = chatStore.appendMessage('assistant', `${streamingText.value}\n\n*(已中断)*`)
      if (streamingToolEvents.value.length) msg.toolEvents = [...streamingToolEvents.value]
      chatStore.saveToStorage()
    } else if (!isAbort) {
      const errMsg = err instanceof Error ? err.message : '请求失败'
      message.error(errMsg)
      chatStore.appendMessage('assistant', `请求失败：${errMsg}`)
    }
  } finally {
    isStreaming.value = false
    streamingText.value = ''
    streamingToolEvents.value = []
    abortController = null
    scrollToBottom()
  }
}

async function confirmAction(msg: ChatMessage) {
  if (!msg.actionProposal || !selectedProjectId.value) return
  msg.actionProposal.status = 'executing'
  chatStore.saveToStorage()
  try {
    const res = await executeAiChatAction({
      project_id: selectedProjectId.value,
      action: msg.actionProposal.action,
      params: msg.actionProposal.params,
    })
    msg.actionProposal.status = 'executed'
    msg.actionProposal.resultMessage = res.message
    msg.actionProposal.resultRoute = res.route ?? undefined
    chatStore.saveToStorage()
    message.success(res.message)
    void loadProjectSnapshot()
  } catch (err: unknown) {
    msg.actionProposal.status = 'failed'
    chatStore.saveToStorage()
    const detail = (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail
      || (err instanceof Error ? err.message : '执行失败')
    message.error(detail)
  }
}

function cancelAction(msg: ChatMessage) {
  if (!msg.actionProposal) return
  msg.actionProposal.status = 'cancelled'
  chatStore.saveToStorage()
}

watch(
  () => route.query.project_id,
  (next) => {
    const normalized = projectIdFromQuery(next)
    if (normalized && normalized !== selectedProjectId.value) {
      selectedProjectId.value = normalized
      void loadProjectSnapshot()
    }
  },
)

onMounted(async () => {
  chatStore.loadFromStorage()
  await loadProjects()
  if (selectedProjectId.value) {
    void loadProjectSnapshot()
  }
  scrollToBottom()
})

onBeforeUnmount(() => {
  stopStreaming()
})
</script>

<style scoped>
.hermes-shell {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 88px);
  min-height: 540px;
  background: var(--c-bg-body);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.hermes-topbar {
  height: 48px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px;
  border-bottom: 1px solid var(--c-border);
  background: var(--c-bg-elevated);
  gap: 12px;
}

.topbar-left,
.topbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.brand-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  color: var(--c-text);
}

.brand-icon {
  color: var(--c-primary);
  font-size: 16px;
}

.project-picker {
  width: 190px;
}

.metric-pills {
  display: flex;
  align-items: center;
  gap: 6px;
}

.metric-pill {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--c-bg-subtle);
  color: var(--c-text-secondary);
}

.metric-pill.warn {
  color: #d4380d;
  background: rgba(255, 77, 79, 0.1);
}

.hermes-body {
  flex: 1;
  min-height: 0;
  display: flex;
}

.history-pane,
.context-pane {
  width: 248px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--c-bg-elevated);
  min-height: 0;
}

.history-pane {
  border-right: 1px solid var(--c-border);
}

.context-pane {
  width: 268px;
  border-left: 1px solid var(--c-border);
  padding: 12px;
  gap: 14px;
  overflow-y: auto;
}

.pane-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text);
  border-bottom: 1px solid var(--c-border-subtle);
}

.context-pane .pane-header {
  padding: 0 0 8px;
}

.history-scroll {
  flex: 1;
  min-height: 0;
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
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--c-text-secondary);
  font-size: 13px;
}

.history-item:hover {
  background: var(--c-bg-subtle);
  color: var(--c-text);
}

.history-item.active {
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-weight: 500;
}

.history-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-del {
  opacity: 0;
  font-size: 12px;
}

.history-item:hover .history-del {
  opacity: 0.7;
}

.chat-pane {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.messages-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px 24px;
}

.empty-stage {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.empty-avatar {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: var(--c-primary-soft);
  color: var(--c-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}

.empty-stage h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--c-text);
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 260px));
  gap: 10px;
}

.quick-chip {
  padding: 10px 14px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  background: var(--c-bg-elevated);
  color: var(--c-text);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}

.quick-chip:hover {
  border-color: var(--c-primary);
  background: var(--c-primary-soft);
}

.message-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 860px;
  margin: 0 auto;
}

.msg-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.msg-row.user {
  flex-direction: row-reverse;
}

.msg-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--c-bg-subtle);
  color: var(--c-text-secondary);
}

.msg-row.assistant .msg-avatar {
  background: var(--c-primary-soft);
  color: var(--c-primary);
}

.msg-content {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-width: 82%;
}

.msg-row.user .msg-content {
  align-items: flex-end;
}

.tool-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tool-chip {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--c-bg-subtle);
  color: var(--c-text-secondary);
}

.msg-bubble {
  padding: 10px 14px;
  border-radius: 12px;
  background: var(--c-bg-elevated);
  border: 1px solid var(--c-border);
  color: var(--c-text);
  font-size: 14px;
  line-height: 1.6;
}

.msg-row.user .msg-bubble {
  background: var(--c-primary);
  border-color: var(--c-primary);
  color: #fff;
}

.user-text {
  white-space: pre-wrap;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(pre) {
  padding: 10px;
  border-radius: 6px;
  background: var(--c-bg-subtle);
  overflow-x: auto;
}

.action-card {
  padding: 10px 12px;
  border: 1px solid var(--c-primary);
  border-radius: 10px;
  background: var(--c-bg-elevated);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.action-card-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.action-card-summary {
  font-size: 13px;
  color: var(--c-text-secondary);
}

.action-card-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 2px;
}

.action-done {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #16a34a;
}

.action-status.muted {
  color: var(--c-text-secondary);
  font-size: 12px;
}

.typing-dots {
  display: inline-flex;
  gap: 4px;
  padding: 4px 2px;
}

.typing-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--c-text-secondary);
  animation: dotPulse 1s infinite ease-in-out;
}

.typing-dots span:nth-child(2) {
  animation-delay: 0.15s;
}

.typing-dots span:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes dotPulse {
  0%, 80%, 100% {
    opacity: 0.3;
    transform: scale(0.85);
  }
  40% {
    opacity: 1;
    transform: scale(1);
  }
}

.composer-wrap {
  padding: 12px 24px 16px;
  flex-shrink: 0;
}

.composer-box {
  max-width: 860px;
  margin: 0 auto;
  border: 1px solid var(--c-border);
  border-radius: 12px;
  background: var(--c-bg-elevated);
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.composer-input {
  width: 100%;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  color: var(--c-text);
  font-size: 14px;
  line-height: 1.5;
}

.composer-actions {
  display: flex;
  justify-content: flex-end;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.stat-cell {
  padding: 10px;
  border-radius: 8px;
  background: var(--c-bg-body);
  border: 1px solid var(--c-border-subtle);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stat-label {
  font-size: 12px;
  color: var(--c-text-secondary);
}

.stat-cell strong {
  font-size: 16px;
  color: var(--c-text);
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text);
  margin-bottom: 8px;
}

.failure-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.failure-item {
  width: 100%;
  text-align: left;
  padding: 8px 10px;
  border: 1px solid var(--c-border-subtle);
  border-radius: 8px;
  background: var(--c-bg-body);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.failure-item:hover {
  border-color: var(--c-primary);
}

.failure-name {
  font-size: 13px;
  color: var(--c-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.failure-meta {
  font-size: 12px;
  color: var(--c-text-secondary);
}
</style>
