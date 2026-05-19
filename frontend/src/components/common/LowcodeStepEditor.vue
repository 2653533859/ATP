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

          <!-- goto -->
          <template v-if="step.action === 'goto'">
            <a-form-item label="URL" :label-col="{ span: 3 }">
              <a-input
                v-model:value="step.params.url"
                :placeholder="t('case.lowcode_editor.url_placeholder')"
                @input="emitUpdate"
              />
            </a-form-item>
          </template>

          <!-- click -->
          <template v-else-if="step.action === 'click'">
            <a-form-item :label="t('case.lowcode_editor.selector')" :label-col="{ span: 3 }">
              <a-input
                v-model:value="step.params.selector"
                :placeholder="t('case.lowcode_editor.selector_playwright_placeholder')"
                @input="emitUpdate"
              />
            </a-form-item>
          </template>

          <!-- fill -->
          <template v-else-if="step.action === 'fill'">
            <a-row :gutter="12">
              <a-col :span="12">
                <a-form-item :label="t('case.lowcode_editor.selector')" :label-col="{ span: 6 }">
                  <a-input
                    v-model:value="step.params.selector"
                    :placeholder="t('case.lowcode_editor.selector_placeholder')"
                    @input="emitUpdate"
                  />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item :label="t('case.lowcode_editor.input_value')" :label-col="{ span: 6 }">
                  <a-input
                    v-model:value="step.params.value"
                    :placeholder="t('case.lowcode_editor.input_value_placeholder')"
                    @input="emitUpdate"
                  />
                </a-form-item>
              </a-col>
            </a-row>
          </template>

          <!-- assert_text -->
          <template v-else-if="step.action === 'assert_text'">
            <a-form-item :label="t('case.lowcode_editor.assert_text')" :label-col="{ span: 3 }">
              <a-input
                v-model:value="step.params.text"
                :placeholder="t('case.lowcode_editor.assert_text_placeholder')"
                @input="emitUpdate"
              />
            </a-form-item>
          </template>

          <!-- assert_visible -->
          <template v-else-if="step.action === 'assert_visible'">
            <a-form-item :label="t('case.lowcode_editor.selector')" :label-col="{ span: 3 }">
              <a-input
                v-model:value="step.params.selector"
                :placeholder="t('case.lowcode_editor.assert_visible_placeholder')"
                @input="emitUpdate"
              />
            </a-form-item>
          </template>

          <!-- wait -->
          <template v-else-if="step.action === 'wait'">
            <a-form-item :label="t('case.lowcode_editor.wait_time')" :label-col="{ span: 3 }">
              <a-input-number
                v-model:value="step.params.ms"
                :min="100"
                :max="30000"
                addon-after="ms"
                style="width: 200px"
                @change="emitUpdate"
              />
            </a-form-item>
          </template>

          <!-- screenshot -->
          <template v-else-if="step.action === 'screenshot'">
            <a-alert :message="t('case.lowcode_editor.screenshot_hint')" type="info" show-icon />
          </template>

          <!-- select -->
          <template v-else-if="step.action === 'select'">
            <a-row :gutter="12">
              <a-col :span="12">
                <a-form-item :label="t('case.lowcode_editor.selector')" :label-col="{ span: 6 }">
                  <a-input
                    v-model:value="step.params.selector"
                    :placeholder="t('case.lowcode_editor.select_placeholder')"
                    @input="emitUpdate"
                  />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item :label="t('case.lowcode_editor.option_value')" :label-col="{ span: 6 }">
                  <a-input
                    v-model:value="step.params.value"
                    :placeholder="t('case.lowcode_editor.option_value_placeholder')"
                    @input="emitUpdate"
                  />
                </a-form-item>
              </a-col>
            </a-row>
          </template>

          <!-- press -->
          <template v-else-if="step.action === 'press'">
            <a-row :gutter="12">
              <a-col :span="12">
                <a-form-item :label="t('case.lowcode_editor.key')" :label-col="{ span: 6 }">
                  <a-input
                    v-model:value="step.params.key"
                    :placeholder="t('case.lowcode_editor.key_placeholder')"
                    @input="emitUpdate"
                  />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item :label="t('case.lowcode_editor.target_element')" :label-col="{ span: 6 }">
                  <a-input
                    v-model:value="step.params.selector"
                    :placeholder="t('case.lowcode_editor.target_element_placeholder')"
                    @input="emitUpdate"
                  />
                </a-form-item>
              </a-col>
            </a-row>
          </template>

          <!-- hover -->
          <template v-else-if="step.action === 'hover'">
            <a-form-item :label="t('case.lowcode_editor.selector')" :label-col="{ span: 3 }">
              <a-input
                v-model:value="step.params.selector"
                :placeholder="t('case.lowcode_editor.hover_placeholder')"
                @input="emitUpdate"
              />
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
  { label: t('case.lowcode_editor.actions.goto'), value: 'goto' },
  { label: t('case.lowcode_editor.actions.click'), value: 'click' },
  { label: t('case.lowcode_editor.actions.fill'), value: 'fill' },
  { label: t('case.lowcode_editor.actions.assert_text'), value: 'assert_text' },
  { label: t('case.lowcode_editor.actions.assert_visible'), value: 'assert_visible' },
  { label: t('case.lowcode_editor.actions.wait'), value: 'wait' },
  { label: t('case.lowcode_editor.actions.screenshot'), value: 'screenshot' },
  { label: t('case.lowcode_editor.actions.select'), value: 'select' },
  { label: t('case.lowcode_editor.actions.press'), value: 'press' },
  { label: t('case.lowcode_editor.actions.hover'), value: 'hover' },
])

const defaultParams: Record<string, () => Record<string, any>> = {
  goto: () => ({ url: '' }),
  click: () => ({ selector: '' }),
  fill: () => ({ selector: '', value: '' }),
  assert_text: () => ({ text: '' }),
  assert_visible: () => ({ selector: '' }),
  wait: () => ({ ms: 1000 }),
  screenshot: () => ({}),
  select: () => ({ selector: '', value: '' }),
  press: () => ({ key: 'Enter', selector: '' }),
  hover: () => ({ selector: '' }),
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
  const action = 'goto'
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
