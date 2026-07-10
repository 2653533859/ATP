<template>
  <div class="case-step-editor">
    <div class="toolbar">
      <a-button type="dashed" @click="addStep">{{ t('case.step_editor.add_step') }}</a-button>
      <span class="hint">{{ t('case.step_editor.hint') }}</span>
    </div>

    <a-empty v-if="rows.length === 0" :description="t('case.detail.no_standard_steps')" />

    <a-card v-for="(step, index) in rows" :key="step.step_no ?? index" size="small" class="step-card">
      <template #title>
        <div class="step-title">
          <span>{{ t('case.step_editor.step_title', { index: index + 1 }) }}</span>
          <a-space>
            <a-button size="small" :disabled="index === 0" @click="moveStep(index, -1)">{{ t('case.step_editor.move_up') }}</a-button>
            <a-button size="small" :disabled="index === rows.length - 1" @click="moveStep(index, 1)">{{ t('case.step_editor.move_down') }}</a-button>
            <a-button size="small" danger @click="removeStep(index)">{{ t('common.delete') }}</a-button>
          </a-space>
        </div>
      </template>

      <a-form layout="vertical">
        <a-row :gutter="12">
          <a-col :span="14">
            <a-form-item :label="t('case.ai.action')">
              <a-input v-model:value="step.action" :placeholder="t('case.step_editor.action_placeholder')" />
            </a-form-item>
          </a-col>
          <a-col :span="10">
            <a-form-item :label="t('case.detail.key_step')">
              <a-switch v-model:checked="step.is_key_step" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item :label="t('case.detail.test_data')">
          <a-textarea v-model:value="step.test_data" :rows="2" :placeholder="t('case.step_editor.test_data_placeholder')" />
        </a-form-item>

        <a-form-item :label="t('case.detail.expected_result')">
          <a-textarea v-model:value="step.expected_result" :rows="2" :placeholder="t('case.step_editor.expected_placeholder')" />
        </a-form-item>

        <a-form-item :label="t('case.detail.remarks')">
          <a-textarea v-model:value="step.remarks" :rows="2" :placeholder="t('case.drawer.optional')" />
        </a-form-item>
      </a-form>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { CaseStepItem } from '@/api'

// normalize() 把可空文本字段统一成 string，本地行类型据此收窄，
// 使 a-textarea 的 v-model:value 拿到非 null 类型。
type EditableStep = CaseStepItem & {
  action: string
  test_data: string
  expected_result: string
  remarks: string
}

const props = defineProps<{
  modelValue: CaseStepItem[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: CaseStepItem[]]
}>()
const { t } = useI18n()

const rows = ref<EditableStep[]>([])
const syncingFromProps = ref(false)

function normalize(items: CaseStepItem[]): EditableStep[] {
  return items.map((item, index) => ({
    ...item,
    step_no: index + 1,
    action: item.action ?? '',
    test_data: item.test_data ?? '',
    expected_result: item.expected_result ?? '',
    remarks: item.remarks ?? '',
    is_key_step: Boolean(item.is_key_step),
  }))
}

function syncFromProps() {
  syncingFromProps.value = true
  rows.value = normalize(props.modelValue ?? [])
  void nextTick(() => {
    syncingFromProps.value = false
  })
}

function emitUpdate() {
  emit('update:modelValue', normalize(rows.value))
}

function addStep() {
  rows.value = [
    ...rows.value,
    {
      step_no: rows.value.length + 1,
      action: '',
      test_data: '',
      expected_result: '',
      remarks: '',
      is_key_step: rows.value.length === 0,
    },
  ]
  emitUpdate()
}

function removeStep(index: number) {
  rows.value = rows.value.filter((_, currentIndex) => currentIndex !== index)
  emitUpdate()
}

function moveStep(index: number, offset: number) {
  const targetIndex = index + offset
  if (targetIndex < 0 || targetIndex >= rows.value.length) {
    return
  }
  const next = [...rows.value]
  const [item] = next.splice(index, 1)
  next.splice(targetIndex, 0, item)
  rows.value = next
  emitUpdate()
}

watch(
  () => props.modelValue,
  () => {
    syncFromProps()
  },
  { immediate: true, deep: true },
)

watch(
  rows,
  () => {
    if (syncingFromProps.value) {
      return
    }
    emitUpdate()
  },
  { deep: true },
)
</script>

<style scoped>
.case-step-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.hint {
  color: #888;
  font-size: 12px;
}

.step-card {
  border-radius: 10px;
}

.step-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
</style>
