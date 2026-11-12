<template>
  <section class="agent-panel panel" data-testid="android-agent-panel">
    <div class="panel-head compact-head">
      <div>
        <div class="panel-kicker">{{ t('android_agent.kicker') }}</div>
        <h2>{{ t('android_agent.title') }}</h2>
      </div>
      <div class="agent-head-actions">
        <a-select
          v-if="sessions.length"
          :value="sessionId ?? undefined"
          :placeholder="t('android_agent.session_select_placeholder')"
          size="small"
          class="session-select"
          allow-clear
          @change="handleSessionSelect"
        >
          <a-select-option v-for="s in sessions" :key="s.id" :value="s.id">
            {{ s.title }} (#{{ s.id }})
          </a-select-option>
        </a-select>
        <a-button size="small" :loading="loading" @click="refreshAll">
          <ReloadOutlined /> {{ t('android_agent.refresh') }}
        </a-button>
      </div>
    </div>
    <p class="agent-description">{{ t('android_agent.description') }}</p>

    <a-alert
      v-if="errorMessage"
      class="agent-alert"
      type="error"
      show-icon
      :message="errorMessage"
      closable
      @close="errorMessage = ''"
    />

    <div v-if="!sessions.length && !session && !loading" class="agent-empty">
      <span>{{ t('android_agent.empty_session') }}</span>
    </div>

    <div class="agent-form">
      <div class="agent-form-grid">
        <div class="form-group">
          <label>{{ t('android_agent.device_label') }}</label>
          <a-select
            v-model:value="formDeviceId"
            :options="deviceOptions"
            :placeholder="t('app_workbench.device_placeholder')"
            size="small"
          />
        </div>
        <div class="form-group">
          <label>{{ t('android_agent.package_label') }}</label>
          <div class="agent-package-row">
            <a-auto-complete
              v-model:value="formPackage"
              :options="packageOptions"
              :placeholder="t('android_agent.package_placeholder')"
              size="small"
              class="agent-package-input"
            />
            <a-button size="small" :loading="packagesLoading" :disabled="formDeviceId === undefined" @click="loadDevicePackages">
              {{ t('android_agent.load_packages') }}
            </a-button>
          </div>
          <span v-if="packageHint" class="form-hint">{{ packageHint }}</span>
        </div>
        <div class="form-group">
          <label>{{ t('android_agent.budget_label') }}</label>
          <div class="agent-budget-row">
            <a-input-number v-model:value="formMaxSteps" :min="1" :max="100" size="small" />
            <a-input-number v-model:value="formMaxCalls" :min="1" :max="120" size="small" />
          </div>
        </div>
      </div>
      <div class="form-group">
        <label>{{ t('android_agent.goal_label') }}</label>
        <a-input v-model:value="formGoal" :placeholder="t('android_agent.goal_placeholder')" size="small" />
      </div>
      <div class="form-group">
        <label>{{ t('android_agent.outcome_label') }}</label>
        <a-input v-model:value="formOutcome" :placeholder="t('android_agent.outcome_placeholder')" size="small" />
      </div>
      <div class="agent-form-actions">
        <a-button
          type="primary"
          size="small"
          :disabled="!canCreate"
          :loading="creating"
          @click="createSession"
        >
          {{ t('android_agent.create') }}
        </a-button>
      </div>
    </div>

    <div v-if="sessionId" class="agent-session">
      <div class="agent-session-head">
        <div class="agent-session-meta">
          <a-tag :color="statusColor(session?.status)">{{ session?.status || '-' }}</a-tag>
          <span class="agent-controller">{{ t('android_agent.controller_label') }}: {{ session?.controller || '-' }}</span>
          <span class="agent-usage tabular-nums">{{ usageLabel }}</span>
        </div>
        <div class="agent-controls">
          <a-button size="small" :disabled="!canStart" :loading="acting" @click="startSession">
            {{ t('android_agent.start') }}
          </a-button>
          <a-button
            size="small"
            :disabled="!canRunLoop"
            :loading="running"
            @click="runLoop"
          >
            {{ t('android_agent.run_loop') }}
          </a-button>
          <a-button size="small" :disabled="!canPause" :loading="acting" @click="control('pause')">
            {{ t('android_agent.pause') }}
          </a-button>
          <a-button size="small" :disabled="!canPause" :loading="acting" @click="control('takeover')">
            {{ t('android_agent.takeover') }}
          </a-button>
          <a-button size="small" :disabled="!canResume" :loading="acting" @click="control('resume')">
            {{ t('android_agent.resume') }}
          </a-button>
          <a-button size="small" danger :disabled="!canCancel" :loading="acting" @click="control('cancel')">
            {{ t('android_agent.cancel') }}
          </a-button>
        </div>
      </div>
      <p class="agent-hint">{{ t('android_agent.control_hint') }}</p>

      <div class="agent-events">
        <div class="agent-events-head">
          <strong>{{ t('android_agent.events_title') }}</strong>
          <span class="agent-events-note">{{ t('android_agent.events_order') }}</span>
        </div>
        <p v-if="!events.length" class="agent-events-empty">{{ t('android_agent.events_empty') }}</p>
        <ul v-else class="agent-event-list">
          <li v-for="event in events" :key="event.seq" class="agent-event-row" :data-seq="event.seq">
            <span class="agent-event-seq">#{{ event.seq }}</span>
            <span class="agent-event-type">{{ event.event_type }}</span>
            <span class="agent-event-time tabular-nums">{{ formatTime(event.created_at) }}</span>
          </li>
        </ul>
      </div>

      <div class="agent-draft">
        <div class="agent-draft-head">
          <strong>{{ draft ? t('android_agent.draft_title', { version: draft.version }) : t('android_agent.compile_draft') }}</strong>
          <a-button size="small" :disabled="!canCompile" :loading="compiling" @click="compileDraft">
            {{ t('android_agent.compile_draft') }}
          </a-button>
        </div>
        <template v-if="draft">
          <div class="agent-draft-status">
            <a-tag :color="draft.status === 'blocked' ? 'red' : 'green'">{{ draftStatusLabel }}</a-tag>
            <span class="agent-draft-hash tabular-nums">{{ draft.content_hash.slice(0, 12) }}</span>
          </div>
          <div v-if="draft.blocking_issues.length" class="agent-blocking">
            <span>{{ t('android_agent.blocking_issues') }}</span>
            <ul>
              <li v-for="issue in draft.blocking_issues" :key="issue.code">{{ issue.code }} - {{ issue.message }}</li>
            </ul>
          </div>
          <div class="agent-steps">
            <span>{{ t('android_agent.steps_preview') }}</span>
            <ol>
              <li v-for="(step, index) in draft.steps" :key="index">
                {{ step.action }} {{ stepResource(step) }}
              </li>
            </ol>
          </div>
          <div class="agent-replay">
            <a-checkbox v-model:checked="replayStateConfirmed">
              {{ t('android_agent.replay_confirm_state') }}
            </a-checkbox>
            <div class="agent-replay-row">
              <span>{{ t('android_agent.replay_module') }}</span>
              <a-select v-model:value="replayModuleId" :options="moduleOptions" size="small" />
              <a-button size="small" :disabled="!previewReady" @click="openReplayPreview">
                {{ t('android_agent.replay_preview') }}
              </a-button>
              <a-button
                size="small"
                type="primary"
                :disabled="!canStartReplay"
                :loading="replaying"
                @click="startReplay"
              >
                {{ t('android_agent.replay_start') }}
              </a-button>
              <a-button size="small" :disabled="!canPublish" :loading="publishing" @click="publishDraft">
                {{ t('android_agent.publish') }}
              </a-button>
            </div>
            <p v-if="previewItems.length" class="agent-preview-items">
              <span v-for="item in previewItems" :key="item.code" :class="['agent-preview-item', item.status]">
                {{ item.code }}: {{ item.message }}
              </span>
            </p>
            <p v-if="publishedCaseId" class="agent-published tabular-nums">
              {{ t('android_agent.published_case', { id: publishedCaseId }) }}
            </p>
          </div>
        </template>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { ReloadOutlined } from '@ant-design/icons-vue'

import { androidAgentApi, deviceApi, type AgentDraftItem, type AgentEventItem, type AgentSessionItem } from '@/api'

const props = defineProps<{
  projectId: number | null
  devices: Array<{ id: number; serial?: string; name?: string | null; status?: string }>
  modules: Array<{ id: number; name: string }>
  canModify: boolean
}>()

const { t } = useI18n()

const sessions = ref<AgentSessionItem[]>([])
const session = ref<AgentSessionItem | null>(null)
const events = ref<AgentEventItem[]>([])
const draft = ref<AgentDraftItem | null>(null)
const previewItems = ref<Array<{ code: string; status: string; message: string }>>([])
const publishedCaseId = ref<number | null>(null)

const loading = ref(false)
const creating = ref(false)
const acting = ref(false)
const running = ref(false)
const compiling = ref(false)
const replaying = ref(false)
const publishing = ref(false)
const errorMessage = ref('')

const formDeviceId = ref<number | undefined>(undefined)
const formPackage = ref('')
const devicePackages = ref<string[]>([])
const packagesLoading = ref(false)
const foregroundPackage = ref<string | null>(null)
const formGoal = ref('')
const formOutcome = ref('')
const formMaxSteps = ref(30)
const formMaxCalls = ref(40)

const replayStateConfirmed = ref(false)
const replayModuleId = ref<number | undefined>(undefined)

const sessionId = computed(() => session.value?.id ?? null)
const deviceOptions = computed(() =>
  props.devices.map((device) => ({
    value: device.id,
    label: device.name || device.serial || '#' + device.id,
  })),
)
const moduleOptions = computed(() => props.modules.map((module) => ({ value: module.id, label: module.name })))
const packageOptions = computed(() =>
  devicePackages.value.map((pkg) => ({
    value: pkg,
    label: pkg === foregroundPackage.value
      ? `${pkg} · ${t('android_agent.foreground_tag')}`
      : pkg,
  })),
)
const packageHint = computed(() => {
  if (foregroundPackage.value) {
    return t('android_agent.foreground_hint', { package: foregroundPackage.value })
  }
  if (devicePackages.value.length) {
    return t('android_agent.packages_loaded', { count: devicePackages.value.length })
  }
  return ''
})

const statusValue = computed(() => session.value?.status ?? '')
const canCreate = computed(
  () => props.canModify && Boolean(props.projectId) && formDeviceId.value !== undefined && formPackage.value.trim() !== '' &&
    formGoal.value.trim() !== '' && formOutcome.value.trim() !== '',
)
const canStart = computed(() => props.canModify && statusValue.value === 'created')
const canPause = computed(() => props.canModify && ['running', 'prechecking'].includes(statusValue.value))
const canRunLoop = computed(() => props.canModify && statusValue.value === 'running')
const canResume = computed(() => props.canModify && statusValue.value === 'paused')
const canCancel = computed(
  () => props.canModify && !['completed', 'failed', 'cancelled'].includes(statusValue.value),
)
const canCompile = computed(
  () => props.canModify && ['completed', 'failed', 'cancelled'].includes(statusValue.value),
)
const draftStatusLabel = computed(() => {
  const value = draft.value?.status
  if (value === 'blocked') return t('android_agent.draft_blocked')
  if (value === 'pending_replay') return t('android_agent.draft_pending')
  if (value === 'verified') return t('android_agent.draft_verified')
  return t('android_agent.draft_replayable')
})
const previewReady = computed(() => Boolean(draft.value) && draft.value?.status !== 'blocked')
const canStartReplay = computed(
  () =>
    props.canModify &&
    Boolean(draft.value) &&
    draft.value?.status !== 'blocked' &&
    replayStateConfirmed.value &&
    replayModuleId.value !== undefined,
)
const canPublish = computed(() => props.canModify && Boolean(draft.value) && draft.value?.status !== 'blocked')
const usageLabel = computed(() => {
  const item = session.value
  if (!item) return ''
  return [
    t('android_agent.steps_used', { used: item.steps_count, total: item.budget_max_steps }),
    t('android_agent.calls_used', { used: item.model_calls_count, total: item.budget_max_calls }),
    t('android_agent.tokens_used', { used: item.total_tokens }),
  ].join(' · ')
})

let pollTimer: ReturnType<typeof setInterval> | null = null

function statusColor(status?: string) {
  if (status === 'running') return 'green'
  if (status === 'paused' || status === 'pause_requested') return 'orange'
  if (status === 'failed' || status === 'cancelled') return 'red'
  if (status === 'completed') return 'blue'
  return 'default'
}

function formatTime(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleTimeString()
}

function stepResource(step: Record<string, unknown>) {
  const resourceId = step?.resource_id
  if (typeof resourceId === 'string' && resourceId) return resourceId
  const params = step?.params
  if (params && typeof params === 'object') {
    const value = (params as Record<string, unknown>).resource_id
    if (typeof value === 'string') return value
  }
  return ''
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(() => {
    // 循环执行期间后端阻塞处理，轮询只会拿到中间态，等它收敛后再拉
    if (running.value) return
    void refreshSession()
  }, 3000)
}

async function refreshEvents() {
  if (!props.projectId || !sessionId.value) return
  const page = await androidAgentApi.events(props.projectId, sessionId.value, 0, 200)
  events.value = page.items
}

async function loadDevicePackages() {
  const deviceId = formDeviceId.value
  if (deviceId === undefined) {
    devicePackages.value = []
    foregroundPackage.value = null
    return
  }
  packagesLoading.value = true
  try {
    const result = await deviceApi.packages(deviceId)
    devicePackages.value = result.packages
    foregroundPackage.value = result.current_package
    if (!formPackage.value.trim() && result.current_package) {
      formPackage.value = result.current_package
    }
  } catch {
    devicePackages.value = []
    foregroundPackage.value = null
    message.warning(t('android_agent.packages_failed'))
  } finally {
    packagesLoading.value = false
  }
}

watch(
  () => formDeviceId.value,
  () => {
    devicePackages.value = []
    foregroundPackage.value = null
    void loadDevicePackages()
  },
)

async function refreshSession() {
  if (!props.projectId || !sessionId.value) return
  session.value = await androidAgentApi.getSession(props.projectId, sessionId.value)
  await refreshEvents()
}

async function refreshSessionsList() {
  if (!props.projectId) {
    sessions.value = []
    return
  }
  try {
    sessions.value = await androidAgentApi.listSessions(props.projectId)
  } catch {
    // 忽略加载历史列表异常
  }
}

async function handleSessionSelect(val: unknown) {
  const sid = typeof val === 'number' ? val : Number(val)
  if (!sid || isNaN(sid)) {
    session.value = null
    events.value = []
    draft.value = null
    previewItems.value = []
    publishedCaseId.value = null
    return
  }
  if (!props.projectId) return
  loading.value = true
  errorMessage.value = ''
  try {
    session.value = await androidAgentApi.getSession(props.projectId, sid)
    await refreshEvents()
    startPolling()
  } catch (error) {
    errorMessage.value = describeError(error)
  } finally {
    loading.value = false
  }
}

async function refreshAll() {
  if (!props.projectId) return
  loading.value = true
  errorMessage.value = ''
  try {
    await refreshSessionsList()
    if (sessionId.value) await refreshSession()
  } catch {
    errorMessage.value = t('android_agent.error_generic')
  } finally {
    loading.value = false
  }
}

async function createSession() {
  const deviceId = formDeviceId.value
  if (!props.projectId || deviceId === undefined) return
  creating.value = true
  errorMessage.value = ''
  try {
    const created = await androidAgentApi.createSession(
      props.projectId,
      {
        device_id: deviceId,
        package_name: formPackage.value.trim(),
        goal: formGoal.value.trim(),
        expected_outcome: formOutcome.value.trim(),
        budget: { max_steps: formMaxSteps.value, max_calls: formMaxCalls.value },
      },
      'agent-session-' + Date.now(),
    )
    session.value = created
    sessions.value = [created, ...sessions.value]
    draft.value = null
    previewItems.value = []
    publishedCaseId.value = null
    await refreshEvents()
    startPolling()
  } catch (error) {
    errorMessage.value = describeError(error)
  } finally {
    creating.value = false
  }
}

async function startSession() {
  if (!props.projectId || !sessionId.value) return
  acting.value = true
  try {
    session.value = await androidAgentApi.startSession(props.projectId, sessionId.value)
    await refreshEvents()
  } catch (error) {
    errorMessage.value = describeError(error)
  } finally {
    acting.value = false
  }
}

async function runLoop() {
  if (!props.projectId || !sessionId.value) return
  running.value = true
  errorMessage.value = ''
  message.info(t('android_agent.run_started'))
  try {
    // 阻塞调用：后端一直跑到收敛（暂停/失败/预算耗尽）才返回，结果只给稳定状态与用量
    const result = await androidAgentApi.runSession(props.projectId, sessionId.value)
    message.info(t('android_agent.run_finished', { status: result.status, reason: result.reason }))
    await refreshSession()
  } catch (error) {
    errorMessage.value = describeError(error)
  } finally {
    running.value = false
  }
}

async function control(action: 'pause' | 'takeover' | 'resume' | 'cancel') {
  if (!props.projectId || !session.value) return
  acting.value = true
  try {
    const result = await androidAgentApi.control(props.projectId, session.value.id, action, session.value.version)
    session.value = { ...session.value, status: result.status, controller: result.controller, control_epoch: result.control_epoch, version: result.version }
    await refreshEvents()
  } catch (error) {
    errorMessage.value = describeError(error)
  } finally {
    acting.value = false
  }
}

async function compileDraft() {
  if (!props.projectId || !sessionId.value) return
  compiling.value = true
  try {
    draft.value = await androidAgentApi.compileDraft(props.projectId, sessionId.value)
    previewItems.value = []
    publishedCaseId.value = draft.value.published_case_id ?? null
    if (!replayModuleId.value && moduleOptions.value.length) replayModuleId.value = moduleOptions.value[0].value
    await refreshEvents()
  } catch (error) {
    errorMessage.value = describeError(error)
  } finally {
    compiling.value = false
  }
}

async function openReplayPreview() {
  if (!props.projectId || !draft.value) return
  try {
    const preview = await androidAgentApi.replayPreview(props.projectId, draft.value.id)
    previewItems.value = preview.items
  } catch (error) {
    errorMessage.value = describeError(error)
  }
}

async function startReplay() {
  const moduleId = replayModuleId.value
  if (!props.projectId || !draft.value || moduleId === undefined) return
  replaying.value = true
  try {
    const handoff = await androidAgentApi.startReplay(props.projectId, draft.value.id, {
      initial_state_confirmed: replayStateConfirmed.value,
      module_id: moduleId,
      idempotency_key: 'agent-replay-' + draft.value.id + '-' + draft.value.version,
    })
    message.success(t('android_agent.replay_start') + ' #' + handoff.replay.id)
  } catch (error) {
    errorMessage.value = describeError(error)
  } finally {
    replaying.value = false
  }
}

async function publishDraft() {
  if (!props.projectId || !draft.value) return
  publishing.value = true
  try {
    const result = await androidAgentApi.publishDraft(
      props.projectId,
      draft.value.id,
      'agent-publish-' + draft.value.id + '-' + draft.value.version,
    )
    publishedCaseId.value = result.case_id
  } catch (error) {
    errorMessage.value = describeError(error)
  } finally {
    publishing.value = false
  }
}

function describeError(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string') {
    if (detail.includes('device_busy')) return t('android_agent.error_device_busy')
    return detail
  }
  return t('android_agent.error_generic')
}

watch(
  () => props.projectId,
  () => {
    stopPolling()
    sessions.value = []
    session.value = null
    events.value = []
    draft.value = null
    previewItems.value = []
    publishedCaseId.value = null
    void refreshSessionsList()
  },
)

onMounted(() => {
  void refreshSessionsList()
})

onBeforeUnmount(stopPolling)

// 暴露给父组件与单测的契约面
defineExpose({
  refreshAll,
  createSession,
  startSession,
  runLoop,
  control,
  compileDraft,
  startReplay,
  publishDraft,
  formDeviceId,
  formPackage,
  devicePackages,
  packagesLoading,
  loadDevicePackages,
  formGoal,
  formOutcome,
  session,
  replayStateConfirmed,
  replayModuleId,
  publishedCaseId,
  errorMessage,
  canRunLoop,
  canStartReplay,
  canPublish,
})
</script>

<style scoped>
.agent-panel {
  margin-top: 16px;
  background: var(--c-bg-elevated);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-lg);
  padding: 20px;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.panel-kicker {
  color: var(--c-text-tertiary);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0;
  text-transform: none;
}

.panel-head h2 {
  margin: 4px 0 0;
  color: var(--c-text);
  font-size: 16px;
  font-weight: 600;
}

.agent-head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.session-select {
  width: 220px;
}

.agent-description {
  margin: 8px 0 16px;
  color: var(--c-text-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.agent-alert {
  margin-bottom: 16px;
  border-radius: var(--radius-sm);
}

.agent-empty {
  padding: 24px;
  text-align: center;
  color: var(--c-text-tertiary);
  font-size: 13px;
  background: var(--c-bg-subtle);
  border-radius: var(--radius-md);
  margin-bottom: 16px;
}

.agent-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--c-bg-subtle);
  padding: 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--c-border-subtle);
}

.agent-form-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group label {
  color: var(--c-text-secondary);
  font-size: 12px;
  font-weight: 500;
}

.agent-budget-row {
  display: flex;
  gap: 8px;
}

.agent-package-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.agent-package-input {
  flex: 1;
  min-width: 0;
}

.form-hint {
  color: var(--c-text-tertiary);
  font-size: 11px;
  line-height: 1.4;
}

.agent-form-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 4px;
}

.agent-session {
  margin-top: 20px;
  border-top: 1px solid var(--c-border);
  padding-top: 16px;
}

.agent-session-head {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: space-between;
  align-items: center;
}

.agent-session-meta {
  display: flex;
  gap: 12px;
  align-items: center;
  font-size: 13px;
}

.tabular-nums {
  font-family: 'JetBrains Mono', monospace, sans-serif;
  font-variant-numeric: tabular-nums;
}

.agent-controller {
  color: var(--c-text-secondary);
  font-size: 12px;
}

.agent-usage {
  color: var(--c-text-tertiary);
  font-size: 12px;
}

.agent-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.agent-hint {
  color: var(--c-text-tertiary);
  font-size: 12px;
  margin: 8px 0 16px;
}

.agent-events {
  margin-bottom: 20px;
}

.agent-events-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.agent-events-head strong {
  font-size: 13px;
  color: var(--c-text);
}

.agent-events-note {
  color: var(--c-text-tertiary);
  font-size: 11px;
}

.agent-events-empty {
  color: var(--c-text-tertiary);
  font-size: 12px;
  padding: 12px 0;
  text-align: center;
}

.agent-event-list {
  max-height: 240px;
  overflow-y: auto;
  margin: 0;
  padding: 0;
  list-style: none;
  border: 1px solid var(--c-border-subtle);
  border-radius: var(--radius-sm);
  background: var(--c-bg-subtle);
}

.agent-event-row {
  display: grid;
  grid-template-columns: 60px 1fr 100px;
  gap: 12px;
  font-size: 12px;
  padding: 6px 12px;
  border-bottom: 1px solid var(--c-border-subtle);
  align-items: center;
}

.agent-event-row:last-child {
  border-bottom: none;
}

.agent-event-seq {
  color: var(--c-text-tertiary);
  font-family: 'JetBrains Mono', monospace, sans-serif;
  font-variant-numeric: tabular-nums;
}

.agent-event-type {
  color: var(--c-text);
  font-weight: 500;
}

.agent-event-time {
  color: var(--c-text-tertiary);
  font-size: 11px;
  text-align: right;
}

.agent-draft {
  margin-top: 16px;
  border-top: 1px solid var(--c-border-subtle);
  padding-top: 16px;
}

.agent-draft-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.agent-draft-head strong {
  font-size: 13px;
  color: var(--c-text);
}

.agent-draft-status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.agent-draft-hash {
  color: var(--c-text-tertiary);
  font-size: 12px;
}

.agent-blocking {
  background: var(--c-error-soft, rgba(220, 38, 38, 0.08));
  border: 1px solid var(--c-error, #dc2626);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  margin-bottom: 12px;
  color: var(--c-error, #dc2626);
  font-size: 12px;
}

.agent-blocking ul {
  margin: 6px 0 0;
  padding-left: 18px;
}

.agent-steps {
  margin-bottom: 16px;
  background: var(--c-bg-subtle);
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  font-size: 12px;
}

.agent-steps ol {
  margin: 6px 0 0;
  padding-left: 20px;
  color: var(--c-text);
}

.agent-steps li {
  margin-bottom: 4px;
}

.agent-replay {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.agent-replay-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.agent-preview-items {
  margin-top: 8px;
  font-size: 12px;
}

.agent-preview-item {
  display: block;
  margin-bottom: 4px;
}

.agent-preview-item.fail {
  color: var(--c-error, #dc2626);
}

.agent-preview-item.warn {
  color: var(--c-warning, #d97706);
}

.agent-published {
  color: var(--c-success, #059669);
  font-size: 12px;
  font-weight: 500;
  margin-top: 4px;
}
</style>
