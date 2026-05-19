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

        </a-card>
      </template>
    </draggable>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { PlusOutlined, DeleteOutlined, HolderOutlined } from '@ant-design/icons-vue'
import draggable from 'vuedraggable'
import { useI18n } from 'vue-i18n'

interface StepDef {
  action: string
  name: string
  params: Record<string, any>
  _key: number
}

const props = defineProps<{
  modelValue: Array<{ action: string; name: string; params: Record<string, any> }>
}>()
const emit = defineEmits<{
  'update:modelValue': [value: Array<{ action: string; name: string; params: Record<string, any> }>]
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
])

const defaultParams: Record<string, () => Record<string, any>> = {
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
}

function toInternal(items: Array<{ action: string; name: string; params: Record<string, any> }>): StepDef[] {
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

function toExternal(items: StepDef[]): Array<{ action: string; name: string; params: Record<string, any> }> {
  return items.map(({ action, name, params }) => ({ action, name, params }))
}

const steps = ref<StepDef[]>([])

function isSameSteps(items: Array<{ action: string; name: string; params: Record<string, any> }>) {
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
  steps.value = [
    ...steps.value,
    {
      action,
      name: t('case.step_editor.step_title', { index: steps.value.length + 1 }),
      params: defaultParams[action](),
      _key: keyCounter++,
    },
  ]
  emitUpdate()
}

function removeStep(index: number) {
  steps.value = steps.value.filter((_, i) => i !== index)
  emitUpdate()
}

function onActionChange(step: StepDef) {
  step.params = defaultParams[step.action]?.() ?? {}
  emitUpdate()
}
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
