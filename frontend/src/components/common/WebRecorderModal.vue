<template>
  <a-modal
    :open="open"
    :title="t('case.drawer.web.recorder.title')"
    :width="active ? 1160 : 680"
    :footer="null"
    class="web-recorder-modal"
    @cancel="handleClose"
  >
    <a-alert
      v-if="props.replaySteps && props.replaySteps.length && !active"
      type="info"
      show-icon
      class="resume-mode-banner"
      :message="t('case.drawer.web.recorder.resume_mode_title')"
      :description="t('case.drawer.web.recorder.resume_mode_desc', { count: props.replaySteps.length })"
      style="margin-bottom: 16px"
    />

    <!-- 未启动录制时的配置表单 -->
    <a-form v-if="!active" layout="vertical">
      <a-form-item :label="t('case.drawer.web.recorder.start_url')" required>
        <a-input
          v-model:value="startUrl"
          :disabled="active || starting"
          :placeholder="t('case.drawer.web.recorder.start_url_placeholder')"
          @press-enter="startRecording"
        />
      </a-form-item>
      <a-form-item :label="t('case.drawer.web.recorder.browser')">
        <a-select v-model:value="browser" :disabled="active || starting" style="width: 100%">
          <a-select-option value="chromium">Chromium</a-select-option>
          <a-select-option value="firefox">Firefox</a-select-option>
          <a-select-option value="webkit">WebKit</a-select-option>
        </a-select>
        <div class="form-hint">{{ t('case.drawer.web.recorder.browser_hint') }}</div>
      </a-form-item>
      <a-form-item v-if="!props.showCapture" :label="t('case.drawer.web.recorder.auto_assert')">
        <div class="auto-assert-row">
          <a-switch v-model:checked="autoAssert" :disabled="active || starting" />
          <span class="form-hint auto-assert-hint">{{ t('case.drawer.web.recorder.auto_assert_hint') }}</span>
        </div>
      </a-form-item>
    </a-form>

    <a-alert
      v-if="!active && workerStatusError"
      type="warning"
      show-icon
      :message="t('case.drawer.web.recorder.worker_status_error')"
      :description="workerStatusError"
      style="margin-bottom: 16px"
    />
    <a-alert
      v-else-if="!active && workerStatus"
      :type="workerStatus.ready ? 'success' : 'error'"
      show-icon
      :message="workerStatusMessage"
      :description="workerStatusDescription"
      style="margin-bottom: 16px"
    />
    <div v-if="!active && (workerStatus || workerStatusError)" class="worker-status-actions">
      <a-button type="link" size="small" :loading="workerStatusLoading" @click="loadWorkerStatus">
        {{ t('case.drawer.web.recorder.refresh_worker_status') }}
      </a-button>
    </div>

    <!-- 录制中的云端交互双栏控制台 -->
    <div v-if="active" class="cloud-recorder-layout">
      <!-- 左侧：云端虚拟浏览器视窗 -->
      <div class="cloud-viewport-pane">
        <!-- 浏览器地址栏导航 -->
        <div class="browser-navbar">
          <a-button-group size="small">
            <a-button :title="t('case.drawer.web.recorder.browser_back')" @click="handleSendKey('Alt+ArrowLeft')">
              <ArrowLeftOutlined />
            </a-button>
            <a-button :title="t('case.drawer.web.recorder.browser_reload')" @click="handleInteract('reload')">
              <ReloadOutlined />
            </a-button>
          </a-button-group>
          <a-input
            v-model:value="navInputUrl"
            size="small"
            class="browser-url-bar"
            placeholder="http://..."
            @press-enter="handleNavigate"
          >
            <template #prefix>
              <CompassOutlined style="color: var(--c-text-tertiary)" />
            </template>
            <template #suffix>
              <span class="live-dot" :title="t('case.drawer.web.recorder.click_hint')"></span>
            </template>
          </a-input>
          <a-button size="small" type="primary" @click="handleNavigate">前往</a-button>
        </div>

        <!-- 交互视口画布 -->
        <div
          ref="viewportRef"
          tabindex="0"
          class="viewport-screen-wrap"
          :title="t('case.drawer.web.recorder.click_hint')"
          @click="handleCanvasClick"
          @wheel.prevent="handleCanvasWheel"
          @keydown="handleViewportKeydown"
          @compositionend="handleViewportCompositionEnd"
          @paste="handleViewportPaste"
        >
          <img
            v-if="frameUrl"
            ref="frameImgRef"
            :src="frameUrl"
            class="viewport-frame-img"
            alt="Cloud Browser Live View"
            draggable="false"
          />
          <div v-else class="viewport-loading-state">
            <a-spin :tip="t('common.loading')" />
          </div>
          <div class="viewport-crosshair-badge">
            <DesktopOutlined /> {{ t('case.drawer.web.recorder.cloud_viewport_title') }}
          </div>
        </div>

        <!-- 键盘打字与功能按键条 -->
        <div class="viewport-keyboard-bar">
          <div class="input-send-box">
            <a-input
              v-model:value="inputText"
              size="small"
              :placeholder="t('case.drawer.web.recorder.input_placeholder')"
              @press-enter="handleSendInput"
            >
              <template #addonAfter>
                <a-button type="link" size="small" style="height: 22px; padding: 0 4px" @click="handleSendInput">
                  <SendOutlined /> {{ t('case.drawer.web.recorder.send_text') }}
                </a-button>
              </template>
            </a-input>
          </div>
          <a-space size="small" wrap class="quick-keys-row">
            <a-button size="small" @click="handleSendKey('Enter')">{{ t('case.drawer.web.recorder.key_enter') }}</a-button>
            <a-button size="small" @click="handleSendKey('Tab')">{{ t('case.drawer.web.recorder.key_tab') }}</a-button>
            <a-button size="small" @click="handleSendKey('Backspace')">{{ t('case.drawer.web.recorder.key_backspace') }}</a-button>
            <a-button size="small" @click="handleSendKey('Escape')">{{ t('case.drawer.web.recorder.key_esc') }}</a-button>
          </a-space>
        </div>
      </div>

      <!-- 右侧：捕获步骤列表 -->
      <div class="cloud-steps-pane">
        <div class="steps-pane-header">
          <span class="steps-pane-title">录制捕获步骤 ({{ steps.length }})</span>
          <span class="cloud-status-badge">实时捕获中</span>
        </div>

        <a-empty v-if="!steps.length" :description="t('case.drawer.web.recorder.no_steps')" style="margin: 40px 0" />

        <a-list v-if="steps.length" size="small" bordered class="cloud-steps-list">
          <a-list-item v-for="(step, index) in steps" :key="`${step.action}-${index}`">
            <div class="recorded-step-row">
              <span class="recorded-step-index">#{{ index + 1 }}</span>
              <a-tag :color="isAssertionAction(step.action) ? 'green' : 'blue'">{{ actionLabel(step.action) }}</a-tag>
              <span class="recorded-step-name" :title="step.name">{{ step.name }}</span>
            </div>
          </a-list-item>
        </a-list>

        <section v-if="evidenceArtifacts.length || evidence?.artifact_error" class="recording-evidence">
          <div v-if="evidenceArtifacts.length" class="evidence-links">
            <a
              v-for="artifact in evidenceArtifacts"
              :key="artifact.kind"
              :href="artifact.url"
              target="_blank"
              rel="noreferrer"
            >
              {{ artifactLabel(artifact.kind) }}
            </a>
          </div>
          <a-collapse v-if="evidenceEventCount" size="small" class="evidence-collapse">
            <a-collapse-panel key="events" :header="t('case.drawer.web.recorder.evidence_events', { count: evidenceEventCount })">
              <pre class="evidence-preview">{{ formatEvidence(evidence?.network_events?.slice(-8)) }}</pre>
            </a-collapse-panel>
          </a-collapse>
        </section>
      </div>
    </div>

    <!-- 异常提示 -->
    <a-alert
      v-if="error"
      type="error"
      show-icon
      :message="t('case.drawer.web.recorder.error')"
      :description="error"
      style="margin: 16px 0 0"
    />

    <!-- 底部操作按钮 -->
    <div class="recorder-actions" :class="{ 'in-session': active }">
      <a-button v-if="!active" type="primary" :loading="starting" :disabled="workerUnavailable" @click="startRecording">
        {{ t('case.drawer.web.recorder.start') }}
      </a-button>
      <a-button v-if="active && showCapture" type="primary" :loading="capturing" @click="captureScreenshot">
        {{ t('case.drawer.web.recorder.capture') }}
      </a-button>
      <a-button v-if="active && !showCapture" danger :loading="stopping" @click="() => stopRecording()">
        {{ t('case.drawer.web.recorder.stop') }}
      </a-button>
      <a-button v-if="steps.length && !active" type="primary" @click="applySteps">
        {{ t('case.drawer.web.recorder.import') }}
      </a-button>
      <a-button v-if="!active" @click="handleClose">
        {{ t('common.cancel') }}
      </a-button>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  ArrowLeftOutlined,
  ReloadOutlined,
  CompassOutlined,
  DesktopOutlined,
  SendOutlined,
} from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import { normalizeRecordingUrl, recordingErrorMessage } from '@/utils/webRecording'
import {
  webRecordingApi,
  type WebRecordingItem,
  type WebRecordingSource,
  type WebRecordingStatus,
  type WebRecordingStep,
  type WebRecordingWorkersResponse,
} from '@/api'

const props = defineProps<{
  open: boolean
  initialUrl?: string
  projectId?: number | null
  showCapture?: boolean
  autoApply?: boolean
  replaySteps?: Array<Record<string, unknown>>
  resumeTargetIndex?: number | null
  source?: WebRecordingSource
}>()
const emit = defineEmits<{
  close: []
  recorded: [steps: WebRecordingStep[], assetIds: number[], recordingRecordId?: number | null]
  stopped: [recording: WebRecordingItem]
  captured: [file: File, pageUrl: string]
}>()
const { t } = useI18n()

const startUrl = ref('')
const browser = ref<'chromium' | 'firefox' | 'webkit'>('chromium')
const autoAssert = ref(true)
const recordingId = ref<string | null>(null)
const recordingRecordId = ref<number | null>(null)
const status = ref<WebRecordingStatus>('stopped')
const steps = ref<WebRecordingStep[]>([])
const assetIds = ref<number[]>([])
const currentUrl = ref('')
const evidence = ref<import('@/api').WebRecordingItem | null>(null)
const error = ref('')
const starting = ref(false)
const stopping = ref(false)
const capturing = ref(false)
const workerStatus = ref<WebRecordingWorkersResponse | null>(null)
const workerStatusError = ref('')
const workerStatusLoading = ref(false)
let pollTimer: ReturnType<typeof setTimeout> | null = null

const frameUrl = ref('')
const frameLoading = ref(false)
const navInputUrl = ref('')
const inputText = ref('')
const viewportRef = ref<HTMLElement | null>(null)
const frameImgRef = ref<HTMLImageElement | null>(null)
let lastFrameBlobUrl = ''

async function refreshFrame() {
  if (!recordingId.value || !active.value || frameLoading.value) return
  frameLoading.value = true
  try {
    const blob = await webRecordingApi.screenshot(recordingId.value)
    if (lastFrameBlobUrl) {
      URL.revokeObjectURL(lastFrameBlobUrl)
    }
    const newUrl = URL.createObjectURL(blob)
    lastFrameBlobUrl = newUrl
    frameUrl.value = newUrl
  } catch {
    // 忽略单次截图错误
  } finally {
    frameLoading.value = false
  }
}

async function handleInteract(action: string, params: Record<string, unknown> = {}) {
  if (!recordingId.value || !active.value) return
  try {
    const res = await webRecordingApi.interact(recordingId.value, action, params)
    if (res?.snapshot) {
      applyRecordingResult(res.snapshot)
    }
    setTimeout(() => void refreshFrame(), 220)
  } catch (err: any) {
    message.warning(err?.response?.data?.detail || err?.message || '交互动作执行失败')
  }
}

function handleCanvasClick(e: MouseEvent) {
  viewportRef.value?.focus()
  const targetEl = frameImgRef.value ?? (e.currentTarget as HTMLElement)
  const rect = targetEl.getBoundingClientRect()
  if (!rect.width || !rect.height) return
  const scaleX = 1280 / rect.width
  const scaleY = 720 / rect.height
  const rawX = (e.clientX - rect.left) * scaleX
  const rawY = (e.clientY - rect.top) * scaleY
  if (rawX < 0 || rawY < 0 || rawX > 1280 || rawY > 720) return
  const x = Math.round(rawX)
  const y = Math.round(rawY)
  void handleInteract('click', { x, y, button: 'left' })
}

function handleCanvasWheel(e: WheelEvent) {
  void handleInteract('scroll', { delta_x: e.deltaX, delta_y: e.deltaY })
}

const FORWARD_KEYS = new Set([
  'Enter',
  'Backspace',
  'Tab',
  'Escape',
  'Delete',
  'ArrowLeft',
  'ArrowRight',
  'ArrowUp',
  'ArrowDown',
  'Home',
  'End',
])

function handleViewportKeydown(e: KeyboardEvent) {
  if (!active.value || e.isComposing) return
  // 允许 Ctrl/Cmd+V 触发 paste 事件
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'v') return
  if (FORWARD_KEYS.has(e.key)) {
    e.preventDefault()
    e.stopPropagation()
    void handleInteract('press', { key: e.key })
    return
  }
  if (!e.ctrlKey && !e.metaKey && !e.altKey && e.key.length === 1) {
    e.preventDefault()
    e.stopPropagation()
    void handleInteract('type', { text: e.key })
  }
}

function handleViewportCompositionEnd(e: CompositionEvent) {
  if (!active.value) return
  if (e.data) {
    void handleInteract('type', { text: e.data })
  }
}

function handleViewportPaste(e: ClipboardEvent) {
  if (!active.value) return
  const text = e.clipboardData?.getData('text')
  if (text) {
    e.preventDefault()
    void handleInteract('type', { text })
  }
}

function handleSendInput() {
  const text = inputText.value
  if (!text) return
  void handleInteract('type', { text })
  inputText.value = ''
}

function handleSendKey(key: string) {
  void handleInteract('press', { key })
}

function handleNavigate() {
  const url = navInputUrl.value.trim()
  if (!url) return
  void handleInteract('goto', { url })
}

const recordingSource = computed<WebRecordingSource | undefined>(() => {
  if (props.source) return props.source
  if (props.replaySteps?.length) return 'resume'
  return undefined
})
const active = computed(() => status.value === 'starting' || status.value === 'recording' || status.value === 'stopping')
const workerUnavailable = computed(() => workerStatus.value?.mode === 'worker' && !workerStatus.value.ready)
const workerStatusMessage = computed(() => {
  if (!workerStatus.value) return ''
  if (workerStatus.value.mode !== 'worker') return t('case.drawer.web.recorder.worker_local_ready')
  if (workerStatus.value.ready) {
    return t('case.drawer.web.recorder.worker_ready', {
      registered: workerStatus.value.registered_count,
      available: workerStatus.value.available_count,
    })
  }
  if (workerStatus.value.registered_count) {
    return t('case.drawer.web.recorder.worker_full', { registered: workerStatus.value.registered_count })
  }
  return t('case.drawer.web.recorder.worker_missing')
})
const workerStatusDescription = computed(() => {
  if (!workerStatus.value) return ''
  return workerStatus.value.mode === 'worker'
    ? t('case.drawer.web.recorder.worker_status_hint')
    : t('case.drawer.web.recorder.worker_local_hint')
})
const evidenceArtifacts = computed(() => Object.values(evidence.value?.artifacts ?? {}))
const evidenceEventCount = computed(() =>
  (evidence.value?.network_events?.length ?? 0) +
  (evidence.value?.console_messages?.length ?? 0) +
  (evidence.value?.page_errors?.length ?? 0),
)

function reset() {
  clearPoll()
  let initial = props.initialUrl ?? ''
  if (!initial && props.replaySteps && props.replaySteps.length) {
    const firstGoto = props.replaySteps.find((s) => s.action === 'goto' || (s.params as Record<string, unknown> | undefined)?.url)
    if (firstGoto) {
      initial = String((firstGoto.params as Record<string, unknown> | undefined)?.url || '')
    }
  }
  startUrl.value = initial
  browser.value = 'chromium'
  autoAssert.value = true
  recordingId.value = null
  recordingRecordId.value = null
  status.value = 'stopped'
  steps.value = []
  assetIds.value = []
  currentUrl.value = ''
  evidence.value = null
  error.value = ''
  starting.value = false
  stopping.value = false
  capturing.value = false
  workerStatus.value = null
  workerStatusError.value = ''
  workerStatusLoading.value = false
  if (lastFrameBlobUrl) {
    URL.revokeObjectURL(lastFrameBlobUrl)
    lastFrameBlobUrl = ''
  }
  frameUrl.value = ''
  navInputUrl.value = ''
  inputText.value = ''
}

function clearPoll() {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

function actionLabel(action: string) {
  return t(`case.lowcode_editor.actions.${action}`, action)
}

function isAssertionAction(action: string) {
  return action.startsWith('assert_')
}

function artifactLabel(kind: string) {
  return t(`case.drawer.web.recorder.artifacts.${kind}`, kind)
}

function formatEvidence(value: unknown) {
  return JSON.stringify(value ?? [], null, 2)
}

function applyRecordingResult(result: WebRecordingItem) {
  const previousStatus = status.value
  status.value = result.status
  steps.value = result.steps ?? []
  assetIds.value = result.asset_ids ?? assetIds.value
  currentUrl.value = result.current_url ?? currentUrl.value
  if (currentUrl.value && !navInputUrl.value) {
    navInputUrl.value = currentUrl.value
  }
  if (result.recording_record_id !== undefined) {
    recordingRecordId.value = result.recording_record_id ?? null
  }
  evidence.value = result
  if (result.error) error.value = result.error
  if (
    previousStatus !== result.status &&
    (result.status === 'stopped' || result.status === 'error')
  ) {
    emit('stopped', result)
  }
}

async function loadWorkerStatus() {
  workerStatusLoading.value = true
  workerStatusError.value = ''
  try {
    workerStatus.value = await webRecordingApi.workers()
  } catch (e: unknown) {
    workerStatus.value = null
    workerStatusError.value = recordingErrorMessage(e, t('case.drawer.web.recorder.error'))
  } finally {
    workerStatusLoading.value = false
  }
}

async function startRecording() {
  if (!startUrl.value.trim()) {
    message.warning(t('case.drawer.web.recorder.start_url_required'))
    return
  }
  if (!props.projectId) {
    message.warning(t('web_assets.select_project_hint'))
    return
  }
  if (workerUnavailable.value) {
    message.warning(t('case.drawer.web.recorder.worker_unavailable'))
    return
  }
  starting.value = true
  error.value = ''
  steps.value = []
  try {
    try {
      startUrl.value = normalizeRecordingUrl(startUrl.value)
    } catch {
      throw new Error(t('case.drawer.web.recorder.start_url_invalid'))
    }
    const result = await webRecordingApi.start({
      start_url: startUrl.value.trim(),
      project_id: props.projectId,
      browser: browser.value,
      replay_steps: props.replaySteps,
      ...(props.showCapture ? {} : { auto_assert: autoAssert.value }),
      ...(recordingSource.value ? { source: recordingSource.value } : {}),
    })
    recordingId.value = result.id
    assetIds.value = []
    applyRecordingResult(result)
    currentUrl.value = result.current_url ?? result.start_url
    navInputUrl.value = currentUrl.value
    schedulePoll()
    setTimeout(() => void refreshFrame(), 400)
  } catch (e: unknown) {
    error.value = recordingErrorMessage(e, t('case.drawer.web.recorder.error'))
    status.value = 'error'
  } finally {
    starting.value = false
  }
}

function schedulePoll() {
  clearPoll()
  if (!recordingId.value || !active.value) return
  pollTimer = setTimeout(() => void pollRecording(), 800)
}

async function pollRecording() {
  if (!recordingId.value) return
  try {
    const result = await webRecordingApi.get(recordingId.value)
    applyRecordingResult(result)
    void refreshFrame()
    schedulePoll()
  } catch (e: unknown) {
    error.value = recordingErrorMessage(e, t('case.drawer.web.recorder.error'))
    status.value = 'error'
  }
}

async function stopRecording(closeAfter = false) {
  if (!recordingId.value) {
    if (closeAfter) emit('close')
    return
  }
  clearPoll()
  stopping.value = true
  let stopSucceeded = false
  try {
    const result = await webRecordingApi.stop(recordingId.value)
    stopSucceeded = true
    applyRecordingResult(result)
  } catch (e: unknown) {
    error.value = recordingErrorMessage(e, t('case.drawer.web.recorder.error'))
    status.value = 'error'
  } finally {
    stopping.value = false
    if (props.autoApply && !closeAfter) {
      if (!stopSucceeded) return
      if (steps.value.length) applySteps()
      else {
        reset()
        emit('close')
      }
      return
    }
    if (closeAfter && stopSucceeded) {
      reset()
      emit('close')
    }
  }
}

async function captureScreenshot() {
  if (!recordingId.value) return
  capturing.value = true
  error.value = ''
  try {
    const blob = await webRecordingApi.screenshot(recordingId.value)
    const file = new File([blob], `web-baseline-${Date.now()}.png`, { type: 'image/png' })
    emit('captured', file, currentUrl.value || startUrl.value)
    await stopRecording(true)
  } catch (e: unknown) {
    error.value = recordingErrorMessage(e, t('case.drawer.web.recorder.error'))
  } finally {
    capturing.value = false
  }
}

function applySteps() {
  if (!steps.value.length) return
  emit(
    'recorded',
    steps.value.map((step) => ({ ...step, params: { ...step.params } })),
    [...assetIds.value],
    recordingRecordId.value,
  )
  reset()
  emit('close')
}

async function handleClose() {
  if (active.value) {
    await stopRecording(true)
    return
  }
  reset()
  emit('close')
}

watch(() => props.open, (open) => {
  if (open) {
    reset()
    void loadWorkerStatus()
  }
}, { immediate: true })

onBeforeUnmount(() => {
  clearPoll()
  if (lastFrameBlobUrl) {
    URL.revokeObjectURL(lastFrameBlobUrl)
    lastFrameBlobUrl = ''
  }
})
</script>

<style scoped>
.recorder-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}

.step-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recording-evidence {
  margin-top: 16px;
}

.evidence-links {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  margin: 10px 2px;
}

.evidence-collapse {
  margin-top: 8px;
}

.evidence-preview {
  max-height: 180px;
  margin: 0;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.form-hint {
  color: #8c8c8c;
  font-size: 12px;
  line-height: 1.5;
  margin-top: 4px;
}

.auto-assert-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.auto-assert-hint {
  margin-top: 0;
}

.worker-status-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: -12px;
  margin-bottom: 8px;
}

/* 云端交互双栏控制台 */
.cloud-recorder-layout {
  display: flex;
  gap: 16px;
  min-height: 480px;
}

.cloud-viewport-pane {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--c-bg-elevated);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md, 8px);
  overflow: hidden;
}

.browser-navbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--c-bg-subtle);
  border-bottom: 1px solid var(--c-border-subtle);
}

.browser-url-bar {
  flex: 1;
  font-family: 'JetBrains Mono', monospace;
}

.live-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #52c41a;
  box-shadow: 0 0 6px #52c41a;
}

.viewport-screen-wrap {
  position: relative;
  flex: 1;
  aspect-ratio: 16 / 9;
  background: #0f172a;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  cursor: crosshair;
  user-select: none;
  outline: none;
}

.viewport-screen-wrap:focus {
  box-shadow: inset 0 0 0 2px #1677ff;
}

.viewport-frame-img {
  width: 100%;
  height: 100%;
  object-fit: fill;
  pointer-events: none;
}

.viewport-loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.viewport-crosshair-badge {
  position: absolute;
  top: 8px;
  left: 10px;
  background: rgba(15, 23, 42, 0.75);
  color: #e2e8f0;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  pointer-events: none;
  backdrop-filter: blur(4px);
}

.viewport-keyboard-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 12px;
  background: var(--c-bg-subtle);
  border-top: 1px solid var(--c-border-subtle);
  flex-wrap: wrap;
}

.input-send-box {
  flex: 1;
  min-width: 220px;
}

.quick-keys-row {
  flex: none;
}

.cloud-steps-pane {
  width: 340px;
  flex: none;
  display: flex;
  flex-direction: column;
  background: var(--c-bg-elevated);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md, 8px);
  padding: 12px;
}

.steps-pane-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--c-border-subtle);
}

.steps-pane-title {
  font-weight: 600;
  font-size: 13px;
  color: var(--c-text);
}

.cloud-status-badge {
  font-size: 11px;
  color: #1677ff;
  background: #e6f4ff;
  border: 1px solid #91caff;
  border-radius: 4px;
  padding: 1px 6px;
}

.cloud-steps-list {
  flex: 1;
  max-height: 460px;
  overflow-y: auto;
}

.recorded-step-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.recorded-step-index {
  font-size: 11px;
  color: var(--c-text-tertiary);
  font-family: monospace;
}

.recorded-step-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}

.recorder-actions.in-session {
  border-top: 1px solid var(--c-border-subtle);
  padding-top: 12px;
}
</style>
