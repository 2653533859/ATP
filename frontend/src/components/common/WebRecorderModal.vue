<template>
  <a-modal
    :open="open"
    :title="t('case.drawer.web.recorder.title')"
    :width="680"
    :footer="null"
    @cancel="handleClose"
  >
    <a-form layout="vertical">
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
    </a-form>

    <a-alert
      v-if="workerStatusError"
      type="warning"
      show-icon
      :message="t('case.drawer.web.recorder.worker_status_error')"
      :description="workerStatusError"
      style="margin-bottom: 16px"
    />
    <a-alert
      v-else-if="workerStatus"
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

    <a-alert
      v-if="active"
      type="info"
      show-icon
      :message="status === 'starting' ? t('case.drawer.web.recorder.starting') : t('case.drawer.web.recorder.recording')"
      :description="t('case.drawer.web.recorder.recording_hint')"
      style="margin-bottom: 16px"
    />
    <a-alert
      v-if="error"
      type="error"
      show-icon
      :message="t('case.drawer.web.recorder.error')"
      :description="error"
      style="margin-bottom: 16px"
    />

    <a-empty v-if="!active && !steps.length && !error" :description="t('case.drawer.web.recorder.no_steps')" />

    <a-list v-if="steps.length" size="small" bordered style="max-height: 280px; overflow: auto">
      <a-list-item v-for="(step, index) in steps" :key="`${step.action}-${index}`">
        <a-tag color="blue">{{ actionLabel(step.action) }}</a-tag>
        <span class="step-name">{{ step.name }}</span>
      </a-list-item>
    </a-list>

    <section v-if="evidenceArtifacts.length || evidence?.artifact_error" class="recording-evidence">
      <a-alert
        :type="evidence?.artifact_error ? 'warning' : 'success'"
        show-icon
        :message="t('case.drawer.web.recorder.evidence_title')"
        :description="evidence?.artifact_error || t('case.drawer.web.recorder.evidence_ready', { count: evidenceArtifacts.length })"
      />
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

    <div class="recorder-actions">
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
import { useI18n } from 'vue-i18n'
import { webRecordingApi, type WebRecordingStatus, type WebRecordingStep, type WebRecordingWorkersResponse } from '@/api'

const props = defineProps<{
  open: boolean
  initialUrl?: string
  projectId?: number | null
  showCapture?: boolean
  autoApply?: boolean
}>()
const emit = defineEmits<{
  close: []
  recorded: [steps: WebRecordingStep[], assetIds: number[]]
  captured: [file: File, pageUrl: string]
}>()
const { t } = useI18n()

const startUrl = ref('')
const browser = ref<'chromium' | 'firefox' | 'webkit'>('chromium')
const recordingId = ref<string | null>(null)
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
  startUrl.value = props.initialUrl ?? ''
  browser.value = 'chromium'
  recordingId.value = null
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

function artifactLabel(kind: string) {
  return t(`case.drawer.web.recorder.artifacts.${kind}`, kind)
}

function formatEvidence(value: unknown) {
  return JSON.stringify(value ?? [], null, 2)
}

function applyRecordingResult(result: import('@/api').WebRecordingItem) {
  status.value = result.status
  steps.value = result.steps ?? []
  assetIds.value = result.asset_ids ?? assetIds.value
  currentUrl.value = result.current_url ?? currentUrl.value
  evidence.value = result
  if (result.error) error.value = result.error
}

async function loadWorkerStatus() {
  workerStatusLoading.value = true
  workerStatusError.value = ''
  try {
    workerStatus.value = await webRecordingApi.workers()
  } catch (e: unknown) {
    workerStatus.value = null
    workerStatusError.value = e instanceof Error ? e.message : String(e)
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
    const result = await webRecordingApi.start({
      start_url: startUrl.value.trim(),
      project_id: props.projectId,
      browser: browser.value,
    })
    recordingId.value = result.id
    assetIds.value = []
    applyRecordingResult(result)
    currentUrl.value = result.current_url ?? result.start_url
    schedulePoll()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : String(e)
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
    schedulePoll()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : String(e)
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
    error.value = e instanceof Error ? e.message : String(e)
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
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    capturing.value = false
  }
}

function applySteps() {
  if (!steps.value.length) return
  emit('recorded', steps.value.map((step) => ({ ...step, params: { ...step.params } })), [...assetIds.value])
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

onBeforeUnmount(() => clearPoll())
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

.worker-status-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: -12px;
  margin-bottom: 8px;
}
</style>
