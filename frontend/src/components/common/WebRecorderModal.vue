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
      <a-form-item :label="t('case.drawer.browser')">
        <a-select v-model:value="browser" :disabled="active || starting" style="width: 180px">
          <a-select-option value="chromium">Chromium</a-select-option>
          <a-select-option value="firefox">Firefox</a-select-option>
          <a-select-option value="webkit">WebKit</a-select-option>
        </a-select>
      </a-form-item>
    </a-form>

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

    <div class="recorder-actions">
      <a-button v-if="!active" type="primary" :loading="starting" @click="startRecording">
        {{ t('case.drawer.web.recorder.start') }}
      </a-button>
      <a-button v-else danger :loading="stopping" @click="() => stopRecording()">
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
import { webRecordingApi, type WebRecordingStatus, type WebRecordingStep } from '@/api'

const props = defineProps<{
  open: boolean
  initialUrl?: string
  projectId?: number | null
}>()
const emit = defineEmits<{
  close: []
  recorded: [steps: WebRecordingStep[]]
}>()
const { t } = useI18n()

const startUrl = ref('')
const browser = ref<'chromium' | 'firefox' | 'webkit'>('chromium')
const recordingId = ref<string | null>(null)
const status = ref<WebRecordingStatus>('stopped')
const steps = ref<WebRecordingStep[]>([])
const error = ref('')
const starting = ref(false)
const stopping = ref(false)
let pollTimer: ReturnType<typeof setTimeout> | null = null

const active = computed(() => status.value === 'starting' || status.value === 'recording' || status.value === 'stopping')

function reset() {
  clearPoll()
  startUrl.value = props.initialUrl ?? ''
  browser.value = 'chromium'
  recordingId.value = null
  status.value = 'stopped'
  steps.value = []
  error.value = ''
  starting.value = false
  stopping.value = false
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

async function startRecording() {
  if (!startUrl.value.trim()) {
    message.warning(t('case.drawer.web.recorder.start_url_required'))
    return
  }
  starting.value = true
  error.value = ''
  steps.value = []
  try {
    const result = await webRecordingApi.start({
      start_url: startUrl.value.trim(),
      project_id: props.projectId ?? null,
      browser: browser.value,
    })
    recordingId.value = result.id
    status.value = result.status
    steps.value = result.steps ?? []
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
    status.value = result.status
    steps.value = result.steps ?? []
    if (result.error) error.value = result.error
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
  try {
    const result = await webRecordingApi.stop(recordingId.value)
    status.value = result.status
    steps.value = result.steps ?? []
    if (result.error) error.value = result.error
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : String(e)
    status.value = 'error'
  } finally {
    stopping.value = false
    if (closeAfter) {
      reset()
      emit('close')
    }
  }
}

function applySteps() {
  if (!steps.value.length) return
  emit('recorded', steps.value.map((step) => ({ ...step, params: { ...step.params } })))
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
  if (open) reset()
})

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
</style>
