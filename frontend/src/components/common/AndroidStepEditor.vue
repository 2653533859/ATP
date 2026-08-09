<template>
  <div class="step-editor">
    <div class="step-toolbar">
      <a-button type="dashed" @click="addStep">
        <PlusOutlined /> {{ t('case.step_editor.add_step') }}
      </a-button>
      <span style="color: #999; font-size: 12px; margin-left: 8px">
        {{ t('case.lowcode_editor.drag_hint') }}
      </span>
    </div>

    <a-card size="small" class="visual-recorder" :title="t('case.android_editor.visual_title')">
      <template #extra>
        <a-button size="small" :loading="screenshotLoading" :disabled="!props.deviceId" @click="refreshScreenshot">
          {{ t('case.android_editor.refresh_screen') }}
        </a-button>
      </template>
      <a-alert
        v-if="!props.deviceId"
        type="info"
        show-icon
        :message="t('case.android_editor.visual_no_device')"
      />
      <template v-else>
        <div class="visual-hint">{{ t('case.android_editor.visual_hint') }}</div>
        <div
          class="screen-canvas"
          :class="{ 'is-busy': recordingAction }"
          @pointerdown="onScreenPointerDown"
          @pointerup="onScreenPointerUp"
        >
          <img
            v-if="screenshotUrl"
            ref="screenImageRef"
            :src="screenshotUrl"
            :alt="t('case.android_editor.visual_title')"
            draggable="false"
          />
          <a-empty v-else :description="t('case.android_editor.visual_empty')" />
          <div v-if="recordingAction" class="recording-mask">
            <a-spin :tip="t('case.android_editor.visual_operating')" />
          </div>
        </div>
      </template>
    </a-card>

    <a-empty v-if="steps.length === 0" :description="t('case.lowcode_editor.empty')" />

    <draggable
      v-else
      v-model="steps"
      item-key="_key"
      handle=".drag-handle"
      @end="emitUpdate"
    >
      <template #item="{ element: step, index }">
        <a-card size="small" class="step-card" :key="step._key">
          <template #title>
            <div class="step-header">
              <HolderOutlined class="drag-handle" />
              <span class="step-index">#{{ index + 1 }}</span>
              <a-input
                v-model:value="step.name"
                size="small"
                :placeholder="t('case.lowcode_editor.step_name')"
                style="width: 200px"
                @input="emitUpdate"
              />
              <a-select
                v-model:value="step.action"
                size="small"
                style="width: 160px"
                :options="actionOptions"
                @change="() => onActionChange(step)"
              />
              <a-button
                type="text"
                danger
                size="small"
                @click="removeStep(index)"
              >
                <DeleteOutlined />
              </a-button>
            </div>
          </template>

          <!-- click -->
          <template v-if="step.action === 'click'">
            <a-row :gutter="12">
              <a-col :span="8">
                <a-form-item :label="t('case.android_editor.text')" :label-col="{ span: 8 }">
                  <a-input v-model:value="step.params.text" :placeholder="t('case.android_editor.button_text_placeholder')" @input="emitUpdate" />
                </a-form-item>
              </a-col>
              <a-col :span="8">
                <a-form-item :label="t('case.android_editor.resource_id')" :label-col="{ span: 8 }">
                  <a-input v-model:value="step.params.resourceId" placeholder="com.app:id/btn" @input="emitUpdate" />
                </a-form-item>
              </a-col>
              <a-col :span="4">
                <a-form-item label="X" :label-col="{ span: 8 }">
                  <a-input-number v-model:value="step.params.x" style="width:100%" @change="emitUpdate" />
                </a-form-item>
              </a-col>
              <a-col :span="4">
                <a-form-item label="Y" :label-col="{ span: 8 }">
                  <a-input-number v-model:value="step.params.y" style="width:100%" @change="emitUpdate" />
                </a-form-item>
              </a-col>
            </a-row>
          </template>

          <!-- long_click -->
          <template v-else-if="step.action === 'long_click'">
            <a-row :gutter="12">
              <a-col :span="6">
                <a-form-item label="X" :label-col="{ span: 6 }">
                  <a-input-number v-model:value="step.params.x" style="width:100%" @change="emitUpdate" />
                </a-form-item>
              </a-col>
              <a-col :span="6">
                <a-form-item label="Y" :label-col="{ span: 6 }">
                  <a-input-number v-model:value="step.params.y" style="width:100%" @change="emitUpdate" />
                </a-form-item>
              </a-col>
              <a-col :span="6">
                <a-form-item :label="t('case.android_editor.duration_ms')" :label-col="{ span: 10 }">
                  <a-input-number v-model:value="step.params.duration" :min="300" style="width:100%" @change="emitUpdate" />
                </a-form-item>
              </a-col>
            </a-row>
          </template>

          <!-- swipe -->
          <template v-else-if="step.action === 'swipe'">
            <a-row :gutter="12">
              <a-col :span="8">
                <a-form-item :label="t('case.android_editor.direction')" :label-col="{ span: 8 }">
                  <a-select v-model:value="step.params.direction" allow-clear :placeholder="t('case.android_editor.or_coordinates')" @change="emitUpdate">
                    <a-select-option value="up">{{ t('case.android_editor.directions.up') }}</a-select-option>
                    <a-select-option value="down">{{ t('case.android_editor.directions.down') }}</a-select-option>
                    <a-select-option value="left">{{ t('case.android_editor.directions.left') }}</a-select-option>
                    <a-select-option value="right">{{ t('case.android_editor.directions.right') }}</a-select-option>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :span="4">
                <a-form-item :label="t('case.android_editor.start_x')" :label-col="{ span: 10 }">
                  <a-input-number v-model:value="step.params.x1" style="width:100%" @change="emitUpdate" />
                </a-form-item>
              </a-col>
              <a-col :span="4">
                <a-form-item :label="t('case.android_editor.start_y')" :label-col="{ span: 10 }">
                  <a-input-number v-model:value="step.params.y1" style="width:100%" @change="emitUpdate" />
                </a-form-item>
              </a-col>
              <a-col :span="4">
                <a-form-item :label="t('case.android_editor.end_x')" :label-col="{ span: 10 }">
                  <a-input-number v-model:value="step.params.x2" style="width:100%" @change="emitUpdate" />
                </a-form-item>
              </a-col>
              <a-col :span="4">
                <a-form-item :label="t('case.android_editor.end_y')" :label-col="{ span: 10 }">
                  <a-input-number v-model:value="step.params.y2" style="width:100%" @change="emitUpdate" />
                </a-form-item>
              </a-col>
            </a-row>
          </template>

          <!-- input -->
          <template v-else-if="step.action === 'input'">
            <a-row :gutter="12">
              <a-col :span="12">
                <a-form-item :label="t('case.android_editor.input_content')" :label-col="{ span: 6 }">
                  <a-input v-model:value="step.params.text" :placeholder="t('case.android_editor.input_text_placeholder')" @input="emitUpdate" />
                </a-form-item>
              </a-col>
              <a-col :span="8">
                <a-form-item :label="t('case.android_editor.resource_id')" :label-col="{ span: 8 }">
                  <a-input v-model:value="step.params.resourceId" :placeholder="t('case.android_editor.target_input_placeholder')" @input="emitUpdate" />
                </a-form-item>
              </a-col>
              <a-col :span="4">
                <a-form-item :label="t('case.android_editor.clear')" :label-col="{ span: 10 }">
                  <a-switch v-model:checked="step.params.clear" size="small" @change="emitUpdate" />
                </a-form-item>
              </a-col>
            </a-row>
          </template>

          <!-- press_key -->
          <template v-else-if="step.action === 'press_key'">
            <a-form-item :label="t('case.lowcode_editor.key')" :label-col="{ span: 3 }">
              <a-select v-model:value="step.params.key" style="width: 200px" @change="emitUpdate">
                <a-select-option value="HOME">HOME</a-select-option>
                <a-select-option value="BACK">BACK</a-select-option>
                <a-select-option value="ENTER">ENTER</a-select-option>
                <a-select-option value="MENU">MENU</a-select-option>
                <a-select-option value="RECENT">RECENT</a-select-option>
                <a-select-option value="DELETE">DELETE</a-select-option>
                <a-select-option value="POWER">POWER</a-select-option>
                <a-select-option value="VOLUME_UP">{{ t('case.android_editor.volume_up') }}</a-select-option>
                <a-select-option value="VOLUME_DOWN">{{ t('case.android_editor.volume_down') }}</a-select-option>
              </a-select>
            </a-form-item>
          </template>

          <!-- start_app -->
          <template v-else-if="step.action === 'start_app'">
            <a-row :gutter="12">
              <a-col :span="12">
                <a-form-item :label="t('case.mobile.package_name')" :label-col="{ span: 6 }">
                  <a-input v-model:value="step.params.package" placeholder="com.example.app" @input="emitUpdate" />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="Activity" :label-col="{ span: 6 }">
                  <a-input v-model:value="step.params.activity" :placeholder="t('case.android_editor.activity_placeholder')" @input="emitUpdate" />
                </a-form-item>
              </a-col>
            </a-row>
          </template>

          <!-- stop_app -->
          <template v-else-if="step.action === 'stop_app'">
            <a-form-item :label="t('case.mobile.package_name')" :label-col="{ span: 3 }">
              <a-input v-model:value="step.params.package" placeholder="com.example.app" @input="emitUpdate" />
            </a-form-item>
          </template>

          <!-- assert_text -->
          <template v-else-if="step.action === 'assert_text'">
            <a-form-item :label="t('case.android_editor.expected_text')" :label-col="{ span: 3 }">
              <a-input v-model:value="step.params.text" :placeholder="t('case.android_editor.expected_text_placeholder')" @input="emitUpdate" />
            </a-form-item>
          </template>

          <!-- assert_element -->
          <template v-else-if="step.action === 'assert_element'">
            <a-form-item :label="t('case.android_editor.resource_id')" :label-col="{ span: 3 }">
              <a-input v-model:value="step.params.resourceId" placeholder="com.app:id/element" @input="emitUpdate" />
            </a-form-item>
          </template>

          <!-- wait -->
          <template v-else-if="step.action === 'wait'">
            <a-form-item :label="t('case.android_editor.wait_ms')" :label-col="{ span: 4 }">
              <a-input-number v-model:value="step.params.ms" :min="100" :step="500" style="width: 200px" @change="emitUpdate" />
            </a-form-item>
          </template>

          <template v-else-if="step.action === 'rotate'">
            <a-form-item :label="t('case.android_editor.orientation')" :label-col="{ span: 4 }">
              <a-select v-model:value="step.params.orientation" style="width: 220px" @change="emitUpdate">
                <a-select-option value="portrait">{{ t('case.android_editor.orientations.portrait') }}</a-select-option>
                <a-select-option value="landscape">{{ t('case.android_editor.orientations.landscape') }}</a-select-option>
                <a-select-option value="reverse_portrait">{{ t('case.android_editor.orientations.reverse_portrait') }}</a-select-option>
                <a-select-option value="reverse_landscape">{{ t('case.android_editor.orientations.reverse_landscape') }}</a-select-option>
              </a-select>
            </a-form-item>
          </template>

          <template v-else-if="['grant_permission', 'revoke_permission'].includes(step.action)">
            <a-row :gutter="12">
              <a-col :span="10"><a-form-item :label="t('case.mobile.package_name')"><a-input v-model:value="step.params.package" placeholder="com.example.app" @input="emitUpdate" /></a-form-item></a-col>
              <a-col :span="14"><a-form-item :label="t('case.android_editor.permission')"><a-input v-model:value="step.params.permission" placeholder="android.permission.CAMERA" @input="emitUpdate" /></a-form-item></a-col>
            </a-row>
          </template>

          <template v-else-if="step.action === 'network_profile'">
            <a-form-item :label="t('case.android_editor.network_profile')" :label-col="{ span: 4 }">
              <a-select v-model:value="step.params.profile" style="width: 220px" @change="emitUpdate">
                <a-select-option value="normal">{{ t('case.android_editor.networks.normal') }}</a-select-option>
                <a-select-option value="wifi_off">{{ t('case.android_editor.networks.wifi_off') }}</a-select-option>
                <a-select-option value="data_off">{{ t('case.android_editor.networks.data_off') }}</a-select-option>
                <a-select-option value="offline">{{ t('case.android_editor.networks.offline') }}</a-select-option>
              </a-select>
            </a-form-item>
          </template>

          <template v-else-if="step.action === 'foreground'">
            <a-form-item :label="t('case.mobile.package_name')" :label-col="{ span: 4 }">
              <a-input v-model:value="step.params.package" placeholder="com.example.app" @input="emitUpdate" />
            </a-form-item>
          </template>

        </a-card>
      </template>
    </draggable>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined, DeleteOutlined, HolderOutlined } from '@ant-design/icons-vue'
import draggable from 'vuedraggable'
import { useI18n } from 'vue-i18n'
import { deviceApi } from '@/api'

type StepParams = Record<string, unknown>
type ExternalStep = { action: string; name: string; params: StepParams }

interface StepDef {
  action: string
  name: string
  params: StepParams
  _key: number
}

const props = defineProps<{
  modelValue: ExternalStep[]
  deviceId?: number | null
}>()
const emit = defineEmits<{
  'update:modelValue': [value: ExternalStep[]]
}>()
const { t } = useI18n()

let keyCounter = 0

const actionOptions = computed(() => [
  { label: t('case.android_editor.actions.click'), value: 'click' },
  { label: t('case.android_editor.actions.long_click'), value: 'long_click' },
  { label: t('case.android_editor.actions.swipe'), value: 'swipe' },
  { label: t('case.android_editor.actions.input'), value: 'input' },
  { label: t('case.android_editor.actions.press_key'), value: 'press_key' },
  { label: t('case.android_editor.actions.start_app'), value: 'start_app' },
  { label: t('case.android_editor.actions.stop_app'), value: 'stop_app' },
  { label: t('case.android_editor.actions.assert_text'), value: 'assert_text' },
  { label: t('case.android_editor.actions.assert_element'), value: 'assert_element' },
  { label: t('case.android_editor.actions.wait'), value: 'wait' },
  { label: t('case.android_editor.actions.screenshot'), value: 'screenshot' },
  { label: t('case.android_editor.actions.rotate'), value: 'rotate' },
  { label: t('case.android_editor.actions.grant_permission'), value: 'grant_permission' },
  { label: t('case.android_editor.actions.revoke_permission'), value: 'revoke_permission' },
  { label: t('case.android_editor.actions.network_profile'), value: 'network_profile' },
  { label: t('case.android_editor.actions.background'), value: 'background' },
  { label: t('case.android_editor.actions.foreground'), value: 'foreground' },
])

const defaultParams: Record<string, () => StepParams> = {
  click: () => ({ text: '', resourceId: '', x: undefined, y: undefined }),
  long_click: () => ({ x: undefined, y: undefined, duration: 1000 }),
  swipe: () => ({ direction: 'up', x1: undefined, y1: undefined, x2: undefined, y2: undefined }),
  input: () => ({ text: '', resourceId: '', clear: false }),
  press_key: () => ({ key: 'BACK' }),
  start_app: () => ({ package: '', activity: '' }),
  stop_app: () => ({ package: '' }),
  assert_text: () => ({ text: '' }),
  assert_element: () => ({ resourceId: '' }),
  wait: () => ({ ms: 1000 }),
  screenshot: () => ({}),
  rotate: () => ({ orientation: 'portrait' }),
  grant_permission: () => ({ package: '', permission: '' }),
  revoke_permission: () => ({ package: '', permission: '' }),
  network_profile: () => ({ profile: 'normal' }),
  background: () => ({}),
  foreground: () => ({ package: '' }),
}

function toInternal(items: ExternalStep[]): StepDef[] {
  const keyPool = new Map<string, number[]>()

  for (const step of steps.value) {
    const signature = JSON.stringify(toExternal([step])[0])
    const keys = keyPool.get(signature) ?? []
    keys.push(step._key)
    keyPool.set(signature, keys)
  }

  return items.map((item) => {
    const params = { ...item.params }
    const signature = JSON.stringify({ action: item.action, name: item.name, params })
    const reusableKey = keyPool.get(signature)?.shift()

    return {
      ...item,
      params,
      _key: reusableKey ?? keyCounter++,
    }
  })
}

function toExternal(items: StepDef[]): ExternalStep[] {
  return items.map(({ action, name, params }) => ({ action, name, params }))
}

const steps = ref<StepDef[]>([])
const screenshotUrl = ref<string | null>(null)
const screenshotLoading = ref(false)
const recordingAction = ref(false)
const screenImageRef = ref<HTMLImageElement | null>(null)
const dragStart = ref<{ x: number; y: number } | null>(null)
let screenshotObjectUrl: string | null = null

function isSameSteps(items: ExternalStep[]) {
  return JSON.stringify(items) === JSON.stringify(toExternal(steps.value))
}

watch(
  () => props.modelValue,
  (val) => {
    const nextSteps = val || []
    if (isSameSteps(nextSteps)) {
      return
    }
    steps.value = toInternal(nextSteps)
  },
  { immediate: true },
)

function emitUpdate() {
  emit('update:modelValue', toExternal(steps.value))
}

function addStep() {
  const action = 'click'
  appendStep(action, defaultParams[action]())
}

function removeStep(index: number) {
  steps.value = steps.value.filter((_, i) => i !== index)
  emitUpdate()
}

function onActionChange(step: StepDef) {
  step.params = defaultParams[step.action]?.() ?? {}
  emitUpdate()
}

function appendStep(action: string, params: StepParams) {
  steps.value = [
    ...steps.value,
    {
      action,
      name: t('case.step_editor.step_title', { index: steps.value.length + 1 }),
      params,
      _key: keyCounter++,
    },
  ]
  emitUpdate()
}

function revokeScreenshotUrl() {
  if (screenshotObjectUrl) {
    URL.revokeObjectURL(screenshotObjectUrl)
    screenshotObjectUrl = null
  }
}

async function refreshScreenshot() {
  if (!props.deviceId) return
  screenshotLoading.value = true
  try {
    const blob = await deviceApi.screenshot(props.deviceId)
    const nextUrl = URL.createObjectURL(blob)
    revokeScreenshotUrl()
    screenshotObjectUrl = nextUrl
    screenshotUrl.value = nextUrl
  } catch {
    message.error(t('case.android_editor.visual_refresh_failed'))
  } finally {
    screenshotLoading.value = false
  }
}

function eventToDevicePoint(event: PointerEvent) {
  const image = screenImageRef.value
  if (!image) return null
  const rect = image.getBoundingClientRect()
  if (rect.width <= 0 || rect.height <= 0) return null
  const x = Math.round((event.clientX - rect.left) * (image.naturalWidth / rect.width))
  const y = Math.round((event.clientY - rect.top) * (image.naturalHeight / rect.height))
  return {
    x: Math.max(0, Math.min(image.naturalWidth, x)),
    y: Math.max(0, Math.min(image.naturalHeight, y)),
  }
}

function onScreenPointerDown(event: PointerEvent) {
  if (recordingAction.value) return
  ;(event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId)
  dragStart.value = eventToDevicePoint(event)
}

async function onScreenPointerUp(event: PointerEvent) {
  ;(event.currentTarget as HTMLElement).releasePointerCapture?.(event.pointerId)
  const start = dragStart.value
  const end = eventToDevicePoint(event)
  dragStart.value = null
  if (!start || !end || !props.deviceId || recordingAction.value) return

  const distance = Math.hypot(end.x - start.x, end.y - start.y)
  if (distance < 12) {
    appendStep('click', { text: '', resourceId: '', x: start.x, y: start.y })
    await performLiveAction(
      () => deviceApi.tap(props.deviceId!, { x: start.x, y: start.y }),
      t('case.android_editor.visual_click_added', { x: start.x, y: start.y }),
    )
    return
  }

  appendStep('swipe', {
    direction: undefined,
    x1: start.x,
    y1: start.y,
    x2: end.x,
    y2: end.y,
    duration: 300,
  })
  await performLiveAction(
    () => deviceApi.swipe(props.deviceId!, {
      x1: start.x,
      y1: start.y,
      x2: end.x,
      y2: end.y,
      duration_ms: 300,
    }),
    t('case.android_editor.visual_swipe_added'),
  )
}

async function performLiveAction(action: () => Promise<unknown>, successMessage: string) {
  recordingAction.value = true
  try {
    await action()
    message.success(successMessage)
    await new Promise((resolve) => setTimeout(resolve, 350))
    await refreshScreenshot()
  } catch {
    message.error(t('case.android_editor.visual_action_failed'))
  } finally {
    recordingAction.value = false
  }
}

watch(
  () => props.deviceId,
  (deviceId) => {
    revokeScreenshotUrl()
    screenshotUrl.value = null
    if (deviceId) {
      void refreshScreenshot()
    }
  },
)

onBeforeUnmount(revokeScreenshotUrl)
</script>

<style scoped>
.step-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.step-toolbar {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}
.step-card {
  margin-bottom: 8px;
}
.visual-recorder {
  margin-bottom: 8px;
}
.visual-hint {
  color: #8c8c8c;
  font-size: 12px;
  margin-bottom: 8px;
}
.screen-canvas {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 220px;
  max-height: 520px;
  overflow: hidden;
  background: #111;
  border-radius: 8px;
  cursor: crosshair;
  user-select: none;
  touch-action: none;
}
.screen-canvas img {
  max-width: 100%;
  max-height: 520px;
  object-fit: contain;
  pointer-events: auto;
}
.screen-canvas.is-busy {
  cursor: wait;
}
.recording-mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.35);
}
.step-card :deep(.ant-card-head) {
  min-height: 40px;
  padding: 0 12px;
}
.step-card :deep(.ant-card-head-title) {
  padding: 6px 0;
}
.step-card :deep(.ant-card-body) {
  padding: 8px 12px;
}
.step-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.drag-handle {
  cursor: grab;
  color: #999;
  font-size: 16px;
}
.drag-handle:active {
  cursor: grabbing;
}
.step-index {
  font-weight: 600;
  color: #666;
  min-width: 28px;
}
</style>
